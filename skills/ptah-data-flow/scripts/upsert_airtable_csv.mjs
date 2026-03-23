#!/usr/bin/env node

// Usage:
//   AIRTABLE_TOKEN=pat... node upsert_airtable_csv.mjs \
//     --url "https://airtable.com/app.../tbl.../viw...?blocks=hide" \
//     --csv /abs/path/to/entities.airtable.csv
//
// Notes:
// - Dry-run by default. Add --execute to send requests.
// - Uses PATCH + performUpsert with batches of up to 10 records.
// - Uses Airtable field names from the CSV header.

import fs from "node:fs/promises";
import path from "node:path";

const API_ROOT = "https://api.airtable.com/v0";
const DEFAULT_BATCH_SIZE = 10;
const DEFAULT_THROTTLE_MS = 250;

function arg(name, fallback = null) {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 ? process.argv[index + 1] : fallback;
}

function hasFlag(name) {
  return process.argv.includes(`--${name}`);
}

function fail(message) {
  console.error(message);
  process.exit(1);
}

function parsePositiveInt(value, label) {
  const parsed = Number.parseInt(String(value), 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    fail(`${label} must be a positive integer. Received: ${value}`);
  }
  return parsed;
}

function parseAirtableUrl(rawUrl) {
  const url = new URL(rawUrl);
  const match = url.pathname.match(
    /^\/(?<base>app[a-zA-Z0-9]+)\/(?<table>tbl[a-zA-Z0-9]+)(?:\/(?<view>viw[a-zA-Z0-9]+))?\/?$/
  );

  if (!match?.groups?.base || !match?.groups?.table) {
    throw new Error(`Could not parse Airtable base/table IDs from URL: ${rawUrl}`);
  }

  return {
    baseId: match.groups.base,
    tableId: match.groups.table,
  };
}

async function fetchJson(url, token, { method = "GET", body = null } = {}) {
  const res = await fetch(url, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });

  const text = await res.text();
  let data = null;

  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!res.ok) {
    const detail = typeof data === "string" ? data : JSON.stringify(data, null, 2);
    throw new Error(`${res.status} ${res.statusText}\n${detail}`);
  }

  return data;
}

async function fetchBaseSchema(baseId, token) {
  const url = `${API_ROOT}/meta/bases/${baseId}/tables`;
  return fetchJson(url, token);
}

function parseCsv(text) {
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

async function loadCsvRows(csvPath) {
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

function prepareFieldPayload(row, headers, fieldMap) {
  const fields = {};

  for (const header of headers) {
    if (header === "Updated At") {
      continue;
    }

    const value = String(row[header] ?? "");
    const trimmed = value.trim();
    const field = fieldMap.get(header);

    if (!field) {
      fail(`Missing field metadata for CSV header: ${header}`);
    }

    if (field.type === "number") {
      if (trimmed === "") {
        fields[header] = null;
        continue;
      }

      const numericValue = Number(trimmed);
      if (!Number.isFinite(numericValue)) {
        fail(`Invalid numeric value for field "${header}" in row Name="${row.Name || ""}": ${value}`);
      }
      fields[header] = numericValue;
      continue;
    }

    fields[header] = trimmed === "" ? null : value;
  }

  return fields;
}

function validateSchema(table, headers, mergeFields) {
  const tableFieldNames = new Set((table.fields || []).map((field) => field.name));

  for (const header of headers) {
    if (!tableFieldNames.has(header)) {
      fail(`CSV field not found in Airtable schema: ${header}`);
    }
  }

  for (const mergeField of mergeFields) {
    if (!tableFieldNames.has(mergeField)) {
      fail(`Merge field not found in Airtable schema: ${mergeField}`);
    }
  }

  return new Map((table.fields || []).map((field) => [field.name, field]));
}

async function main() {
  const token = process.env.AIRTABLE_TOKEN;
  if (!token) {
    fail("Missing AIRTABLE_TOKEN in environment.");
  }

  let baseId = arg("base");
  let tableId = arg("table");
  const rawUrl = arg("url");
  const csvArg = arg("csv");
  if (!csvArg) {
    fail("Required: --csv /abs/path/to/file.csv");
  }
  const csvPath = path.resolve(csvArg);
  const mergeFields = String(arg("merge-fields", "Id"))
    .split(",")
    .map((field) => field.trim())
    .filter(Boolean);
  const batchSize = parsePositiveInt(arg("batch-size", String(DEFAULT_BATCH_SIZE)), "batch-size");
  const throttleMs = parsePositiveInt(arg("throttle-ms", String(DEFAULT_THROTTLE_MS)), "throttle-ms");
  const limitArg = arg("limit");
  const limit = limitArg ? parsePositiveInt(limitArg, "limit") : null;
  const execute = hasFlag("execute");

  if (batchSize > 10) {
    fail("batch-size cannot exceed 10 for Airtable record batch endpoints.");
  }

  if (rawUrl) {
    const parsed = parseAirtableUrl(rawUrl);
    baseId ||= parsed.baseId;
    tableId ||= parsed.tableId;
  }

  if (!baseId || !tableId) {
    fail("Required: --url airtable_url or --base app... --table tbl...");
  }

  let schemaData;
  try {
    schemaData = await fetchBaseSchema(baseId, token);
  } catch (error) {
    fail(
      [
        "Failed to fetch base schema from Airtable Metadata API.",
        "Check AIRTABLE_TOKEN permissions and confirm it includes `schema.bases:read` for this base.",
        "",
        String(error.message || error),
      ].join("\n")
    );
  }

  const table = schemaData.tables?.find(
    (item) => item.id === tableId || item.name === tableId
  );
  if (!table) {
    fail(`Table not found in base schema: ${tableId}`);
  }

  const { headers, records: csvRows } = await loadCsvRows(csvPath);
  const fieldMap = validateSchema(table, headers, mergeFields);

  const limitedRows = limit ? csvRows.slice(0, limit) : csvRows;
  const payloadRows = limitedRows.map((row) => prepareFieldPayload(row, headers, fieldMap));
  const batches = chunk(payloadRows, batchSize);

  console.log(`Base: ${baseId}`);
  console.log(`Table: ${table.name} (${table.id})`);
  console.log(`CSV: ${csvPath}`);
  console.log(`Rows: ${payloadRows.length}`);
  console.log(`Merge fields: ${mergeFields.join(", ")}`);
  console.log(`Batch size: ${batchSize}`);
  console.log(`Estimated API requests: ${batches.length}`);
  console.log(`Throttle: ${throttleMs}ms`);
  console.log(`Mode: ${execute ? "execute" : "dry-run"}`);

  if (!execute) {
    console.log("");
    console.log("Dry-run only. Add --execute to send PATCH requests with performUpsert.");
    return;
  }

  const endpoint = `${API_ROOT}/${baseId}/${encodeURIComponent(table.id)}`;
  let created = 0;
  let updated = 0;

  for (let index = 0; index < batches.length; index += 1) {
    const batch = batches[index];
    const response = await fetchJson(endpoint, token, {
      method: "PATCH",
      body: {
        performUpsert: {
          fieldsToMergeOn: mergeFields,
        },
        records: batch.map((fields) => ({ fields })),
      },
    });

    created += Array.isArray(response.createdRecords) ? response.createdRecords.length : 0;
    updated += Array.isArray(response.updatedRecords) ? response.updatedRecords.length : 0;

    console.log(
      `Batch ${index + 1}/${batches.length}: created=${Array.isArray(response.createdRecords) ? response.createdRecords.length : 0} updated=${Array.isArray(response.updatedRecords) ? response.updatedRecords.length : 0}`
    );

    if (index < batches.length - 1) {
      await sleep(throttleMs);
    }
  }

  console.log("");
  console.log(`Done. created=${created} updated=${updated} total=${created + updated}`);
}

main().catch((error) => {
  fail(String(error.message || error));
});
