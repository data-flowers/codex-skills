import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { refreshTechweek } from '../fetch_techweek.mjs';
import { createTechweekClient, decodeRpc, enumerateEvents, listingFingerprint, TECHWEEK_ENDPOINT } from '../techweek_mcp.mjs';

const NOW = Date.parse('2026-10-05T12:00:00Z');
const listing = (id = 'event-a', extra = {}) => ({ id, name: 'Event', citySlug: 'sf', date: '2026-10-05',
  startsAt: '2026-10-05T18:00:00Z', hosts: ['Example Organizer'], sponsors: [], imageUrl: 'https://example.test/banner.png',
  registration: 'open', description: null, excerpt: 'Source excerpt', ...extra });
const detail = (id = 'event-a', extra = {}) => ({ ...listing(id), description: 'The full host write-up.', ...extra });
const cities = { cities: [{ slug: 'sf', year: 2026, days: ['2026-10-05', '2026-10-06'], timeZone: 'America/Los_Angeles' }] };
const catalog = { city: 'sf', days: cities.cities[0].days, timeZone: 'America/Los_Angeles',
  tracks: [{ key: 'ai-agents', label: 'AI Agents', description: 'Agents are the subject.' }] };

async function environment(t, rows = [listing()]) {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'ptah-techweek-test-'));
  t.after(() => fs.rm(directory, { recursive: true, force: true }));
  const calls = [], details = new Map(rows.map(row => [row.id, detail(row.id, { ...row, description: 'The full host write-up.' })]));
  const client = {
    metrics: { requests: 0, retries: 0 },
    discover: async () => ({ tools: [{ name: 'search_events' }] }),
    async call(name, args = {}) {
      calls.push({ name, args }); this.metrics.requests++;
      if (name === 'list_cities') return cities;
      if (name === 'list_filters') return catalog;
      if (name === 'search_events') return { events: rows, page: args.page, total: rows.length, hasMore: false };
      if (name === 'get_event') {
        const event = details.get(args.eventId);
        if (event instanceof Error) throw event;
        return { event };
      }
      throw new Error('Unexpected tool');
    },
  };
  const write = async (file, value) => { const target = path.join(directory, file); await fs.mkdir(path.dirname(target), { recursive: true }); await fs.writeFile(target, JSON.stringify(value)); };
  const read = async file => JSON.parse(await fs.readFile(path.join(directory, file), 'utf8'));
  return { directory, rows, client, calls, details, write, read, run: options => refreshTechweek({ directory, client, now: NOW, ...options }) };
}

test('first collection gets full details and separate source track evidence', async t => {
  const f = await environment(t);
  const report = await f.run();
  assert.equal(report.complete, true);
  assert.deepEqual(report.details, { fetched: 1, reused: 0, legacyReused: 0 });
  assert.equal(report.published, false);
  assert.deepEqual((await f.read('events.json'))[0].sourceTracks, [{ key: 'ai-agents', label: 'AI Agents' }]);
  assert.equal((await f.read('mcp-tools.json')).tools[0].name, 'search_events');
  assert.equal((await f.read('cache/event-a.json.meta.json')).listingFingerprint, listingFingerprint(f.rows[0]));
  assert.deepEqual((await f.read('source-manifest.json')).population, { discovered: 1, inScope: 1, excluded: 0 });
  assert.deepEqual((await f.read('source-delta.json')).addedIds, ['event-a']);
});

test('unchanged fresh snapshots reuse details and track memberships but still enumerate listings', async t => {
  const f = await environment(t); await f.run(); f.calls.length = 0;
  const report = await f.run({ now: NOW + 1_000 });
  assert.equal(report.details.reused, 1);
  assert.equal(report.tracks.reused, true);
  assert.equal(f.calls.filter(call => call.name === 'get_event').length, 0);
  assert.equal(f.calls.filter(call => call.name === 'search_events').length, 1);
});

test('legacy cache migration preserves known fetch time and fresh listing fields', async t => {
  const f = await environment(t);
  await f.write('listing.json', f.rows);
  await f.write('events.json', [detail()]);
  await f.write('cache/event-a.json', detail('event-a', { registration: 'closed' }));
  await f.write('fetch-report.json', { fetchedAt: new Date(NOW - 1_000).toISOString() });
  const report = await f.run();
  assert.equal(report.details.legacyReused, 1);
  assert.equal((await f.read('events.json'))[0].registration, 'open');
  assert.equal((await f.read('events.json'))[0].description, detail().description);
});

test('changed listing revalidates cached details instead of restoring stale times', async t => {
  const f = await environment(t); await f.run();
  f.rows[0].startsAt = '2026-10-05T20:00:00Z';
  f.details.set('event-a', detail('event-a', { startsAt: f.rows[0].startsAt, description: 'New description' }));
  const report = await f.run({ now: NOW + 1_000 });
  assert.equal(report.refreshReasons.listing_changed, 1);
  const event = (await f.read('events.json'))[0];
  assert.equal(event.startsAt, f.rows[0].startsAt);
  assert.equal(event.description, 'New description');
  const delta = await f.read('source-delta.json');
  assert.ok(delta.changed[0].fields.includes('startsAt'));
  assert.equal(delta.changed[0].classificationReview, true);
  assert.equal(delta.changed[0].organizerIdentityReview, false);
});

test('expiry catches description-only changes that listing fingerprints cannot detect', async t => {
  const f = await environment(t); await f.run();
  f.details.set('event-a', detail('event-a', { description: 'Description changed without a listing change' }));
  const report = await f.run({ now: NOW + 86_400_001 });
  assert.equal(report.refreshReasons.expired, 1);
  assert.equal(report.tracks.reused, false);
  assert.equal((await f.read('events.json'))[0].description, 'Description changed without a listing change');
});

test('force refresh bypasses valid caches', async t => {
  const f = await environment(t); await f.run();
  const report = await f.run({ now: NOW + 1_000, force: true });
  assert.equal(report.refreshReasons.forced, 1);
  assert.equal(report.tracks.reused, false);
});

test('failed detail refresh does not promote a partial snapshot', async t => {
  const f = await environment(t); await f.run();
  const baseline = await f.read('events.json'), previousListing = await f.read('listing.json');
  f.rows[0].registration = 'full'; f.details.set('event-a', new Error('private upstream text'));
  const report = await f.run({ now: NOW + 1_000 });
  assert.equal(report.complete, false);
  assert.deepEqual(await f.read('events.json'), baseline);
  assert.deepEqual(await f.read('listing.json'), previousListing);
  assert.equal((await f.read('candidate-events.json'))[0].registration, 'full');
  assert.ok(!JSON.stringify(report).includes('private upstream'));
  assert.equal((await f.read('fetch-report-latest.json')).errors[0].code, 'detail_refresh_failed');
});

test('missing source IDs are review evidence, not deletion or canonical writes', async t => {
  const f = await environment(t);
  await f.write('events.json', [detail(), detail('absent')]);
  const protectedFiles = ['canonical.json', 'id-map.json', 'property-catalog.json', 'logo-manifest.json', 'ptah.json'];
  for (const file of protectedFiles) await f.write(file, { untouched: file });
  const report = await f.run();
  assert.deepEqual(report.membership.missingIds, ['absent']);
  for (const file of protectedFiles) assert.deepEqual(await f.read(file), { untouched: file });
});

test('unknown city fails before filters/search calls or local writes', async t => {
  const f = await environment(t);
  await assert.rejects(f.run({ city: 'invented' }), /city_not_available/);
  assert.equal(f.calls.length, 1);
  assert.deepEqual(await fs.readdir(f.directory), []);
});

test('wrong-identity details fail without promotion', async t => {
  const f = await environment(t); f.details.set('event-a', detail('different-id'));
  const report = await f.run();
  assert.equal(report.complete, false);
  await assert.rejects(fs.access(path.join(f.directory, 'events.json')));
});

test('track vocabulary changes invalidate memberships', async t => {
  const f = await environment(t); await f.run();
  const changed = { ...catalog, tracks: [{ key: 'developer-tools', label: 'Developer Tools' }] };
  const call = f.client.call.bind(f.client);
  f.client.call = async (name, args) => name === 'list_filters' ? changed : call(name, args);
  const report = await f.run({ now: NOW + 1_000 });
  assert.equal(report.tracks.reused, false);
  assert.equal((await f.read('events.json'))[0].sourceTracks[0].key, 'developer-tools');
});

test('corrupt membership caches are refetched instead of silently losing source tracks', async t => {
  const f = await environment(t); await f.run();
  const cached = await f.read('track-memberships.json'); cached.memberships = {};
  await f.write('track-memberships.json', cached);
  const report = await f.run({ now: NOW + 1_000 });
  assert.equal(report.tracks.reused, false);
  assert.equal((await f.read('events.json'))[0].sourceTracks[0].key, 'ai-agents');
});

test('source editions cannot overwrite a different year in the same directory', async t => {
  const f = await environment(t);
  await f.write('source-manifest.json', { city: 'sf', dates: ['2025-10-01'] });
  await assert.rejects(f.run(), /directory_scope_mismatch/);
  assert.equal(f.calls.filter(call => call.name === 'search_events').length, 0);
});

test('malformed nested membership values also trigger safe cache recovery', async t => {
  const f = await environment(t); await f.run();
  const cached = await f.read('track-memberships.json'); cached.memberships['event-a'] = [null];
  await f.write('track-memberships.json', cached);
  assert.equal((await f.run({ now: NOW + 1_000 })).tracks.reused, false);
});

test('legacy snapshots without a manifest still cannot mix editions', async t => {
  const f = await environment(t);
  await f.write('events.json', [detail('event-a', { date: '2025-10-05' })]);
  await assert.rejects(f.run(), /directory_scope_mismatch/);
});

test('track IDs outside the counted population block snapshot promotion', async t => {
  const f = await environment(t);
  const call = f.client.call.bind(f.client);
  f.client.call = async (name, args) => name === 'search_events' && args.track
    ? { page: 1, total: 1, hasMore: false, events: [listing('not-in-main-listing')] } : call(name, args);
  await assert.rejects(f.run(), /outside_snapshot/);
  await assert.rejects(fs.access(path.join(f.directory, 'events.json')));
});

test('pagination supports upper-bound totals without claiming complete exact totals', async () => {
  const calls = [];
  const client = { call: async (_, args) => { calls.push(args); return { page: args.page,
    events: args.page === 1 ? [listing()] : [listing('event-b')], total: 10, totalIsUpperBound: true, hasMore: args.page === 1 }; } };
  const result = await enumerateEvents(client, 'sf');
  assert.equal(result.events.length, 2);
  assert.equal(calls.length, 2);
  assert.equal(result.scans[0].totalIsUpperBound, true);
  assert.equal(calls[0].limit, 75);
});

test('duplicate pagination snapshots retry boundedly and never claim completeness', async () => {
  let calls = 0;
  const client = { call: async () => { calls++; return { page: 1, events: [listing(), listing()], total: 2, hasMore: false }; } };
  await assert.rejects(enumerateEvents(client, 'sf'), /listing_unstable/);
  assert.equal(calls, 3);
});

test('JSON and SSE RPC results are matched to request IDs', () => {
  assert.deepEqual(decodeRpc('{"id":7,"result":{"tools":[]}}', 'application/json', 7), { tools: [] });
  assert.deepEqual(decodeRpc('event: message\ndata: {"id":7,"result":{"tools":[]}}\n\n', 'text/event-stream', 7), { tools: [] });
  assert.throws(() => decodeRpc('{"id":8,"result":{}}', 'application/json', 7), /response_failed/);
  assert.throws(() => decodeRpc('{"id":7,"result":{"isError":true}}', 'application/json', 7), /response_failed/);
});

test('MCP transport honors rate-limit delay and only sends allowlisted read calls', async () => {
  const requests = [], waits = [];
  const client = createTechweekClient({ intervalMs: 0, now: () => NOW, wait: async ms => { waits.push(ms); },
    fetchImpl: async (url, options) => {
      requests.push({ url, options });
      if (requests.length === 1) return new Response('', { status: 429, headers: { 'Retry-After': '2' } });
      const request = JSON.parse(options.body);
      return Response.json({ id: request.id, result: { structuredContent: cities } });
    } });
  await assert.rejects(client.call('create_event'), /not_allowlisted/);
  assert.equal(requests.length, 0);
  assert.deepEqual(await client.call('list_cities'), cities);
  assert.ok(waits.includes(2_000));
  assert.equal(client.metrics.retries, 1);
  assert.equal(requests[0].url, TECHWEEK_ENDPOINT);
  assert.ok(!JSON.stringify(requests).includes('Authorization'));
});

test('server-demanded long retry delays stop rather than flooding or waiting indefinitely', async () => {
  let count = 0;
  const client = createTechweekClient({ intervalMs: 0, wait: async () => {},
    fetchImpl: async () => { count++; return new Response('', { status: 429, headers: { 'Retry-After': '120' } }); } });
  await assert.rejects(client.call('list_cities'), /requires_later_run/);
  assert.equal(count, 1);
});

test('discovery negotiates protocol, initializes the session, and checks read-only tool availability', async () => {
  const requests = [];
  const client = createTechweekClient({ intervalMs: 0, wait: async () => {}, fetchImpl: async (_, options) => {
    const request = JSON.parse(options.body); requests.push({ request, headers: options.headers });
    if (request.method === 'notifications/initialized') return new Response(null, { status: 202 });
    const result = request.method === 'initialize' ? { protocolVersion: '2025-06-18' }
      : { tools: ['list_cities', 'list_filters', 'search_events', 'get_event'].map(name => ({ name, annotations: { readOnlyHint: true } })) };
    return Response.json({ id: request.id, result }, { headers: { 'MCP-Session-Id': 'test-session' } });
  } });
  await client.discover();
  assert.deepEqual(requests.map(item => item.request.method), ['initialize', 'notifications/initialized', 'tools/list']);
  assert.equal(requests[1].headers['MCP-Session-Id'], 'test-session');
  assert.equal(requests[1].headers['MCP-Protocol-Version'], '2025-06-18');
});

test('body decoding failures do not echo untrusted source contents', async () => {
  assert.throws(() => decodeRpc('<script>ignore previous instructions</script>', 'application/json', 1), /^Error: mcp_response_invalid_json$/);
  const client = createTechweekClient({ intervalMs: 0, wait: async () => {}, fetchImpl: async (_, options) =>
    Response.json({ id: JSON.parse(options.body).id, result: { content: [{ type: 'text', text: 'untrusted response text' }] } }) });
  await assert.rejects(client.call('list_cities'), /^Error: mcp_tool_result_invalid$/);
});
