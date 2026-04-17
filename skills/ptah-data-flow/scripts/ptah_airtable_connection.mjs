#!/usr/bin/env node

// Usage:
//   node ptah_airtable_connection.mjs test --origin http://localhost:3000 --payload ./connection.json
//   node ptah_airtable_connection.mjs save --origin http://localhost:3000 --payload ./connection.json
//   node ptah_airtable_connection.mjs save --origin http://localhost:3000 \
//     --name "Example Directory" --base-id app... --table-name "Entities" --view "Grid view" \
//     --last-modified-field "Updated At" --description "Example entity directory"
//
// Notes:
// - Supported commands: test, save.
// - Save always creates via POST /airtable-admin.
// - If --payload is omitted, the script builds the same shape the Ptah admin form sends.

import fs from "node:fs";
import path from "node:path";

function fail(message) {
  console.error(message);
  process.exit(1);
}

function hasFlag(name) {
  return process.argv.includes(`--${name}`);
}

function arg(name, fallback = null) {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 ? process.argv[index + 1] : fallback;
}

function parseJsonArg(name) {
  const raw = arg(name);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw);
  } catch (error) {
    fail(`Invalid JSON for --${name}: ${String(error.message || error)}`);
  }
}

function readJsonFile(filePath) {
  try {
    const raw = fs.readFileSync(filePath, "utf8");
    return JSON.parse(raw);
  } catch (error) {
    fail(`Failed to read JSON payload from ${filePath}: ${String(error.message || error)}`);
  }
}

function maybeInt(name) {
  const raw = arg(name);
  if (!raw) {
    return undefined;
  }

  const value = Number.parseInt(raw, 10);
  if (!Number.isFinite(value)) {
    fail(`Invalid integer for --${name}: ${raw}`);
  }
  return value;
}

function isoNow() {
  return new Date().toISOString();
}

function maybeTrim(raw) {
  if (typeof raw !== "string") {
    return "";
  }
  return raw.trim();
}

function buildAdmins() {
  const jsonAdmins = parseJsonArg("admins-json");
  if (jsonAdmins) {
    if (!Array.isArray(jsonAdmins)) {
      fail("--admins-json must be a JSON array");
    }
    return jsonAdmins;
  }

  const admins = [];
  for (let i = 1; i <= 3; i += 1) {
    const name = maybeTrim(arg(`admin${i}-name`));
    const title = maybeTrim(arg(`admin${i}-title`));
    const url = maybeTrim(arg(`admin${i}-url`));
    const avatarUrl = maybeTrim(arg(`admin${i}-avatar`));

    if (!name && !title && !url && !avatarUrl) {
      continue;
    }

    admins.push({
      ...(name ? { name } : {}),
      ...(title ? { title } : {}),
      ...(url ? { url } : {}),
      ...(avatarUrl ? { avatarUrl } : {}),
    });
  }

  return admins;
}

function buildPayloadFromArgs() {
  const name = maybeTrim(arg("name"));
  const baseId = maybeTrim(arg("base-id"));
  const tableName = maybeTrim(arg("table-name"));
  const view = maybeTrim(arg("view"));
  const lastModifiedField = maybeTrim(arg("last-modified-field"));
  const title = maybeTrim(arg("title")) || name;
  const logoUrl = maybeTrim(arg("logo-url"));
  const description = maybeTrim(arg("description"));
  const id = maybeTrim(arg("id"));
  const createdAt = maybeTrim(arg("created-at"));
  const admins = buildAdmins();

  if (!name) {
    fail("Missing required --name when --payload is not provided.");
  }
  if (!baseId) {
    fail("Missing required --base-id when --payload is not provided.");
  }
  if (!tableName) {
    fail("Missing required --table-name when --payload is not provided.");
  }

  const layoutOverrides = {
    categoryColumnsMin: maybeInt("category-columns-min"),
    categoryColumnsMax: maybeInt("category-columns-max"),
    subColumnsMin: maybeInt("sub-columns-min"),
    subColumnsMax: maybeInt("sub-columns-max"),
  };

  const now = isoNow();
  return {
    id: id || crypto.randomUUID(),
    name,
    baseId,
    tableName,
    ...(view ? { view } : {}),
    fieldMap: {},
    layoutOverrides,
    mapInfo: {
      title,
      ...(logoUrl ? { logoUrl } : {}),
      ...(description ? { description } : {}),
      ...(admins.length ? { admins, admin: admins[0] } : {}),
    },
    ...(lastModifiedField ? { lastModifiedField } : {}),
    createdAt: createdAt || now,
    updatedAt: now,
  };
}

function buildPayload() {
  const payloadPath = arg("payload");
  if (payloadPath) {
    const resolved = path.resolve(payloadPath);
    return readJsonFile(resolved);
  }

  return buildPayloadFromArgs();
}

function resolveOrigin() {
  const origin = arg("origin") || process.env.PTAH_ADMIN_ORIGIN || process.env.PTAH_ORIGIN;
  if (!origin) {
    fail("Missing Ptah admin origin. Use --origin http://host:port or set PTAH_ADMIN_ORIGIN.");
  }
  return origin.replace(/\/+$/, "");
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
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

async function main() {
  const command = process.argv[2];
  if (!command || !["test", "save"].includes(command)) {
    fail("Usage: ptah_airtable_connection.mjs <test|save> [--origin ...] [--payload file.json | direct flags]");
  }

  const origin = resolveOrigin();
  const payload = buildPayload();
  let method;
  let endpoint;

  if (command === "test") {
    method = "POST";
    endpoint = "/airtable-admin/test";
  } else {
    method = "POST";
    endpoint = "/airtable-admin";
  }

  const data = await fetchJson(`${origin}${endpoint}`, {
    method,
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  console.log(JSON.stringify({
    command,
    method,
    endpoint,
    payload,
    response: data,
  }, null, 2));
}

main().catch((error) => {
  fail(String(error.message || error));
});
