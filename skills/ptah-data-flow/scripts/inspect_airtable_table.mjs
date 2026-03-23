#!/usr/bin/env node

// Usage:
//   AIRTABLE_TOKEN=pat... node inspect_airtable_table.mjs --url "https://airtable.com/app.../tbl.../viw...?blocks=hide"
//   AIRTABLE_TOKEN=pat... node inspect_airtable_table.mjs --base app... --table tbl... [--view viw...]
//   AIRTABLE_TOKEN=pat... node inspect_airtable_table.mjs --url "..." --json

const API_ROOT = "https://api.airtable.com/v0";

function arg(name, fallback = null) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : fallback;
}

function hasFlag(name) {
  return process.argv.includes(`--${name}`);
}

function fail(message) {
  console.error(message);
  process.exit(1);
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
    viewId: match.groups.view || null,
  };
}

async function fetchJson(url, token) {
  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
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

async function countRecords(baseId, tableId, viewId, token) {
  let offset = null;
  let total = 0;

  do {
    const url = new URL(`${API_ROOT}/${baseId}/${encodeURIComponent(tableId)}`);
    url.searchParams.set("pageSize", "100");
    if (viewId) {
      url.searchParams.set("view", viewId);
    }
    if (offset) {
      url.searchParams.set("offset", offset);
    }

    const data = await fetchJson(url.toString(), token);
    total += Array.isArray(data.records) ? data.records.length : 0;
    offset = data.offset || null;
  } while (offset);

  return total;
}

function formatField(field) {
  return {
    id: field.id,
    name: field.name,
    type: field.type,
    ...(field.options ? { options: field.options } : {}),
  };
}

async function main() {
  const token = process.env.AIRTABLE_TOKEN;
  if (!token) {
    fail("Missing AIRTABLE_TOKEN in environment.");
  }

  let baseId = arg("base");
  let tableId = arg("table");
  let viewId = arg("view");
  const rawUrl = arg("url");
  const asJson = hasFlag("json");

  if (rawUrl) {
    const parsed = parseAirtableUrl(rawUrl);
    baseId ||= parsed.baseId;
    tableId ||= parsed.tableId;
    viewId ||= parsed.viewId;
  }

  if (!baseId || !tableId) {
    fail("Required: --url airtable_url or --base app... --table tbl... [--view viw...]");
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

  const view = viewId
    ? table.views?.find((item) => item.id === viewId || item.name === viewId) || null
    : null;
  if (viewId && !view) {
    fail(`View not found in table schema: ${viewId}`);
  }

  const recordCount = await countRecords(baseId, table.id, view?.id || null, token);

  const result = {
    source: rawUrl || null,
    base: { id: baseId },
    table: {
      id: table.id,
      name: table.name,
      primaryFieldId: table.primaryFieldId,
      fieldCount: Array.isArray(table.fields) ? table.fields.length : 0,
      fields: Array.isArray(table.fields) ? table.fields.map(formatField) : [],
    },
    view: viewId
      ? {
          id: view.id,
          name: view.name,
          type: view.type,
        }
      : null,
    records: {
      count: recordCount,
      isEmpty: recordCount === 0,
      scopedToView: Boolean(viewId),
    },
  };

  if (asJson) {
    console.log(JSON.stringify(result, null, 2));
    return;
  }

  console.log(`Base: ${result.base.id}`);
  const tableLabel = result.table.name ? `${result.table.name} (${result.table.id})` : result.table.id;
  console.log(`Table: ${tableLabel}`);
  if (result.view) {
    const viewName = result.view.name ? `${result.view.name} ` : "";
    console.log(`View: ${viewName}(${result.view.id})`);
  }
  console.log(`Records: ${result.records.count}`);
  console.log(`Empty: ${result.records.isEmpty ? "yes" : "no"}`);
  console.log("");
  console.log("Schema:");
  for (const field of result.table.fields) {
    console.log(`- ${field.name} [${field.type}] (${field.id})`);
  }
}

main().catch((error) => {
  fail(String(error.message || error));
});
