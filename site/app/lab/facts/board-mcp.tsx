import { CodeBlock, CopyField } from "@/components/docs/code-block";
import { FxTabs } from "./client";
import { Head, Opt, Stat } from "./kit";
import {
  CLIENTS,
  FREE,
  MCP_ENDPOINT,
  MCP_PROMPTS,
  READY_CLIENTS,
  STATE_COUNT,
  TOOL_COUNT,
  TOOL_GROUPS,
  firstCode,
} from "./facts-data";

const TITLE = "MCP server";
// The live dek names ChatGPT, but mcp-clients.json marks ChatGPT "not yet"
// (no header auth). The board's dek leaves it out; flagged in the report.
const DEK = (
  <>
    Give Claude, Cursor or any MCP client live road data in {STATE_COUNT} states. Plan a drive, find the best time to leave,
    or check what is on the road right now.
  </>
);
const ACTIONS = (
  <>
    <CopyField value={MCP_ENDPOINT} label="MCP endpoint" />
    <a href="#mcp-1" className="dx-textlink">
      Setup
    </a>
  </>
);
const SRC_CLIENTS = (
  <>
    Clients, commands and the ChatGPT “not yet” come from site/lib/mcp-clients.json (generated from
    src/ca_roads_mcp/connect.py).
  </>
);
const SRC_TOOLS = (
  <>
    {TOOL_COUNT} = tools in site/lib/api-reference.json (generated from the server registry; tests/test_snapshot.py checks every
    “N tools” claim). Groups as on /mcp and in the server instructions.
  </>
);
const SRC_LIMITS = (
  <>
    Free tier from src/ca_roads/apikeys.py <code>TIERS[&quot;free&quot;]</code>: daily 2000, per_second 0.5 (30 a minute),
    counted per account; /mcp and /v1/tools both need a key (ratelimit.py <code>KEY_REQUIRED_PREFIXES</code>).
  </>
);

const INSTALL_TABS = ["claude-code", "codex", "gemini", "cursor", "vscode"].map((id) => {
  const c = CLIENTS.find((x) => x.id === id)!;
  const code = firstCode(id);
  const lang = code.trim().startsWith("{") ? "json" : "sh";
  return {
    id,
    label: c.name.replace(" (GitHub Copilot)", "").replace("OpenAI ", ""),
    body: <CodeBlock code={code} lang={lang} className="fx-tabcode" />,
  };
});

const CHAT = {
  q: "When should I leave home tomorrow to be at work by 9?",
  call: `best_time_to_go(origin="home", destination="work", day="tomorrow", arrive_by="9am")`,
};

export function McpBoard() {
  const chatgpt = CLIENTS.find((c) => c.id === "chatgpt");
  return (
    <>
      <Opt
        id="mcp-1"
        n="M1"
        name="Install command, by client"
        rec
        idea="The header’s job is to get someone connected. Put the one-line add command in the header, with a tab per client, instead of facts."
        trade="The copy field and the Setup section become partly redundant; the header gets taller. Best conversion for the people who came to install."
        src={SRC_CLIENTS}
      >
        <Head
          title={TITLE}
          dek={DEK}
          aside={
            <div className="fx-install">
              <p className="fx-install-k">Connect in one command</p>
              <FxTabs label="Client" tabs={INSTALL_TABS} />
              <p className="fx-install-foot">
                Replace <code className="dx-ic">cs_live_...</code> with your free key. Other clients:{" "}
                <a href="#mcp-1" className="dx-link">
                  Setup
                </a>
              </p>
            </div>
          }
        />
      </Opt>

      <Opt
        id="mcp-2"
        n="M2"
        name="Works with"
        idea="A roster of clients as plain text, each with its status. Honest about the one that cannot connect yet."
        trade="Answers “will it work in my tool?” instantly. Text, not logos, so it never looks like a borrowed brand wall."
        src={SRC_CLIENTS}
      >
        <Head title={TITLE} dek={DEK} actions={ACTIONS}>
          <div className="fx-roster">
            <p className="fx-roster-k">Works with</p>
            <ul>
              {READY_CLIENTS.map((c) => (
                <li key={c.id}>
                  <i aria-hidden="true" data-ok="true" />
                  {c.name}
                </li>
              ))}
              <li>
                <i aria-hidden="true" data-ok="true" />
                Any client that can send a header
              </li>
              {chatgpt ? (
                <li className="fx-roster-no">
                  <i aria-hidden="true" data-ok="false" />
                  {chatgpt.name} <em>not yet, needs sign-in support</em>
                </li>
              ) : null}
            </ul>
          </div>
        </Head>
      </Opt>

      <Opt
        id="mcp-3"
        n="M3"
        name="Spec sheet"
        idea="A definition list a developer can scan like a package README: endpoint, transport, auth, limits, what is inside."
        trade="Precise and quiet; zero personality. Good if the page wants to read as reference."
        src={<>{SRC_TOOLS} {SRC_LIMITS} Transport: “--transport http” in every CLI command in mcp-clients.json. Prompts: the three in src/ca_roads_mcp/server.py.</>}
      >
        <Head title={TITLE} dek={DEK}>
          <dl className="fx-spec">
            <div>
              <dt>Endpoint</dt>
              <dd>
                <code>{MCP_ENDPOINT}</code>
              </dd>
            </div>
            <div>
              <dt>Transport</dt>
              <dd>Streamable HTTP</dd>
            </div>
            <div>
              <dt>Auth</dt>
              <dd>
                <code>Authorization: Bearer</code> with your key
              </dd>
            </div>
            <div>
              <dt>Free limit</dt>
              <dd>{FREE.daily} requests a day per account, shared with the REST API</dd>
            </div>
            <div>
              <dt>Inside</dt>
              <dd>
                {TOOL_COUNT} tools, {MCP_PROMPTS} prompts
              </dd>
            </div>
          </dl>
        </Head>
      </Opt>

      <Opt
        id="mcp-4"
        n="M4"
        name="What a call looks like"
        idea="A literal three-step figure: the question someone types, the tool call their assistant makes, the kind of answer that comes back."
        trade="Explains MCP to someone who has never used it. The answer text is an example, not a promise of exact wording."
        src={<>Tool and parameter names from site/lib/api-reference.json (best_time_to_go: origin, destination, day, arrive_by, which “returns the latest safe departure”; “home” and “work” resolve to saved places with a key). Answer is an example.</>}
      >
        <Head title={TITLE} dek={DEK} actions={ACTIONS}>
          <ol className="fx-chat" aria-label="Example">
            <li>
              <span className="fx-chat-k">You ask</span>
              <p>{CHAT.q}</p>
            </li>
            <li>
              <span className="fx-chat-k">Your assistant calls</span>
              <p>
                <code>{CHAT.call}</code>
              </p>
            </li>
            <li>
              <span className="fx-chat-k">It answers</span>
              <p>The latest safe time to leave, checked against typical traffic, the forecast and what usually happens on that route at that hour.</p>
            </li>
          </ol>
        </Head>
      </Opt>

      <Opt
        id="mcp-5"
        n="M5"
        name="Tool count, split open"
        idea={`Keep “${TOOL_COUNT} tools” as the fact, but show what they are: one bar split into the three groups, with every tool name in mono under its group.`}
        trade="Turns a vanity number into a menu. Busy at phone width, where the names wrap to several lines."
        src={SRC_TOOLS}
      >
        <Head title={TITLE} dek={DEK} actions={ACTIONS}>
          <div className="fx-groups">
            <p className="fx-groups-h">
              <b>{TOOL_COUNT} tools</b> in three groups
            </p>
            <div className="fx-groups-row">
              {TOOL_GROUPS.map((g) => (
                <div key={g.title} style={{ flexGrow: g.tools.length }} className="fx-group">
                  <span className="fx-group-bar" aria-hidden="true" />
                  <p>
                    {g.title} <b>{g.tools.length}</b>
                  </p>
                  <ul>
                    {g.tools.map((t) => (
                      <li key={t}>
                        <code>{t}</code>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </Head>
      </Opt>

      <Opt
        id="mcp-6"
        n="M6"
        name="Three steps"
        idea="The header as a checklist: get a key, add the server, ask. Each step names the exact thing to do."
        trade="Clear path for first-timers; repeats the Setup section in short form."
        src={<>{SRC_LIMITS} Endpoint from mcp-clients.json.</>}
      >
        <Head title={TITLE} dek={DEK}>
          <ol className="fx-steps">
            <li>
              <b>Get a free key</b>
              <span>{FREE.daily} requests a day per account</span>
            </li>
            <li>
              <b>Add the server</b>
              <span>
                <code>{MCP_ENDPOINT.replace("https://", "")}</code>
              </span>
            </li>
            <li>
              <b>Ask about a drive</b>
              <span>“Anything on my way to work?”</span>
            </li>
          </ol>
        </Head>
      </Opt>

      <Opt
        id="mcp-7"
        n="M7"
        name="Config card"
        idea="Show the config file people paste, at full size beside the title. The JSON is the documentation."
        trade="Ideal for editor users; meaningless to someone on claude.ai, whose setup is clicks, not JSON."
        src={SRC_CLIENTS}
      >
        <Head
          title={TITLE}
          dek={DEK}
          actions={ACTIONS}
          aside={<CodeBlock code={firstCode("cursor")} lang="json" title=".cursor/mcp.json" className="fx-aside-code" />}
        />
      </Opt>

      <Opt
        id="mcp-8"
        n="M8"
        name="A better strip"
        idea="Keep the strip format but swap in the facts an installer needs: tools, clients with steps, free limit, auth."
        trade="Lowest-effort change, consistent with the other doc pages; still a row of boxes."
        src={<>{SRC_TOOLS} {SRC_CLIENTS} {SRC_LIMITS}</>}
      >
        <Head title={TITLE} dek={DEK} actions={ACTIONS}>
          <ul className="dx-facts" data-count="4">
            <Stat v={TOOL_COUNT} l="tools" />
            <Stat v={READY_CLIENTS.length} l="clients with setup steps" />
            <Stat v={FREE.daily} l="free requests a day" />
            <Stat v="Bearer" l="one key header" />
          </ul>
        </Head>
      </Opt>

      <Opt
        id="mcp-9"
        n="M9"
        name="Sentence"
        idea="No strip; one line of facts under the endpoint field."
        trade="Least visual weight; the endpoint field becomes the hero."
        src={<>{SRC_TOOLS} {SRC_LIMITS}</>}
      >
        <Head title={TITLE} dek={DEK} actions={ACTIONS}>
          <p className="fx-sentence">
            <b>{TOOL_COUNT}</b> tools and <b>{MCP_PROMPTS}</b> prompts over streamable HTTP. One key header, <b>{FREE.daily}</b> free
            requests a day.
          </p>
        </Head>
      </Opt>
    </>
  );
}
