#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { randomUUID } from 'node:crypto';
import { createTechweekClient, enumerateEvents, fingerprint, listingFingerprint, validateEvent, TECHWEEK_ENDPOINT } from './techweek_mcp.mjs';

async function readJson(file, fallback) {
  try { return JSON.parse(await fs.readFile(file, 'utf8')); }
  catch (error) { if (error.code === 'ENOENT' || error instanceof SyntaxError) return fallback; throw error; }
}

async function writeJson(file, value) {
  const temporary = `${file}.${randomUUID()}.tmp`;
  try { await fs.writeFile(temporary, JSON.stringify(value, null, 2)); await fs.rename(temporary, file); }
  finally { await fs.rm(temporary, { force: true }); }
}

async function pool(items, workers, task) {
  let next = 0;
  await Promise.all(Array.from({ length: Math.min(workers, items.length) }, async () => {
    while (next < items.length) { const index = next++; await task(items[index], index); }
  }));
}

function fresh(timestamp, now, ttlMs) {
  const age = now - Date.parse(timestamp ?? '');
  return Number.isFinite(age) && age >= 0 && age < ttlMs;
}

function validateCatalog(city, filters) {
  if (!city || !Array.isArray(city.days) || !city.days.length || !Number.isSafeInteger(city.year) ||
      typeof city.timeZone !== 'string' || !city.days.every(day => /^\d{4}-\d{2}-\d{2}$/.test(day) &&
        day.startsWith(`${city.year}-`) && new Date(`${day}T00:00:00Z`).toISOString().startsWith(day)) ||
      fingerprint(city.days) !== fingerprint([...new Set(city.days)].sort())) throw new Error('source_city_invalid');
  try { new Intl.DateTimeFormat('en', { timeZone: city.timeZone }); } catch { throw new Error('source_timezone_invalid'); }
  if (filters.city !== city.slug || filters.timeZone !== city.timeZone ||
      fingerprint(filters.days) !== fingerprint(city.days) || !Array.isArray(filters.tracks)) throw new Error('source_filter_catalog_invalid');
  const keys = new Set();
  for (const track of filters.tracks) {
    if (typeof track.key !== 'string' || !track.key || typeof track.label !== 'string' || keys.has(track.key)) throw new Error('source_track_catalog_invalid');
    keys.add(track.key);
  }
}

async function collectTracks({ client, directory, city, filters, events, now, ttlMs, force, maxPages }) {
  const catalogFingerprint = fingerprint(filters.tracks);
  const populationFingerprint = fingerprint(events.map(event => event.id).sort());
  const cached = await readJson(path.join(directory, 'track-memberships.json'), null);
  const labels = new Map(filters.tracks.map(track => [track.key, track.label]));
  const validMemberships = cached?.memberships && fingerprint(Object.keys(cached.memberships).sort()) === populationFingerprint &&
    Object.values(cached.memberships).every(values => Array.isArray(values) &&
      values.every(value => value && typeof value === 'object' && labels.get(value.key) === value.label));
  if (!force && cached?.city === city.slug && cached.year === city.year &&
      cached.catalogFingerprint === catalogFingerprint && cached.populationFingerprint === populationFingerprint &&
      validMemberships && fresh(cached.fetchedAt, now, ttlMs)) return { ...cached, reused: true };
  const ids = new Set(events.map(event => event.id)), memberships = Object.fromEntries(events.map(event => [event.id, []]));
  const counts = {}, outsideSnapshot = new Set();
  for (const track of filters.tracks) {
    const result = await enumerateEvents(client, city.slug, { track: [track.key] }, maxPages);
    counts[track.key] = result.events.length;
    for (const event of result.events) {
      if (!ids.has(event.id)) outsideSnapshot.add(event.id);
      else memberships[event.id].push({ key: track.key, label: track.label });
    }
  }
  if (outsideSnapshot.size) throw new Error('source_track_membership_outside_snapshot');
  for (const values of Object.values(memberships)) values.sort((a, b) => a.key.localeCompare(b.key));
  return { version: 1, city: city.slug, year: city.year, fetchedAt: new Date(now).toISOString(),
    catalogFingerprint, populationFingerprint, memberships, counts, reused: false };
}

/** Fetch source evidence only. No canonical, taxonomy, logo, Airtable, or publication writes. */
export async function refreshTechweek({ directory, city = 'sf', client = createTechweekClient(), ttlMs = 86_400_000,
  force = false, workers = 2, maxPages = 1_000, now = Date.now() }) {
  if (!directory || !Number.isFinite(ttlMs) || ttlMs <= 0 || !Number.isInteger(workers) || workers < 1 || workers > 6 ||
      !Number.isInteger(maxPages) || maxPages < 1 || !Number.isFinite(now)) throw new Error('invalid_refresh_parameters');
  const startedAt = Date.now();
  const manifest = await client.discover();
  const cities = await client.call('list_cities');
  const selectedCity = cities.cities?.find(item => item.slug === city);
  if (!selectedCity) throw new Error('source_city_not_available');
  const filters = await client.call('list_filters', { city });
  validateCatalog(selectedCity, filters);
  const previousManifest = await readJson(path.join(directory, 'source-manifest.json'), null);
  const previousYear = previousManifest?.year ?? Number(previousManifest?.dates?.[0]?.slice(0, 4));
  if (previousManifest?.city && (previousManifest.city !== city ||
      (Number.isFinite(previousYear) && previousYear !== selectedCity.year))) throw new Error('source_directory_scope_mismatch');
  const [oldListing, oldEvents, oldReport] = await Promise.all([
    readJson(path.join(directory, 'listing.json'), []), readJson(path.join(directory, 'events.json'), []),
    readJson(path.join(directory, 'fetch-report.json'), {}),
  ]);
  if (!Array.isArray(oldListing) || !Array.isArray(oldEvents)) throw new Error('source_local_snapshot_invalid');
  if ([...oldListing, ...oldEvents].some(event => event.citySlug !== city)) throw new Error('source_directory_scope_mismatch');
  const localYear = oldReport.year ?? Number((oldEvents[0]?.date ?? oldListing[0]?.date)?.slice(0, 4));
  if (Number.isFinite(localYear) && localYear !== selectedCity.year) throw new Error('source_directory_scope_mismatch');
  const oldById = new Map(oldListing.map(event => [event.id, event]));
  const oldEvidence = new Map(oldEvents.map(event => [event.id, event]));
  const listing = await enumerateEvents(client, city, {}, maxPages);
  await fs.mkdir(path.join(directory, 'cache'), { recursive: true });
  const tracks = await collectTracks({ client, directory, city: selectedCity, filters, events: listing.events, now, ttlMs, force, maxPages });
  const events = Array(listing.events.length), errors = [], details = { fetched: 0, reused: 0, legacyReused: 0 };
  const refreshReasons = {};
  await pool(listing.events, workers, async (row, index) => {
    const file = path.join(directory, 'cache', `${row.id}.json`);
    const [cached, metadata] = await Promise.all([readJson(file, null), readJson(`${file}.meta.json`, null)]);
    const listingHash = listingFingerprint(row);
    const validCached = cached?.id === row.id && cached.citySlug === city && typeof cached.description === 'string';
    const oldHash = metadata?.eventId === row.id ? metadata.listingFingerprint
      : oldById.has(row.id) ? listingFingerprint(oldById.get(row.id)) : null;
    const fetchedAt = metadata?.eventId === row.id ? metadata.fetchedAt : oldReport.fetchedAt;
    const reason = force ? 'forced' : !validCached ? 'missing_or_invalid' : oldHash !== listingHash ? 'listing_changed'
      : !fresh(fetchedAt, now, ttlMs) ? 'expired' : null;
    let event;
    if (reason) {
      refreshReasons[reason] = (refreshReasons[reason] ?? 0) + 1;
      try {
        const result = await client.call('get_event', { eventId: row.id });
        const detail = validateEvent(result.event, city);
        if (detail.id !== row.id || typeof detail.description !== 'string') throw new Error('source_detail_invalid');
        event = { ...row, ...detail };
        await writeJson(file, event);
        await writeJson(`${file}.meta.json`, { version: 1, eventId: row.id, fetchedAt: new Date(now).toISOString(), listingFingerprint: listingHash });
        details.fetched++;
      } catch {
        errors.push({ id: row.id, code: 'detail_refresh_failed', reason });
        event = { ...cached, ...row, description: validCached ? cached.description : null };
      }
    } else {
      // Fresh enumeration wins over cached listing fields; never overwrite it wholesale.
      event = { ...cached, ...row, description: cached.description };
      details.reused++;
      if (!metadata) {
        details.legacyReused++;
        await writeJson(`${file}.meta.json`, { version: 1, eventId: row.id, fetchedAt, listingFingerprint: listingHash });
      }
    }
    events[index] = { ...event, sourceTracks: tracks.memberships[row.id] ?? [] };
  });
  const currentIds = new Set(events.map(event => event.id));
  const membership = { addedIds: events.filter(event => !oldEvidence.has(event.id)).map(event => event.id),
    missingIds: oldEvents.filter(event => !currentIds.has(event.id)).map(event => event.id) };
  const changedFieldsById = {};
  for (const event of events) {
    const old = oldEvidence.get(event.id);
    if (!old) continue;
    const previous = { ...old, sourceTracks: old.sourceTracks ?? [] };
    const fields = [...new Set([...Object.keys(previous), ...Object.keys(event)])].filter(key =>
      fingerprint({ value: previous[key] }) !== fingerprint({ value: event[key] }));
    if (fields.length) changedFieldsById[event.id] = fields;
  }
  const changedIds = Object.keys(changedFieldsById);
  const delta = { version: 1, city, year: selectedCity.year, addedIds: membership.addedIds, missingIds: membership.missingIds,
    changed: changedIds.map(sourceId => ({ sourceId, fields: changedFieldsById[sourceId],
      classificationReview: changedFieldsById[sourceId].some(field => ['name', 'description', 'themes', 'formats', 'sourceTracks'].includes(field)),
      organizerIdentityReview: changedFieldsById[sourceId].some(field => ['hosts', 'sponsors'].includes(field)) })),
    publicationAction: 'none; review and derive an approved narrow field delta' };
  const report = { version: 1, source: TECHWEEK_ENDPOINT, city, year: selectedCity.year, fetchedAt: new Date(now).toISOString(),
    officialRange: { start: selectedCity.days[0], end: selectedCity.days.at(-1) }, timeZone: selectedCity.timeZone,
    listed: listing.total, unique: events.length, scans: listing.scans,
    fullDescriptions: events.filter(event => typeof event.description === 'string' && event.description.trim()).length,
    details, refreshReasons, tracks: { count: filters.tracks.length, reused: tracks.reused, counts: tracks.counts },
    membership, changedIds, changedFieldsById, errors, complete: errors.length === 0, published: false,
    requests: client.metrics?.requests, retries: client.metrics?.retries, elapsedMs: Date.now() - startedAt };
  if (errors.length) {
    await writeJson(path.join(directory, 'candidate-events.json'), events);
    await writeJson(path.join(directory, 'fetch-report-latest.json'), report);
    return report;
  }
  for (const [name, value] of Object.entries({ 'cities.json': cities, 'filters.json': filters, 'listing.json': listing.events,
    'events.json': events, 'track-memberships.json': tracks, 'mcp-tools.json': manifest, 'source-delta.json': delta,
    'source-manifest.json': { version: 2, source: TECHWEEK_ENDPOINT, city, year: selectedCity.year,
      dates: selectedCity.days, timeZone: selectedCity.timeZone, discovered: events.length, inScope: events.length,
      attempted: events.length, recovered: events.length, failed: 0, detailRequests: details.fetched, detailCacheHits: details.reused,
      population: { discovered: events.length, inScope: events.length, excluded: 0 },
      crawl: { target: 'discovered', attempted: events.length, recovered: events.length, failedSourceIds: [] },
      identity: { stableSourceIdsAvailable: true, profileUrlsAvailable: events.every(event => typeof event.eventUrl === 'string' && event.eventUrl.startsWith('https://')) },
      scopeRule: `Official ${city} calendar, edition ${selectedCity.year}; preserve boundary-spanning dates`,
      membership, fetchedAt: report.fetchedAt } })) await writeJson(path.join(directory, name), value);
  await writeJson(path.join(directory, 'fetch-report.json'), report);
  await writeJson(path.join(directory, 'fetch-report-latest.json'), report);
  return report;
}

export async function main(argv = process.argv.slice(2), defaults = {}) {
  const { values } = parseArgs({ args: argv, options: {
    dir: { type: 'string', default: defaults.directory }, city: { type: 'string', default: defaults.city ?? 'sf' },
    'ttl-hours': { type: 'string', default: '24' }, force: { type: 'boolean' }, resume: { type: 'boolean' },
    workers: { type: 'string', default: '2' }, 'interval-ms': { type: 'string', default: '1000' }, help: { type: 'boolean' },
  } });
  if (values.help) {
    console.log('Usage: node fetch_techweek.mjs --dir <source-directory> [--city sf|la] [--ttl-hours 24] [--force] [--workers 2] [--interval-ms 1000]\nSource-only refresh. --resume is a compatibility alias: listings are always re-enumerated. Never writes Airtable, canonical records, IDs, logos, or publication state.');
    return;
  }
  const intervalMs = Number(values['interval-ms']);
  if (!Number.isFinite(intervalMs) || intervalMs < 250 || intervalMs > 60_000) throw new Error('invalid_request_interval');
  const report = await refreshTechweek({ directory: values.dir, city: values.city, ttlMs: Number(values['ttl-hours']) * 3_600_000,
    force: values.force, workers: Number(values.workers), client: createTechweekClient({ intervalMs }) });
  console.log(JSON.stringify({ complete: report.complete, published: false, events: report.unique, details: report.details,
    tracks: report.tracks.count, added: report.membership.addedIds.length, missing: report.membership.missingIds.length,
    changed: report.changedIds.length, failed: report.errors.length, requests: report.requests, elapsedMs: report.elapsedMs }));
  if (!report.complete) process.exitCode = 1;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) main().catch(error => {
  console.error(`[TechWeekSource] ERROR ${error.message}`); process.exitCode = 1;
});
