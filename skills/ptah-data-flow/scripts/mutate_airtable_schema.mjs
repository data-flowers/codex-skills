#!/usr/bin/env node

// Usage:
//   AIRTABLE_TOKEN=pat... node mutate_airtable_schema.mjs plan --url "https://airtable.com/app.../tbl.../viw...?blocks=hide"
//   AIRTABLE_TOKEN=pat... node mutate_airtable_schema.mjs apply --url "https://airtable.com/app.../tbl.../viw...?blocks=hide"
//   AIRTABLE_TOKEN=pat... node mutate_airtable_schema.mjs plan --url "..." --json

const API_ROOT = "https://api.airtable.com/v0";

const CONTRACT = [
  { name: "Id", createType: "singleLineText", createOptions: null },
  { name: "Category", createType: "singleLineText", createOptions: null },
  { name: "Subcategory", createType: "singleLineText", createOptions: null },
  { name: "Name", createType: "singleLineText", createOptions: null },
  { name: "Website", createType: "url", createOptions: null },
  { name: "Logo", createType: "url", createOptions: null },
  { name: "Description", createType: "multilineText", createOptions: null },
  { name: "Year Founded", createType: "singleLineText", createOptions: null },
  { name: "Email", createType: "singleLineText", createOptions: null },
  { name: "Tech Capabilities", createType: "multilineText", createOptions: null },
  { name: "Updated At", createType: null, createOptions: null },
  { name: "AI Context", createType: "multilineText", createOptions: null },
];

function fail(message) {
  console.error(message);
  process.exit(1);
}

function arg(name, fallback = null) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : fallback;
}

function hasFlag(name) {
  return process.argv.includes(`--${name}`);
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

async function fetchJson(url, token, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  const text = await response.text();
  let data = null;

  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!response.ok) {
    const detail = typeof data === "string" ? data : JSON.stringify(data, null, 2);
    throw new Error(`${response.status} ${response.statusText}\n${detail}`);
  }

  return data;
}

async function fetchBaseSchema(baseId, token) {
  return fetchJson(`${API_ROOT}/meta/bases/${baseId}/tables`, token);
}

async function updateField(baseId, tableId, fieldId, body, token) {
  return fetchJson(`${API_ROOT}/meta/bases/${baseId}/tables/${tableId}/fields/${fieldId}`, token, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

async function createField(baseId, tableId, body, token) {
  return fetchJson(`${API_ROOT}/meta/bases/${baseId}/tables/${tableId}/fields`, token, {
    method: "POST",
    body: JSON.stringify(body),
  });
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

function buildPlan(table) {
  const actions = [];
  const notes = [];
  const { exact, normalized } = buildFieldMaps(table.fields || []);

  for (const expected of CONTRACT) {
    const exactField = exact.get(expected.name) || null;
    const normalizedField = normalized.get(expected.name) || null;
    const field = exactField || normalizedField;

    if (!exactField && normalizedField) {
      actions.push({
        kind: "rename_field",
        fieldId: normalizedField.id,
        from: normalizedField.name,
        to: expected.name,
        issues: describeNameIssue(normalizedField.name, expected.name),
      });
    }

    if (!field) {
      if (expected.createType) {
        actions.push({
          kind: "create_field",
          name: expected.name,
          fieldType: expected.createType,
          options: expected.createOptions,
        });
      } else {
        notes.push({
          kind: "missing_field",
          field: expected.name,
          message: `Missing field "${expected.name}" still needs manual repair.`,
        });
      }
      continue;
    }

  }

  return { actions, notes };
}

async function loadTarget({ rawUrl, baseId, tableId, viewId, token }) {
  let resolvedBaseId = baseId;
  let resolvedTableId = tableId;
  let resolvedViewId = viewId;

  if (rawUrl) {
    const parsed = parseAirtableUrl(rawUrl);
    resolvedBaseId ||= parsed.baseId;
    resolvedTableId ||= parsed.tableId;
    resolvedViewId ||= parsed.viewId;
  }

  if (!resolvedBaseId || !resolvedTableId) {
    fail("Required: --url airtable_url or --base app... --table tbl...");
  }

  let schemaData;
  try {
    schemaData = await fetchBaseSchema(resolvedBaseId, token);
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
    (item) => item.id === resolvedTableId || item.name === resolvedTableId
  );
  if (!table) {
    fail(`Table not found in base schema: ${resolvedTableId}`);
  }

  const view = resolvedViewId
    ? table.views?.find((item) => item.id === resolvedViewId || item.name === resolvedViewId) || null
    : null;
  if (resolvedViewId && !view) {
    fail(`View not found in table schema: ${resolvedViewId}`);
  }

  return {
    source: rawUrl || null,
    baseId: resolvedBaseId,
    table,
    view,
  };
}

async function applyPlan(target, plan, token) {
  const results = [];

  for (const action of plan.actions) {
    if (action.kind === "rename_field") {
      const response = await updateField(target.baseId, target.table.id, action.fieldId, { name: action.to }, token);
      results.push({
        kind: action.kind,
        from: action.from,
        to: action.to,
        fieldId: action.fieldId,
        response,
      });
      continue;
    }

    if (action.kind === "create_field") {
      const body = {
        name: action.name,
        type: action.fieldType,
        ...(action.options ? { options: action.options } : {}),
      };
      const response = await createField(target.baseId, target.table.id, body, token);
      results.push({
        kind: action.kind,
        name: action.name,
        fieldType: action.fieldType,
        response,
      });
      continue;
    }

  }

  return results;
}

function printHuman(target, plan, applyResults = null) {
  const tableLabel = `${target.table.name} (${target.table.id})`;
  console.log(`Base: ${target.baseId}`);
  console.log(`Table: ${tableLabel}`);
  if (target.view) {
    console.log(`View: ${target.view.name} (${target.view.id})`);
  }
  console.log("");

  if (!plan.actions.length) {
    console.log("No schema repairs planned.");
  } else {
    console.log("Planned repairs:");
    for (const action of plan.actions) {
      if (action.kind === "rename_field") {
        const suffix = action.issues?.length ? ` [${action.issues.join(", ")}]` : "";
        console.log(`- rename field: ${action.from} -> ${action.to}${suffix}`);
      } else if (action.kind === "create_field") {
        console.log(`- create field: ${action.name} [${action.fieldType}]`);
      }
    }
  }

  if (plan.notes.length) {
    console.log("");
    console.log("Still needs manual repair:");
    for (const note of plan.notes) {
      console.log(`- ${note.message}`);
    }
  }

  if (applyResults) {
    console.log("");
    console.log("Applied repairs:");
    for (const item of applyResults) {
      if (item.kind === "rename_field") {
        console.log(`- renamed ${item.from} -> ${item.to}`);
      } else if (item.kind === "create_field") {
        console.log(`- created ${item.name} [${item.fieldType}]`);
      }
    }
  }
}

async function main() {
  const command = process.argv[2];
  if (!command || !["plan", "apply"].includes(command)) {
    fail("Usage: mutate_airtable_schema.mjs <plan|apply> [--url ... | --base app... --table tbl...] [--json]");
  }

  const token = process.env.AIRTABLE_TOKEN;
  if (!token) {
    fail("Missing AIRTABLE_TOKEN in environment.");
  }

  const rawUrl = arg("url");
  const baseId = arg("base");
  const tableId = arg("table");
  const viewId = arg("view");
  const asJson = hasFlag("json");

  const target = await loadTarget({ rawUrl, baseId, tableId, viewId, token });
  const plan = buildPlan(target.table);

  let applyResults = null;
  if (command === "apply" && plan.actions.length) {
    try {
      applyResults = await applyPlan(target, plan, token);
    } catch (error) {
      fail(
        [
          "Failed to apply Airtable schema repair.",
          "Check that the token includes `schema.bases:write` and has access to this base.",
          "",
          String(error.message || error),
        ].join("\n")
      );
    }
  }

  const refreshedTarget = command === "apply" ? await loadTarget({ rawUrl, baseId, tableId, viewId, token }) : target;
  const refreshedPlan = buildPlan(refreshedTarget.table);

  const result = {
    source: refreshedTarget.source,
    base: { id: refreshedTarget.baseId },
    table: {
      id: refreshedTarget.table.id,
      name: refreshedTarget.table.name,
    },
    view: refreshedTarget.view
      ? {
          id: refreshedTarget.view.id,
          name: refreshedTarget.view.name,
        }
      : null,
    mode: command,
    plannedActions: plan.actions,
    notes: plan.notes,
    appliedActions: applyResults || [],
    remainingPlan: refreshedPlan.actions,
    remainingNotes: refreshedPlan.notes,
  };

  if (asJson) {
    console.log(JSON.stringify(result, null, 2));
    return;
  }

  printHuman(refreshedTarget, plan, applyResults);
  if (command === "apply") {
    console.log("");
    console.log(`Remaining repairs: ${refreshedPlan.actions.length}`);
  }
}

main().catch((error) => {
  fail(String(error.message || error));
});
