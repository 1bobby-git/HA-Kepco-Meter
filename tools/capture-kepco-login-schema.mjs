#!/usr/bin/env node
import { createHash } from "node:crypto";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";
import { stdin as input, stdout as output } from "node:process";
import readline from "node:readline/promises";
import { fileURLToPath } from "node:url";

const BASE_URL = "https://online.kepco.co.kr";
const START_URL = `${BASE_URL}/MYM001D00`;
const OUTPUT_FILE = "login-schema.safe.json";
const TEMP_PROFILE_PREFIX = "kepco-login-schema-";

export const ALLOWED_ENDPOINTS = Object.freeze([
  "/cyb/me/login/indi/api",
  "/me/login/firstLogin/check",
  "/sessionCheck",
  "/ssoCheck",
]);

const SUCCESS_FAILURE_FIELD_PATTERN = /(?:^|\.)(?:result|errorCode|errorMessage|loginChk|statusCode|rsMsg)$/i;
const TOKEN_FIELD_PATTERN = /token|jwt|session|sso|authorization|auth/i;

function typeOfJson(value) {
  if (value === null) {
    return "null";
  }
  if (Array.isArray(value)) {
    return "array";
  }
  return typeof value;
}

function isPlainObject(value) {
  return Object.prototype.toString.call(value) === "[object Object]";
}

function sortedEntries(value) {
  return Object.entries(value).sort(([left], [right]) => left.localeCompare(right));
}

function jsonPathFor(parent, key) {
  if (/^[A-Za-z_$][A-Za-z0-9_$]*$/.test(key)) {
    return `${parent}.${key}`;
  }
  return `${parent}[${JSON.stringify(key)}]`;
}

function looksBase64(value) {
  return value.length >= 16 && value.length % 4 === 0 && /^[A-Za-z0-9+/]+={0,2}$/.test(value);
}

function looksHex(value) {
  return value.length >= 16 && value.length % 2 === 0 && /^[a-fA-F0-9]+$/.test(value);
}

function looksJwt(value) {
  return /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(value);
}

function stringMeta(path, value, secrets) {
  return {
    path,
    type: "string",
    length: value.length,
    matchesBase64: looksBase64(value),
    matchesHex: looksHex(value),
    matchesJwt: looksJwt(value),
    matchesPassword: value === secrets.password,
    matchesUsername: value === secrets.username,
  };
}

export function flattenJsonPaths(value, options = {}) {
  const secrets = {
    username: options.username ?? "",
    password: options.password ?? "",
  };
  const paths = [];

  function visit(current, path) {
    const type = typeOfJson(current);
    if (type === "object") {
      if (path !== "$") {
        paths.push({ path, type });
      }
      for (const [key, child] of sortedEntries(current)) {
        visit(child, jsonPathFor(path, key));
      }
      return;
    }
    if (type === "array") {
      if (path !== "$") {
        paths.push({ path, type, length: current.length });
      }
      current.forEach((child, index) => visit(child, `${path}[${index}]`));
      return;
    }
    if (type === "string") {
      paths.push(stringMeta(path, current, secrets));
      return;
    }
    if (type === "null") {
      paths.push({ path, type, isNull: true });
      return;
    }
    paths.push({ path, type });
  }

  visit(value, "$");
  return paths;
}

export function endpointFromUrl(url) {
  try {
    const parsed = new URL(url, BASE_URL);
    if (parsed.origin !== BASE_URL) {
      return null;
    }
    return parsed.pathname;
  } catch {
    return null;
  }
}

export function isAllowedEndpoint(urlOrPath) {
  const path = urlOrPath.startsWith("/") ? urlOrPath : endpointFromUrl(urlOrPath);
  return path !== null && ALLOWED_ENDPOINTS.includes(path);
}

function headerValue(headers, name) {
  const wanted = name.toLowerCase();
  for (const [key, value] of Object.entries(headers ?? {})) {
    if (key.toLowerCase() === wanted && typeof value === "string") {
      return value;
    }
  }
  return undefined;
}

function safeSubmissionId(value) {
  if (typeof value !== "string" || value === "") {
    return undefined;
  }
  if (!/^[A-Za-z0-9_.:-]{1,128}$/.test(value)) {
    return "[unsafe-format]";
  }
  return value;
}

export function summarizeRequest(request, secrets = {}) {
  const endpoint = endpointFromUrl(request.url);
  const body = isPlainObject(request.postDataJSON) || Array.isArray(request.postDataJSON)
    ? request.postDataJSON
    : {};
  return {
    endpoint,
    method: String(request.method ?? "").toUpperCase(),
    allowed: endpoint !== null && isAllowedEndpoint(endpoint),
    submissionid: safeSubmissionId(headerValue(request.headers, "submissionid")),
    bodyPaths: flattenJsonPaths(body, secrets),
  };
}

function lastPathName(path) {
  const dotIndex = path.lastIndexOf(".");
  const bracketIndex = path.lastIndexOf("[");
  const index = Math.max(dotIndex, bracketIndex);
  return path.slice(index + 1).replaceAll(/[\]"']/g, "");
}

export function summarizeResponse(response) {
  const json = isPlainObject(response.json) || Array.isArray(response.json) ? response.json : {};
  const keyPaths = flattenJsonPaths(json);
  const contentType = headerValue(response.headers, "content-type");
  return {
    status: response.status,
    contentType,
    keyPaths: keyPaths.map((item) => {
      const copy = { path: item.path, type: item.type };
      if ("length" in item) {
        copy.length = item.length;
      }
      if ("isNull" in item) {
        copy.isNull = item.isNull;
      }
      return copy;
    }),
    tokenLikeFields: keyPaths
      .filter((item) => item.type === "string" && TOKEN_FIELD_PATTERN.test(lastPathName(item.path)))
      .map((item) => ({ path: item.path, name: lastPathName(item.path), length: item.length }))
      .sort((left, right) => left.path.localeCompare(right.path)),
    successFailureCodeFields: keyPaths
      .filter((item) => SUCCESS_FAILURE_FIELD_PATTERN.test(item.path))
      .map((item) => item.path)
      .sort(),
  };
}

export function buildSafeCapture(records, secrets = {}) {
  const safeRecords = [];
  for (const record of records) {
    const request = summarizeRequest(record.request, secrets);
    if (!request.allowed) {
      continue;
    }
    const response = summarizeResponse(record.response ?? {});
    safeRecords.push({
      endpoint: request.endpoint,
      method: request.method,
      submissionid: request.submissionid,
      request,
      response,
    });
  }
  safeRecords.sort((left, right) => {
    const endpointOrder = left.endpoint.localeCompare(right.endpoint);
    if (endpointOrder !== 0) {
      return endpointOrder;
    }
    return left.method.localeCompare(right.method);
  });
  return {
    generatedAt: new Date(0).toISOString(),
    source: "kepco-login-schema-capture",
    allowedEndpoints: [...ALLOWED_ENDPOINTS],
    records: safeRecords,
  };
}

function stableCopy(value) {
  if (Array.isArray(value)) {
    return value.map(stableCopy);
  }
  if (isPlainObject(value)) {
    return Object.fromEntries(sortedEntries(value).map(([key, child]) => [key, stableCopy(child)]));
  }
  return value;
}

function hasCanary(serialized, canary) {
  return typeof canary === "string" && canary.length > 0 && serialized.includes(canary);
}

function findSuspiciousSerializedValues(value, path = "$", findings = []) {
  if (Array.isArray(value)) {
    value.forEach((child, index) => findSuspiciousSerializedValues(child, `${path}[${index}]`, findings));
    return findings;
  }
  if (isPlainObject(value)) {
    for (const [key, child] of Object.entries(value)) {
      findSuspiciousSerializedValues(child, jsonPathFor(path, key), findings);
    }
    return findings;
  }
  if (typeof value === "string") {
    const name = lastPathName(path);
    if (TOKEN_FIELD_PATTERN.test(name) && value.length > 0 && !/^\$\.|^\/|^[A-Za-z-]+$/.test(value)) {
      findings.push(path);
    }
    if (looksJwt(value)) {
      findings.push(path);
    }
  }
  return findings;
}

export function safeStringify(value, secrets = {}) {
  const sorted = stableCopy(value);
  const suspicious = findSuspiciousSerializedValues(sorted);
  if (suspicious.length > 0) {
    throw new Error(`Refusing to write suspicious secret-shaped values at ${suspicious.join(", ")}`);
  }
  const serialized = `${JSON.stringify(sorted, null, 2)}\n`;
  if (hasCanary(serialized, secrets.username) || hasCanary(serialized, secrets.password)) {
    throw new Error("Refusing to write capture output because credential canaries are present");
  }
  return serialized;
}

export function validateTempProfileForRemoval(profilePath) {
  const resolved = resolve(profilePath);
  const tempRoot = resolve(tmpdir());
  const expectedParent = tempRoot.endsWith(sep) ? tempRoot : `${tempRoot}${sep}`;
  const expectedPrefix = `${expectedParent}${TEMP_PROFILE_PREFIX}`;
  if (!resolved.startsWith(expectedPrefix)) {
    throw new Error(`Refusing to remove unexpected profile path: ${resolved}`);
  }
  return resolved;
}

async function promptVisible(query) {
  const rl = readline.createInterface({ input, output });
  try {
    return await rl.question(query);
  } finally {
    rl.close();
  }
}

async function promptMasked(query) {
  if (!input.isTTY) {
    throw new Error("Password prompt requires an interactive terminal");
  }
  output.write(query);
  input.setRawMode(true);
  input.resume();
  let value = "";
  try {
    for await (const chunk of input) {
      const text = chunk.toString("utf8");
      for (const char of text) {
        const code = char.charCodeAt(0);
        if (char === "\r" || char === "\n") {
          output.write("\n");
          return value;
        }
        if (code === 3) {
          throw new Error("Interrupted");
        }
        if (code === 8 || code === 127) {
          value = value.slice(0, -1);
          continue;
        }
        value += char;
        output.write("*");
      }
    }
  } finally {
    input.setRawMode(false);
    input.pause();
  }
  return value;
}

async function readCredentials() {
  const envUsername = process.env.KEPCO_LOGIN_SCHEMA_USERNAME;
  const envPassword = process.env.KEPCO_LOGIN_SCHEMA_PASSWORD;
  if (envUsername || envPassword) {
    output.write(
      "Warning: credential environment variables are for a one-time local interactive capture only. Clear shell history/session state after use.\n",
    );
  }
  const username = envUsername ?? (await promptVisible("KEPCO ON username: "));
  const password = envPassword ?? (await promptMasked("KEPCO ON password: "));
  if (!username.trim() || !password) {
    throw new Error("Username and password are required for interactive capture");
  }
  return { username: username.trim(), password };
}

function requestToPlain(request) {
  let postDataJSON = {};
  try {
    postDataJSON = request.postDataJSON();
  } catch {
    postDataJSON = {};
  }
  return {
    url: request.url(),
    method: request.method(),
    headers: request.headers(),
    postDataJSON,
  };
}

async function responseToPlain(response) {
  let json = {};
  try {
    json = await response.json();
  } catch {
    json = {};
  }
  return {
    status: response.status(),
    headers: await response.allHeaders(),
    json,
  };
}

async function runCapture() {
  const { chromium } = await import("playwright");
  const secrets = await readCredentials();
  const profilePath = await mkdtemp(join(tmpdir(), TEMP_PROFILE_PREFIX));
  const records = [];
  let context;
  try {
    context = await chromium.launchPersistentContext(profilePath, {
      channel: "chrome",
      headless: false,
    });
    const page = context.pages()[0] ?? (await context.newPage());
    page.on("response", async (response) => {
      const request = response.request();
      if (!isAllowedEndpoint(request.url())) {
        return;
      }
      try {
        const plainRecord = {
          request: requestToPlain(request),
          response: await responseToPlain(response),
        };
        records.push(plainRecord);
        const endpoint = endpointFromUrl(request.url());
        output.write(
          `Captured ${endpoint} status=${plainRecord.response.status} count=${records.length}\n`,
        );
      } catch (error) {
        output.write(`Skipped response summary after capture error: ${error.message}\n`);
      }
    });

    await page.goto(START_URL, { waitUntil: "domcontentloaded" });
    output.write("Complete the normal KEPCO ON login in Chrome. Do not bypass CAPTCHA, MFA, OACX, or other challenges.\n");
    await promptVisible("Press Enter here after login/session checks finish: ");
  } finally {
    if (context) {
      await context.close();
    }
    const safeProfile = validateTempProfileForRemoval(profilePath);
    await rm(safeProfile, { recursive: true, force: true });
  }

  const safeCapture = buildSafeCapture(records, secrets);
  const serialized = safeStringify(
    {
      ...safeCapture,
      generatedAt: new Date().toISOString(),
      captureHash: createHash("sha256")
        .update(JSON.stringify(safeCapture.records))
        .digest("hex"),
    },
    secrets,
  );
  await writeFile(OUTPUT_FILE, serialized, { encoding: "utf8", flag: "wx" });
  output.write(
    `Wrote ${OUTPUT_FILE}; endpoints=${safeCapture.records.length}; security-scan=passed\n`,
  );
}

if (process.argv[1] && resolve(fileURLToPath(import.meta.url)) === resolve(process.argv[1])) {
  runCapture().catch((error) => {
    console.error(`capture failed: ${error.message}`);
    process.exitCode = 1;
  });
}
