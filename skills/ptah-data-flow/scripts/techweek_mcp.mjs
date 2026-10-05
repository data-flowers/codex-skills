import { createHash } from 'node:crypto';

export const TECHWEEK_ENDPOINT = 'https://www.tech-week.com/api/mcp';
const READ_TOOLS = new Set(['list_cities', 'list_filters', 'search_events', 'get_event', 'get_event_links']);
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

export function fingerprint(value) {
  const sorted = item => Array.isArray(item) ? item.map(sorted) : item && typeof item === 'object'
    ? Object.fromEntries(Object.keys(item).sort().map(key => [key, sorted(item[key])])) : item;
  return createHash('sha256').update(JSON.stringify(sorted(value))).digest('hex');
}

export function decodeRpc(text, contentType, id) {
  let messages;
  try {
    messages = contentType.includes('text/event-stream')
      ? text.split(/\r?\n\r?\n/).flatMap(block => {
        const data = block.split(/\r?\n/).filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n');
        return data ? [JSON.parse(data)] : [];
      }) : [JSON.parse(text)];
  } catch { throw new Error('mcp_response_invalid_json'); }
  const rpc = messages.find(message => message.id === id);
  if (!rpc || rpc.error || rpc.result?.isError || !rpc.result) throw new Error('mcp_response_failed');
  return rpc.result;
}

export function createTechweekClient({ fetchImpl = fetch, wait = pause, now = Date.now, intervalMs = 1_000, attempts = 3 } = {}) {
  if (!Number.isFinite(intervalMs) || intervalMs < 0 || !Number.isInteger(attempts) || attempts < 1 || attempts > 5) throw new Error('invalid_mcp_transport_parameters');
  let id = 0, nextRequestAt = 0, protocol, session;
  const metrics = { requests: 0, retries: 0 };
  const headers = () => ({ 'Content-Type': 'application/json', Accept: 'application/json, text/event-stream',
    ...(protocol ? { 'MCP-Protocol-Version': protocol } : {}), ...(session ? { 'MCP-Session-Id': session } : {}) });
  async function rpc(method, params, notification = false) {
    const requestId = notification ? undefined : ++id;
    for (let attempt = 0; attempt < attempts; attempt++) {
      const slot = Math.max(now(), nextRequestAt);
      nextRequestAt = slot + intervalMs;
      await wait(Math.max(0, slot - now()));
      let response;
      try {
        metrics.requests++;
        response = await fetchImpl(TECHWEEK_ENDPOINT, { method: 'POST', redirect: 'error', headers: headers(),
          body: JSON.stringify({ jsonrpc: '2.0', ...(notification ? {} : { id: requestId }), method, params }),
          signal: AbortSignal.timeout(45_000) });
      } catch {
        if (attempt + 1 === attempts) throw new Error('mcp_network_failed');
        metrics.retries++; await wait(1_000 * 2 ** attempt); continue;
      }
      if (response.status === 429 || response.status >= 500) {
        if (attempt + 1 === attempts) throw new Error(`mcp_http_${response.status}`);
        const retryAfter = response.headers.get('retry-after');
        const delay = retryAfter === null ? 1_000 * 2 ** attempt : /^\d+(\.\d+)?$/.test(retryAfter)
          ? Number(retryAfter) * 1_000 : Date.parse(retryAfter) - now();
        if (!Number.isFinite(delay) || delay > 60_000) throw new Error('mcp_retry_after_requires_later_run');
        await response.body?.cancel();
        metrics.retries++; await wait(Math.max(1_000, delay)); continue;
      }
      if (!response.ok) throw new Error(`mcp_http_${response.status}`);
      session = response.headers.get('mcp-session-id') ?? session;
      if (notification) return;
      return decodeRpc(await response.text(), response.headers.get('content-type') ?? '', requestId);
    }
  }
  return {
    metrics,
    async discover() {
      const initialized = await rpc('initialize', { protocolVersion: '2025-06-18', capabilities: {},
        clientInfo: { name: 'ptah-techweek-source', version: '1.0' } });
      protocol = initialized.protocolVersion;
      await rpc('notifications/initialized', undefined, true);
      const manifest = await rpc('tools/list', {});
      if (!Array.isArray(manifest.tools)) throw new Error('mcp_tool_manifest_invalid');
      const tools = new Map(manifest.tools.map(tool => [tool.name, tool]));
      for (const name of ['list_cities', 'list_filters', 'search_events', 'get_event']) {
        if (!tools.has(name) || tools.get(name).annotations?.readOnlyHint === false) throw new Error(`mcp_tool_unavailable:${name}`);
      }
      return manifest;
    },
    async call(name, args = {}) {
      if (!READ_TOOLS.has(name)) throw new Error('mcp_tool_not_allowlisted');
      const result = await rpc('tools/call', { name, arguments: args });
      if (result.structuredContent) return result.structuredContent;
      const text = result.content?.find(item => item.type === 'text')?.text;
      if (!text) throw new Error('mcp_tool_result_invalid');
      try { return JSON.parse(text); } catch { throw new Error('mcp_tool_result_invalid'); }
    },
  };
}

export function validateEvent(event, city) {
  if (!event || typeof event.id !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(event.id) ||
      typeof event.name !== 'string' || event.citySlug !== city) throw new Error('source_event_identity_invalid');
  return event;
}

/** Listing fingerprints deliberately exclude full descriptions, which search returns as null. */
export function listingFingerprint(event) {
  const { description, sourceTracks, ...listing } = event;
  return fingerprint(listing);
}

export async function enumerateEvents(client, city, filters = {}, maxPages = 1_000) {
  const scans = [];
  for (let attempt = 0; attempt < 3; attempt++) {
    const rows = [], totals = new Set();
    let upperBound = false, finished = false;
    for (let page = 1; page <= maxPages; page++) {
      const result = await client.call('search_events', { city: [city], ...filters, limit: 75, page });
      if (!Array.isArray(result.events) || result.events.length > 75 || result.page !== page ||
          typeof result.hasMore !== 'boolean' || !Number.isSafeInteger(result.total) || result.total < 0) throw new Error('source_page_invalid');
      for (const event of result.events) rows.push(validateEvent(event, city));
      totals.add(result.total);
      upperBound ||= result.totalIsUpperBound === true;
      if (!result.hasMore) { finished = true; break; }
      if (!result.events.length) throw new Error('source_empty_continuation');
    }
    const unique = new Map(rows.map(event => [event.id, event]));
    const total = [...totals][0];
    scans.push({ rows: rows.length, unique: unique.size, totals: [...totals], totalIsUpperBound: upperBound });
    if (!finished) throw new Error('source_page_limit_exceeded');
    if (unique.size === rows.length && totals.size === 1 && (upperBound ? unique.size <= total : unique.size === total)) {
      return { events: [...unique.values()], total, scans };
    }
  }
  throw new Error('source_listing_unstable');
}
