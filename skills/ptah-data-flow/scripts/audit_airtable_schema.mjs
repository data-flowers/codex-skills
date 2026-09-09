#!/usr/bin/env node
import { isMain, CONTRACT, arg, hasFlag, fail, parseAirtableUrl, fetchBaseSchema, describeNameIssue, buildFieldMaps } from "./airtable_common.mjs";

// Usage:
//   AIRTABLE_TOKEN=pat... node audit_airtable_schema.mjs --url "https://airtable.com/app.../tbl.../viw...?blocks=hide"
//   AIRTABLE_TOKEN=pat... node audit_airtable_schema.mjs --base app... --table tbl... [--view viw...]
//   AIRTABLE_TOKEN=pat... node audit_airtable_schema.mjs --url "..." --json

export function auditTable(table) {
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

    if (!expected.acceptedTypes.includes(field.type)) {
      const updatedAtGuidance = expected.name === "Updated At"
        ? " CSV import cannot create or preserve Last modified time. For a new table, provision this field natively in Airtable before row import, omit it from the upload artifact, and rerun the audit."
        : "";
      issues.push({
        code: "field_type_mismatch",
        field: expected.name,
        actualName: field.name,
        actualType: field.type,
        repairable: false,
        targetType: expected.acceptedTypes.join(" or "),
        message: `Field "${field.name}" is type "${field.type}". Expected: ${expected.acceptedTypes.join(" or ")}.${updatedAtGuidance}`,
      });
    }
  }

  return {
    status: issues.length > 0 ? "blocked" : "clean",
    issues,
  };
}

export async function main() {
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
    return audit.issues.length ? 2 : 0;
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
    return 0;
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
  return 2;
}

if (isMain(import.meta.url)) main().then(code => { process.exitCode = code; }).catch((error) => {
  console.error(String(error.message || error));
  process.exitCode = 1;
});
