import { CodeBlock } from "@/components/docs/code-block";
import { LiveCatalogCount } from "./client";
import { Head, Opt, Stat } from "./kit";
import { CAPABILITIES, ENDPOINTS, FLARE_CAPS, FLARE_PROTOCOL, KIND_COUNT, KIND_GROUPS, TIERS } from "./facts-data";

const TITLE = "Plugins";
const DEK = (
  <>
    Flare is the open protocol for adding your own road alerts to CommuteScout. A plugin is a small HTTPS server that the map and
    the apps read.
  </>
);
const ACTIONS = (
  <>
    <a href="#plug-1" className="dx-btn dx-btn-primary">
      Run one locally
    </a>
    <a href="#plug-1" className="dx-textlink">
      Read the protocol
    </a>
  </>
);
const SRC_FLARE = <>src/ca_roads/flare.py (the spec is docs/flare.md, version 1)</>;
const SRC_KINDS = (
  <>
    {KIND_COUNT} = <code>len(KINDS)</code> in {SRC_FLARE}; group sizes as the /plugins page groups them.
  </>
);
const SRC_EP = (
  <>Endpoints: the paths <code>check_plugin()</code> calls in {SRC_FLARE}; which capability each needs from <code>CAPABILITIES</code>.</>
);
const SRC_TIERS = (
  <>
    Three tiers and what each may do: <code>tier_of()</code> docstring in {SRC_FLARE} (approved, unreviewed, private).
  </>
);

const HANDSHAKE = `{
  "protocol": "${FLARE_PROTOCOL}",
  "id": "example-alerts",
  "name": "Example Alerts",
  "capabilities": {"alerts": true, "report": true,
                   "confirm": true, "notify": false,
                   "snapshot": false},
  "kinds": ["CRASH_MAJOR", "HAZARD_ON_ROAD"],
  "refresh_s": 60,
  "auth": "none"
}`;

const START = `cd examples/flare-plugin
pip install starlette uvicorn && python server.py
python -m ca_roads.flare check http://127.0.0.1:8300`;

const maxGroup = Math.max(...KIND_GROUPS.map(([, n]) => n));

export function PluginsBoard() {
  return (
    <>
      <Opt
        id="plug-1"
        n="P1"
        name="The protocol on one card"
        rec
        idea="The whole protocol is five endpoints. Show them in the header with their method and which are required; a builder knows the size of the job at once."
        trade="Very concrete, and it makes “Read the protocol” almost unnecessary. Means nothing to a driver who only wants to install one (they belong on Marketplace)."
        src={SRC_EP}
      >
        <Head
          title={TITLE}
          dek={DEK}
          actions={ACTIONS}
          aside={
            <div className="fx-proto">
              <p className="fx-proto-h">
                <code>{FLARE_PROTOCOL}</code> <span>five endpoints, two required</span>
              </p>
              <ul>
                {ENDPOINTS.map(([m, p, needs]) => (
                  <li key={p}>
                    <span className={`dx-tag ${m === "GET" ? "dx-tag-get" : "dx-tag-post"}`}>{m}</span>
                    <code>{p}</code>
                    <em data-req={needs === "required"}>{needs === "required" ? "required" : `if ${needs}`}</em>
                  </li>
                ))}
              </ul>
            </div>
          }
        />
      </Opt>

      <Opt
        id="plug-2"
        n="P2"
        name="Trust ladder"
        idea="Replace “3 trust levels” with the three levels themselves, left to right, saying who it reaches and whether it may alert."
        trade="Answers the first worry of both builders and drivers. Repeats the visibility section unless that section becomes the detail."
        src={SRC_TIERS}
      >
        <Head title={TITLE} dek={DEK} actions={ACTIONS}>
          <ol className="fx-ladder3">
            {TIERS.map((t) => (
              <li key={t.name} data-tone={t.tone}>
                <b>{t.name}</b>
                <span>{t.who}</span>
                <span className="fx-ladder3-a">{t.alerts}</span>
              </li>
            ))}
          </ol>
        </Head>
      </Opt>

      <Opt
        id="plug-3"
        n="P3"
        name={`${KIND_COUNT} kinds, by group`}
        idea="Keep the alert-kind count but make it legible: one bar per group, sized by how many kinds it holds."
        trade="Shows the vocabulary a plugin speaks; a chart in a header can feel like decoration if the groups are not explained below."
        src={SRC_KINDS}
      >
        <Head title={TITLE} dek={DEK} actions={ACTIONS}>
          <figure className="fx-kinds">
            <figcaption>
              <b>{KIND_COUNT} alert kinds</b> a plugin can send, in {KIND_GROUPS.length} groups
            </figcaption>
            <ul>
              {KIND_GROUPS.map(([g, n]) => (
                <li key={g}>
                  <span>{g}</span>
                  <i aria-hidden="true" style={{ width: `${(n / maxGroup) * 100}%` }} />
                  <b>{n}</b>
                </li>
              ))}
            </ul>
          </figure>
        </Head>
      </Opt>

      <Opt
        id="plug-4"
        n="P4"
        name="Handshake card"
        idea="The handshake is what a plugin is. Show a short one beside the title, the way package pages show a manifest."
        trade="Precise for builders; heavy for anyone else. A trimmed sample, so it must say so."
        src={<>Fields from the HANDSHAKE example on /plugins and the checks in {SRC_FLARE}; trimmed.</>}
      >
        <Head
          title={TITLE}
          dek={DEK}
          actions={ACTIONS}
          aside={<CodeBlock code={HANDSHAKE} lang="json" title="GET /flare/v1/handshake" className="fx-aside-code" />}
        />
      </Opt>

      <Opt
        id="plug-5"
        n="P5"
        name="Live catalog"
        idea="Lead with what is real today: how many public plugins are listed and how many of their alerts are on the map, read live from the catalog."
        trade="Honest social proof that grows with the catalog. Small numbers look small while the catalog is young."
        src={<>Live from <code>/api/flare/sources</code> (the same call as the Public catalog section): plugins = sources listed, alerts = sum of each source’s count. {SRC_KINDS}</>}
      >
        <Head title={TITLE} dek={DEK} actions={ACTIONS}>
          <ul className="dx-facts" data-count="3">
            <Stat v={<LiveCatalogCount />} l="public plugins listed" sub="live" />
            <Stat v={<LiveCatalogCount what="alerts" />} l="plugin alerts on the map" sub="live" />
            <Stat v={KIND_COUNT} l="alert kinds" />
          </ul>
        </Head>
      </Opt>

      <Opt
        id="plug-6"
        n="P6"
        name="Capability checklist"
        idea="Five capabilities as a checklist, one required. It tells a builder the minimum plugin is one endpoint."
        trade="Encouraging (“you only need alerts”), but it is the first section of the page moved up."
        src={<>Capabilities and which is required: <code>CAPABILITIES</code> in {SRC_FLARE}.</>}
      >
        <Head title={TITLE} dek={DEK} actions={ACTIONS}>
          <ul className="fx-caps">
            {CAPABILITIES.map(([name, what, req]) => (
              <li key={name} data-req={req}>
                <code>{name}</code>
                <span>{what}</span>
                <em>{req ? "required" : "optional"}</em>
              </li>
            ))}
          </ul>
        </Head>
      </Opt>

      <Opt
        id="plug-7"
        n="P7"
        name="Three steps to listed"
        idea="The path from nothing to the public catalog, with the real commands in the first step. Also answers note #2: the call to action becomes the path."
        trade="Clear goal and next step; listing is the exception, so most readers stop at step one."
        src={<>Commands from the Run one locally and Conformance sections of /plugins; listing rules from Get listed.</>}
      >
        <Head title={TITLE} dek={DEK}>
          <ol className="fx-qs">
            <li>
              <b>Run the example</b>
              <CodeBlock code={START} lang="sh" className="fx-qs-code" />
            </li>
            <li>
              <b>Pass the check</b>
              <span>
                One command tests the handshake, alerts, caps and, if declared, a report and confirm round trip.
              </span>
            </li>
            <li>
              <b>Get listed</b>
              <span>Deploy behind HTTPS and send the manifest. Listed plugins carry their attribution on every marker.</span>
            </li>
          </ol>
        </Head>
      </Opt>

      <Opt
        id="plug-8"
        n="P8"
        name="The rules in numbers"
        idea="A strip of the hard caps a plugin must fit. These are the numbers a builder will hit, not marketing numbers."
        trade="True and useful, but limits first can feel strict. Works best on a protocol-reference page."
        src={<>MAX_ALERTS, MAX_BYTES, MIN_REFRESH_S, MAX_RADIUS_M, SNAPSHOT_MAX_ALERTS in {SRC_FLARE}.</>}
      >
        <Head title={TITLE} dek={DEK} actions={ACTIONS}>
          <ul className="dx-facts fx-facts5" data-count="5">
            {FLARE_CAPS.map((c) => (
              <Stat key={c.l} v={c.v} l={c.l} />
            ))}
          </ul>
        </Head>
      </Opt>

      <Opt
        id="plug-9"
        n="P9"
        name="Sentence"
        idea="No strip. One sentence that says what a plugin needs at minimum."
        trade="Quietest; the actions carry the header."
        src={<>{SRC_EP} {SRC_KINDS}</>}
      >
        <Head title={TITLE} dek={DEK} actions={ACTIONS}>
          <p className="fx-sentence">
            The minimum plugin answers <b>two</b> GET endpoints. Add report, confirm, notify or snapshot when you need them, and send any of{" "}
            <b>{KIND_COUNT}</b> alert kinds.
          </p>
        </Head>
      </Opt>
    </>
  );
}
