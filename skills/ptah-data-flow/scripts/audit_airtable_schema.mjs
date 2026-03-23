#!/usr/bin/env node

// Usage:
//   AIRTABLE_TOKEN=pat... node audit_airtable_schema.mjs --url "https://airtable.com/app.../tbl.../viw...?blocks=hide"
//   AIRTABLE_TOKEN=pat... node audit_airtable_schema.mjs --base app... --table tbl... [--view viw...]
//   AIRTABLE_TOKEN=pat... node audit_airtable_schema.mjs --url "..." --json

const API_ROOT = "https://api.airtable.com/v0";

const CONTRACT = [
  { name: "Id", createType: "singleLineText" },
  { name: "Category", createType: "singleLineText" },
  { name: "Subcategory", createType: "singleLineText" },
  { name: "Name", createType: "singleLineText" },
  { name: "Website", createType: "url" },
  { name: "Logo", createType: "url" },
  { name: "Description", createType: "multilineText" },
  { name: "Year Founded", createType: "singleLineText" },
  { name: "Email", createType: "singleLineText" },
  { name: "Tech Capabilities", createType: "multilineText" },
  { name: "Updated At", requiredType: "lastModifiedTime", createType: null },
  { name: "AI Context", createType: "multilineText" },
];

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
  return fetchJson(`${API_ROOT}/meta/bases/${baseId}/tables`, token);
}

function normalizeName(name) {
  return String(name ?? "")
    .replace(/^\ufeff/, "")
    .trim();
}

function describeNameIssue(actualName, expectedName) {
  const issues = [];
  if (String(actualName).startsWith("\ufeff")) {
    issues.push("leading BOM");
  }
  if (String(actualName) !== String(actualName).trim()) {
    issues.push("leading or trailing whitespace");
  }
  if (normalizeName(actualName) === expectedName && issues.length === 0 && actualName !== expectedName) {
    issues.push("invisible name mismatch");
  }
  return issues;
}

function buildFieldMaps(fields) {
  const exact = new Map();
  const normalized = new Map();

  for (const field of fields) {
    exact.set(field.name, field);
    normalized.set(normalizeName(field.name), field);
  }

  return { exact, normalized };
}

function auditTable(table) {
  const issues = [];
  const { exact, normalized } = buildFieldMaps(table.fields || []);

  for (const expected of CONTRACT) {
    const exactField = exact.get(expected.name) || null;
    const normalizedField = normalized.get(expected.name) || null;

    if (!exactField && !normalizedField) {
      issues.push({
        code: "missing_field",
        field: expected.name,
        repairable: Boolean(expected.createType),
        message: `Missing required field: ${expected.name}`,
      });
      continue;
    }

    const field = exactField || normalizedField;

    if (!exactField && normalizedField) {
      issues.push({
        code: "field_name_pollution",
        field: expected.name,
        actualName: normalizedField.name,
        repairable: true,
        message: `Field "${normalizedField.name}" should be exactly "${expected.name}".`,
        details: describeNameIssue(normalizedField.name, expected.name),
      });
    }

    if (expected.requiredType && field.type !== expected.requiredType) {
      issues.push({
        code: "field_type_mismatch",
        field: expected.name,
        actualName: field.name,
        actualType: field.type,
        repairable: false,
        targetType: expected.requiredType,
        message: `Field "${field.name}" is type "${field.type}". Expected: ${expected.requiredType}.`,
      });
    }
  }

  return {
    status: issues.length > 0 ? "blocked" : "clean",
    issues,
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

  const audit = auditTable(table);
  const result = {
    source: rawUrl || null,
    base: { id: baseId },
    table: {
      id: table.id,
      name: table.name,
      fields: (table.fields || []).map((field) => ({
        id: field.id,
        name: field.name,
        type: field.type,
      })),
    },
    view: view
      ? {
          id: view.id,
          name: view.name,
          type: view.type,
        }
      : null,
    audit,
  };

  if (asJson) {
    console.log(JSON.stringify(result, null, 2));
    return;
  }

  console.log(`Base: ${result.base.id}`);
  console.log(`Table: ${result.table.name} (${result.table.id})`);
  if (result.view) {
    console.log(`View: ${result.view.name} (${result.view.id})`);
  }
  console.log(`Status: ${audit.status}`);
  console.log("");

  if (audit.issues.length === 0) {
    console.log("Schema matches the Ptah contract cleanly.");
    return;
  }

  console.log("Issues:");
  for (const issue of audit.issues) {
    const line = ["-", issue.message];
    if (!issue.repairable) {
      line.push("(manual follow-up)");
    }
    if (issue.code) {
      line.push(`{${issue.code}}`);
    }
    console.log(line.join(" "));
  }
}

main().catch((error) => {
  fail(String(error.message || error));
});
