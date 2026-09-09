#!/usr/bin/env node
import { CONTRACT, CONTRACT_DATA, API_ROOT, isMain, arg, hasFlag, fail, parsePositiveInt, parseAirtableUrl, fetchJson, fetchBaseSchema } from "./airtable_common.mjs";

// Usage:
//   AIRTABLE_TOKEN=pat... node upsert_airtable_csv.mjs \
//     --url "https://airtable.com/app.../tbl.../viw...?blocks=hide" \
//     --csv /abs/path/to/entities.airtable.csv
//
// Notes:
// - Dry-run by default. Add --execute to send requests.
// - Uses PATCH + performUpsert in 100-record work batches by default.
// - Each work batch is internally split into endpoint-safe API requests.
// - Uses Airtable field names from the CSV header.

import fs from "node:fs/promises";

const DEFAULT_BATCH_SIZE = 100;
const API_RECORDS_PER_REQUEST = 10;
const DEFAULT_THROTTLE_MS = 250;

export function parseCsv(text) {
  const rows = [];
  let row = [];
  let value = "";
  let inQuotes = false;
  const source = text.replace(/^\ufeff/, "");

  for (let i = 0; i < source.length; i += 1) {
    const char = source[i];

    if (inQuotes) {
      if (char === '"') {
        if (source[i + 1] === '"') {
          value += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        value += char;
      }
      continue;
    }

    if (char === '"') {
      inQuotes = true;
      continue;
    }

    if (char === ",") {
      row.push(value);
      value = "";
      continue;
    }

    if (char === "\n") {
      row.push(value);
      rows.push(row);
      row = [];
      value = "";
      continue;
    }

    if (char === "\r") {
      continue;
    }

    value += char;
  }

  if (inQuotes) {
    fail("CSV parse error: unmatched quote in input file.");
  }

  if (row.length > 0 || value.length > 0) {
    row.push(value);
    rows.push(row);
  }

  return rows;
}

export async function loadCsvRows(csvPath) {
  const text = await fs.readFile(csvPath, "utf8");
  const rows = parseCsv(text);

  if (rows.length < 2) {
    fail(`CSV has no data rows: ${csvPath}`);
  }

  const headers = rows[0].map((header) => header.trim());
  const seenHeaders = new Set();
  for (const header of headers) {
    if (!header) {
      fail(`CSV contains an empty header: ${csvPath}`);
    }
    if (seenHeaders.has(header)) {
      fail(`CSV contains duplicate header: ${header}`);
    }
    seenHeaders.add(header);
  }

  const records = [];
  for (const rawRow of rows.slice(1)) {
    if (rawRow.every(value => !value.trim())) continue;
    if (rawRow.length !== headers.length) fail("CSV row width does not match its header");
    const row = {};
    for (let i = 0; i < headers.length; i += 1) {
      row[headers[i]] = rawRow[i] ?? "";
    }

    const hasData = Object.values(row).some((value) => String(value).trim() !== "");
    if (hasData) {
      records.push(row);
    }
  }

  return { headers, records };
}

function chunk(items, size) {
  const output = [];
  for (let i = 0; i < items.length; i += size) {
    output.push(items.slice(i, i + size));
  }
  return output;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function validateInput(headers, rows, keys, clearFields = []) {
  if (!keys.length || new Set(keys).size !== keys.length) fail("Merge keys must be nonempty and unique");
  const forbidden = CONTRACT.filter(field => !field.upload).map(field => field.name);
  for (const header of headers) {
    if (forbidden.includes(header)) fail(`Omit protected field ${header}; attachments use their dedicated helper`);
  }
  for (const key of keys) {
    if (!headers.includes(key)) fail(`CSV is missing merge key ${key}`);
    if (clearFields.includes(key)) fail(`Merge key ${key} cannot be cleared`);
  }
  for (const field of clearFields) {
    if (!headers.includes(field)) fail(`Clear field ${field} is absent from the CSV`);
  }
  const seen = new Set();
  for (const row of rows) {
    const values = keys.map(key => row[key]);
    if (values.some(value => typeof value !== "string" || !value.trim())) fail("Merge keys must be nonblank text");
    const signature = JSON.stringify(values);
    if (seen.has(signature)) fail("Duplicate merge key in input");
    seen.add(signature);
  }
  if (!rows.length) fail("CSV has no data rows");
}

export function prepareFieldPayload(row, headers, fieldMap, clearFields = []) {
  const fields = {};
  for (const header of headers) {
    const contract = CONTRACT.find(field => field.name === header);
    const field = fieldMap.get(header);
    if (!field) fail(`Missing field metadata for ${header}`);
    if (contract?.upload === false || field.type === "multipleAttachments") fail(`Omit protected field ${header}`);
    if (contract && !contract.acceptedTypes.includes(field.type)) fail(`Unexpected ${header} type: ${field.type}`);
    const value = row[header] ?? "";
    if (typeof value !== "string") fail(`CSV value for ${header} must be text`);
    const trimmed = value.trim();
    if (header === "Id" && !trimmed) fail("Id must be nonblank text");
    if (!trimmed) {
      if (clearFields.includes(header)) fields[header] = field.type === "multipleSelects" ? [] : field.type === "checkbox" ? false : null;
      continue;
    }
    if (field.type === "number") {
      if (!Number.isFinite(Number(trimmed))) fail(`Invalid number for ${header}`);
      fields[header] = Number(trimmed);
    } else if (field.type === "checkbox") {
      const normalized = trimmed.toLowerCase();
      if (![...CONTRACT_DATA.booleans.true, ...CONTRACT_DATA.booleans.false].includes(normalized)) fail(`Invalid checkbox for ${header}`);
      fields[header] = CONTRACT_DATA.booleans.true.includes(normalized);
    } else if (field.type === "multipleSelects") {
      fields[header] = trimmed.split(/[;,]/).map(name => name.trim()).filter(Boolean);
    } else if (["singleLineText", "multilineText", "richText", "singleSelect", "url", "email", "phoneNumber"].includes(field.type)) {
      fields[header] = value;
    } else {
      fail(`Unsupported writable field type ${field.type} for ${header}`);
    }
    if (["singleSelect", "multipleSelects"].includes(field.type) && field.options?.choices) {
      const valid = new Set(field.options.choices.map(choice => choice.name));
      const selected = Array.isArray(fields[header]) ? fields[header] : [fields[header]];
      if (selected.some(choice => !valid.has(choice))) fail(`Unknown select choice for ${header}`);
    }
  }
  return fields;
}

export function validateSchema(table, headers, mergeFields) {
  const fields = new Map((table.fields || []).map(field => [field.name, field]));
  for (const header of headers) {
    if (!fields.has(header)) fail(`CSV field not found in Airtable schema: ${header}`);
    const contract = CONTRACT.find(field => field.name === header);
    if (contract && !contract.acceptedTypes.includes(fields.get(header).type)) fail(`Unexpected ${header} type: ${fields.get(header).type}`);
  }
  for (const key of mergeFields) {
    if (!headers.includes(key)) fail(`CSV is missing merge key ${key}`);
    if (!fields.has(key)) fail(`Merge field not found in Airtable schema: ${key}`);
    if (fields.get(key).type !== "singleLineText") fail(`Merge key ${key} must be singleLineText`);
  }
  return fields;
}

export async function main() {
  const token = process.env.AIRTABLE_TOKEN;
  let baseId = arg("base");
  let tableId = arg("table");
  const rawUrl = arg("url");
  if (rawUrl) {
    const parsed = parseAirtableUrl(rawUrl);
    if ((baseId && baseId !== parsed.baseId) || (tableId && tableId !== parsed.tableId)) fail("Conflicting Airtable targets");
    baseId = parsed.baseId;
    tableId = parsed.tableId;
  }
  if (!baseId || !tableId) fail("Required: --url or --base and --table");
  const csvPath = arg("csv");
  if (!csvPath) fail("Required: --csv");
  const recordIdColumn = arg("record-id-column");
  const keys = recordIdColumn ? [recordIdColumn] : String(arg("merge-fields", "Id")).split(",").map(s => s.trim()).filter(Boolean);
  const clearFields = String(arg("clear-fields", "")).split(",").map(s => s.trim()).filter(Boolean);
  const {headers: inputHeaders, records: rows} = await loadCsvRows(csvPath);
  validateInput(inputHeaders, rows, keys, clearFields);
  if (recordIdColumn && rows.some(row => !/^rec[a-zA-Z0-9]+$/.test(row[recordIdColumn]))) fail("Invalid Airtable record id");
  const headers = inputHeaders.filter(header => header !== recordIdColumn);
  if (!headers.some(header => !keys.includes(header))) fail("No changed fields in the CSV");
  const batchSize = parsePositiveInt(arg("batch-size", String(DEFAULT_BATCH_SIZE)), "batch-size");
  const throttleMs = parsePositiveInt(arg("throttle-ms", String(DEFAULT_THROTTLE_MS)), "throttle-ms");
  const limit = arg("limit") ? parsePositiveInt(arg("limit"), "limit") : rows.length;
  const execute = hasFlag("execute");
  const boundaryPath = arg("boundary");
  let table;
  if (boundaryPath) {
    const boundary = JSON.parse(await fs.readFile(boundaryPath, "utf8"));
    if (boundary.version !== 1 || boundary.baseId !== baseId || boundary.table?.id !== tableId) fail("Saved boundary does not match the requested target");
    table = boundary.table;
  } else {
    if (!token) fail("Missing AIRTABLE_TOKEN for schema inspection");
    const schema = await fetchBaseSchema(baseId, token);
    table = schema.tables?.find(item => item.id === tableId || item.name === tableId);
  }
  if (!table) fail("Table not found in base schema");
  const fieldMap = validateSchema(table, headers, recordIdColumn ? [] : keys);
  const payloadRows = rows.slice(0, limit).map(row => ({
    ...(recordIdColumn ? {id: row[recordIdColumn]} : {}),
    fields: prepareFieldPayload(row, headers, fieldMap, clearFields),
  })).filter(row => Object.keys(row.fields).some(field => recordIdColumn || !keys.includes(field)));
  const apiBatches = chunk(payloadRows, batchSize).flatMap(work => chunk(work, API_RECORDS_PER_REQUEST));
  if (!execute) {
    console.log(JSON.stringify({mode: "dry-run", rows: payloadRows.length, requests: apiBatches.length, operation: recordIdColumn ? "update" : "upsert"}));
    return;
  }
  if (!token) fail("Missing AIRTABLE_TOKEN in environment");
  let created = 0, updated = 0;
  for (const [index, records] of apiBatches.entries()) {
    const response = await fetchJson(`${API_ROOT}/${baseId}/${encodeURIComponent(table.id)}`, token, {
      method: "PATCH", body: {
        ...(!recordIdColumn ? {performUpsert: {fieldsToMergeOn: keys}} : {}), records,
      },
    });
    if (!Array.isArray(response.records) || response.records.length !== records.length) fail("Surprising Airtable response; stop and inspect the affected rows");
    created += response.createdRecords?.length || 0;
    updated += recordIdColumn ? response.records.length : response.updatedRecords?.length || 0;
    if ((index + 1) % 5 === 0 || index + 1 === apiBatches.length) console.error(`Uploaded ${Math.min((index + 1) * 10, payloadRows.length)}/${payloadRows.length} rows`);
    if (index + 1 < apiBatches.length) await sleep(throttleMs);
  }
  console.log(JSON.stringify({mode: "execute", created, updated, requests: apiBatches.length, rows: payloadRows.length}));
}

if (isMain(import.meta.url)) main().catch(error => {
  console.error(String(error.message || error));
  process.exitCode = 1;
});
