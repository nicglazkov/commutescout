import type { ReactNode } from "react";

// Build-time syntax highlighting for the docs code blocks. The pages are a
// static export and every block is a server component, so this runs once at
// build and ships plain <span>s: no client highlighter, no grammar bundle.
// Four small grammars cover everything the docs show: JSON (responses,
// manifests), shell (curl, git, pip), HTTP exchanges (a request line or a
// status line followed by JSON) and plain text. Capitalized placeholders
// such as LAT,LON or ROUTE get their own color so a reader sees what to
// replace.

export type Lang = "json" | "bash" | "http" | "text" | "toml";

type Tok = [cls: string | null, text: string];

const PLACEHOLDER = /^(?:[A-Z][A-Z0-9_]{2,}|LAT2?|LON2?)$/;
const IS_PH_WORD = /\b(?:YOUR_KEY|MIN_LAT|MIN_LON|MAX_LAT|MAX_LON|LAT2|LON2|LAT|LON|ROUTE|START|END|PLACE|REGION|ADDRESS|DESTINATION)\b/g;

function placeholders(text: string, base: string | null): Tok[] {
  const out: Tok[] = [];
  let last = 0;
  for (const m of text.matchAll(IS_PH_WORD)) {
    const i = m.index ?? 0;
    if (i > last) out.push([base, text.slice(last, i)]);
    out.push(["tk-h", m[0]]);
    last = i + m[0].length;
  }
  if (last < text.length) out.push([base, text.slice(last)]);
  return out;
}

function urlTokens(text: string, base: string): Tok[] {
  // Split a URL-ish string into path, ? & = punctuation, parameter names
  // and values, so long query strings stay readable.
  const q = text.indexOf("?");
  if (q < 0) return placeholders(text, base);
  const out: Tok[] = [...placeholders(text.slice(0, q), base), ["tk-p", "?"]];
  const parts = text.slice(q + 1).split(/(&)/);
  for (const part of parts) {
    if (part === "&") {
      out.push(["tk-p", "&"]);
      continue;
    }
    const eq = part.indexOf("=");
    if (eq < 0) {
      out.push(["tk-k", part]);
      continue;
    }
    out.push(["tk-k", part.slice(0, eq)], ["tk-p", "="], ...placeholders(part.slice(eq + 1), base));
  }
  return out;
}

function json(src: string): Tok[] {
  const out: Tok[] = [];
  const re = /("(?:[^"\\]|\\.)*")(\s*:)?|(-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|\b(true|false|null)\b|([{}[\],:])|(\.\.\.[^.\n]*?\.\.\.)|([A-Za-z_][A-Za-z0-9_]*)/g;
  let last = 0;
  for (const m of src.matchAll(re)) {
    const i = m.index ?? 0;
    if (i > last) out.push([null, src.slice(last, i)]);
    if (m[1]) {
      if (m[2]) {
        out.push(["tk-k", m[1]], ["tk-p", m[2]]);
      } else if (/^"https?:\/\//.test(m[1]) || /^"\/[a-z]/.test(m[1])) {
        out.push(...urlTokens(m[1], "tk-s"));
      } else {
        out.push(...placeholders(m[1], "tk-s"));
      }
    } else if (m[3]) out.push(["tk-n", m[3]]);
    else if (m[4]) out.push(["tk-b", m[4]]);
    else if (m[5]) out.push(["tk-p", m[5]]);
    else if (m[6]) out.push(["tk-c", m[6]]);
    else if (m[7]) out.push([PLACEHOLDER.test(m[7]) ? "tk-h" : null, m[7]]);
    last = i + m[0].length;
  }
  if (last < src.length) out.push([null, src.slice(last)]);
  return out;
}

function bashLine(line: string): Tok[] {
  if (/^\s*#/.test(line)) return [["tk-c", line]];
  const out: Tok[] = [];
  const re = /("(?:[^"\\]|\\.)*"|'[^']*')|(\s--?[A-Za-z][\w-]*)|(\\$)|(\$[A-Z_]+)|(&&|\|)|(\S+)/g;
  let last = 0;
  let first = true;
  for (const m of line.matchAll(re)) {
    const i = m.index ?? 0;
    if (i > last) out.push([null, line.slice(last, i)]);
    if (m[1]) {
      const inner = m[1];
      out.push(...(inner.includes("://") || inner.includes("?") ? urlTokens(inner, "tk-s") : placeholders(inner, "tk-s")));
    } else if (m[2]) out.push(["tk-f", m[2]]);
    else if (m[3]) out.push(["tk-p", m[3]]);
    else if (m[4]) out.push(["tk-b", m[4]]);
    else if (m[5]) {
      out.push(["tk-p", m[5]]);
      first = true;
      last = i + m[0].length;
      continue;
    } else if (m[6]) {
      if (first) out.push(["tk-m", m[6]]);
      else if (m[6].includes("://")) out.push(...urlTokens(m[6], "tk-u"));
      else out.push(...placeholders(m[6], null));
    }
    first = false;
    last = i + m[0].length;
  }
  if (last < line.length) out.push([null, line.slice(last)]);
  // A continuation line (after a trailing backslash) does not start a new command.
  return out;
}

function bash(src: string): Tok[] {
  const lines = src.split("\n");
  const out: Tok[] = [];
  let continued = false;
  lines.forEach((line, n) => {
    const toks = bashLine(line);
    if (continued) {
      // Undo "command" coloring on a continuation line.
      for (const t of toks) if (t[0] === "tk-m") t[0] = null;
    }
    out.push(...toks);
    continued = /\\$/.test(line);
    if (n < lines.length - 1) out.push([null, "\n"]);
  });
  return out;
}

function http(src: string): Tok[] {
  const out: Tok[] = [];
  const lines = src.split("\n");
  lines.forEach((line, n) => {
    const req = line.match(/^(GET|POST|PUT|DELETE|OPTIONS)(\s+)(\S+)(.*)$/);
    const status = line.match(/^(\d{3})(\s+)(.*)$/);
    if (req) {
      out.push(["tk-m", req[1]], [null, req[2]], ...urlTokens(req[3], "tk-u"), [null, req[4]]);
    } else if (status) {
      out.push(["tk-n", status[1]], [null, status[2]]);
      // "201 {json}   trailing words": color the JSON, keep the words muted.
      const tail = status[3];
      const gap = tail.search(/\s{2,}\S[^{}]*$/);
      if (tail.startsWith("{") && gap > 0) {
        out.push(...json(tail.slice(0, gap)), ["tk-c", tail.slice(gap)]);
      } else if (tail.startsWith("{")) {
        out.push(...json(tail));
      } else {
        out.push(["tk-c", tail]);
      }
    } else if (/^[a-z_]+(\s{2,}[a-z_]+.*)?$/.test(line.trim()) && line.trim().includes("_")) {
      // A bare list of error codes.
      out.push(...line.split(/(\s+|\(.*?\))/).map((w): Tok => [/^[a-z_]+$/.test(w) ? "tk-k" : w.startsWith("(") ? "tk-c" : null, w]));
    } else {
      out.push(...json(line));
    }
    if (n < lines.length - 1) out.push([null, "\n"]);
  });
  return out;
}

function toml(src: string): Tok[] {
  const out: Tok[] = [];
  const lines = src.split("\n");
  lines.forEach((line, n) => {
    const sec = line.match(/^(\s*)(\[[^\]]+\])(.*)$/);
    const kv = line.match(/^(\s*)([A-Za-z0-9_.-]+)(\s*=\s*)(.*)$/);
    if (/^\s*#/.test(line)) out.push(["tk-c", line]);
    else if (sec) out.push([null, sec[1]], ["tk-b", sec[2]], [null, sec[3]]);
    else if (kv) out.push([null, kv[1]], ["tk-k", kv[2]], ["tk-p", kv[3]], ...json(kv[4]));
    else out.push(...json(line));
    if (n < lines.length - 1) out.push([null, "\n"]);
  });
  return out;
}

export function highlight(code: string, lang: Lang): ReactNode[] {
  let toks: Tok[];
  switch (lang) {
    case "json":
      toks = json(code);
      break;
    case "bash":
      toks = bash(code);
      break;
    case "http":
      toks = http(code);
      break;
    case "toml":
      toks = toml(code);
      break;
    default:
      toks = placeholders(code, null);
  }
  // Merge neighbors with the same class to keep the markup small.
  const merged: Tok[] = [];
  for (const t of toks) {
    if (!t[1]) continue;
    const prev = merged[merged.length - 1];
    if (prev && prev[0] === t[0]) prev[1] += t[1];
    else merged.push([t[0], t[1]]);
  }
  return merged.map(([cls, text], i) =>
    cls ? (
      <span key={i} className={cls}>
        {text}
      </span>
    ) : (
      text
    ),
  );
}
