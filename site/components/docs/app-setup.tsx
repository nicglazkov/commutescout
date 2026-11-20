"use client";

import { useId, useState } from "react";
import { ArrowUpRight } from "lucide-react";
import { CodeBlock } from "./code-block";

// /mcp head: pick your AI app from a grid, paste your key once, and every
// step below fills in with your personal link. The key stays in this
// browser tab: it is never stored or sent anywhere. The steps come from
// site/lib/mcp-clients.json (generated from src/ca_roads_mcp/connect.py),
// the same source as /llms.txt and the map's post-key panel.
type Step = { text?: string; code?: string; lang?: string };
export type SetupClient = {
  id: string;
  name: string;
  short?: string;
  hint?: string;
  install?: string;
  steps: Step[];
};

// The same shape as a key the server issues (src/ca_roads/apikeys.py).
const KEY_RE = /^cs_live_[0-9a-f]{8}_[A-Za-z0-9_-]{8,64}$/;

function installLink(kind: string | undefined, url: string): string | null {
  if (kind === "cursor") {
    return (
      "cursor://anysphere.cursor-deeplink/mcp/install?name=commutescout&config=" +
      encodeURIComponent(btoa(JSON.stringify({ url })))
    );
  }
  if (kind === "vscode") {
    return "vscode:mcp/install?" + encodeURIComponent(JSON.stringify({ name: "commutescout", type: "http", url }));
  }
  return null;
}

function codeLang(lang?: string) {
  if (lang === "sh") return "bash" as const;
  if (lang === "json" || lang === "toml") return lang;
  return "text" as const;
}

export function AppSetup({
  clients,
  placeholder,
  personalUrl,
}: {
  clients: SetupClient[];
  placeholder: string;
  personalUrl: string;
}) {
  const inputId = useId();
  const [raw, setRaw] = useState("");
  const [pick, setPick] = useState(clients[0]?.id ?? "");
  const typed = raw.trim();
  const key = KEY_RE.test(typed) ? typed : "";
  const bad = typed !== "" && !key;
  const fill = (s: string) => (key ? s.split(placeholder).join(key) : s);
  const client = clients.find((c) => c.id === pick) ?? clients[0];
  const oneClick = key ? installLink(client?.install, fill(personalUrl)) : null;

  return (
    <div className="dx-apps">
      <p className="dx-head-k">Connect in a minute</p>
      <div className="dx-apps-key">
        <label htmlFor={inputId}>Your key</label>
        <input
          id={inputId}
          type="text"
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          placeholder="Paste cs_live_… to fill in the steps"
          autoComplete="off"
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          aria-invalid={bad || undefined}
          aria-describedby={`${inputId}-note`}
        />
        <p id={`${inputId}-note`} className={bad ? "dx-apps-bad" : undefined}>
          {bad ? (
            "That doesn't look like a key. Keys start with cs_live_."
          ) : key ? (
            "Filled in below. Your key stays in this tab and is never saved."
          ) : (
            <>
              Stays in this tab, never saved. No key yet?{" "}
              <a href="/map?settings=keys" className="dx-link">
                Get a free key
              </a>
            </>
          )}
        </p>
      </div>

      <div className="dx-apps-grid" role="group" aria-label="Your AI app">
        {clients.map((c) => (
          <button
            key={c.id}
            type="button"
            className="dx-apps-tile"
            aria-pressed={c.id === client?.id}
            aria-controls={`${inputId}-steps`}
            onClick={() => setPick(c.id)}
          >
            <b>{c.short ?? c.name}</b>
            {c.hint ? <small>{c.hint}</small> : null}
          </button>
        ))}
      </div>

      {client ? (
        <div className="dx-apps-steps" id={`${inputId}-steps`} aria-live="polite">
          <p className="dx-apps-title">{client.name}</p>
          {oneClick ? (
            <a className="dx-btn dx-btn-primary dx-apps-one" href={oneClick}>
              Add to {client.short ?? client.name} <ArrowUpRight aria-hidden="true" />
            </a>
          ) : client.install ? (
            <p className="dx-apps-tip">Paste your key above for a one-click install link.</p>
          ) : null}
          {client.steps.map((step, i) =>
            step.code ? (
              <CodeBlock key={`${client.id}-${i}-${key ? "k" : "p"}`} code={fill(step.code)} lang={codeLang(step.lang)} />
            ) : (
              <p key={`${client.id}-${i}`}>{step.text}</p>
            ),
          )}
        </div>
      ) : null}
    </div>
  );
}
