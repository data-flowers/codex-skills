// Shared Airtable contract and transport. Mutations are never retried implicitly.
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

export const API_ROOT = 'https://api.airtable.com/v0';
export const CONTRACT_DATA = JSON.parse(readFileSync(new URL('./ptah_contract.json', import.meta.url), 'utf8'));
export const CONTRACT = CONTRACT_DATA.fields;
export const isMain = (url) => Boolean(process.argv[1]) && url === pathToFileURL(process.argv[1]).href;
export function fail(message) { throw new Error(message); }
export function arg(name, fallback = null) {
  const index = process.argv.indexOf(`--${name}`);
  if (index < 0) return fallback;
  const value = process.argv[index + 1];
  if (value === undefined || value.startsWith('--')) fail(`Missing value for --${name}`);
  return value;
}
export const hasFlag = (name) => process.argv.includes(`--${name}`);
export function parsePositiveInt(value, label) {
  if (!/^\d+$/.test(String(value)) || !Number.isSafeInteger(Number(value)) || Number(value) < 1) {
    fail(`${label} must be a positive integer`);
  }
  return Number(value);
}
export function parseAirtableUrl(rawUrl) {
  const url = new URL(rawUrl);
  const match = url.pathname.match(/^\/(?<base>app[a-zA-Z0-9]+)\/(?<table>tbl[a-zA-Z0-9]+)(?:\/(?<view>viw[a-zA-Z0-9]+))?\/?$/);
  if (!['airtable.com', 'www.airtable.com'].includes(url.hostname) || !match?.groups) {
    fail('Expected an Airtable base/table URL');
  }
  return { baseId: match.groups.base, tableId: match.groups.table, viewId: match.groups.view || null };
}
export async function fetchJson(url, token, options = {}) {
  const { method = 'GET', body, ...rest } = options;
  const response = await fetch(url, {
    ...rest, method, signal: rest.signal || AbortSignal.timeout(90000),
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...rest.headers },
    ...(body == null ? {} : { body: typeof body === 'string' ? body : JSON.stringify(body) }),
  });
  const text = await response.text();
  let data;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}\n${typeof data === 'string' ? data : JSON.stringify(data)}`);
  }
  if (data === null || typeof data !== 'object') fail('Airtable returned an invalid JSON response');
  return data;
}
export const fetchBaseSchema = (baseId, token) => fetchJson(`${API_ROOT}/meta/bases/${baseId}/tables`, token);
export const normalizeName = (name) => String(name ?? '').replace(/^\ufeff/, '').trim();
export function describeNameIssue(actual, expected) {
  const issues = [];
  if (String(actual).startsWith('\ufeff')) issues.push('leading BOM');
  if (String(actual) !== String(actual).trim()) issues.push('leading or trailing whitespace');
  if (normalizeName(actual) === expected && !issues.length && actual !== expected) issues.push('invisible name mismatch');
  return issues;
}
export function buildFieldMaps(fields) {
  return { exact: new Map(fields.map(f => [f.name, f])), normalized: new Map(fields.map(f => [normalizeName(f.name), f])) };
}
