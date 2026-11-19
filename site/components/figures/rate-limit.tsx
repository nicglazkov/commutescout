"use client";

import { useState } from "react";
import { FigureFrame } from "./frame";

// Two limits per caller, checked in this order (src/ca_roads_mcp/ratelimit.py):
// 1. a token bucket: `burst` tokens, refilled at `per_second`. Empty -> 429 rate_limited, Retry-After: 2
//    (keyless :222-231, keyed :330-335)
// 2. a daily counter, counted only after the bucket allows (comment at :232), reset at UTC midnight
//    (DailyCounter, src/ca_roads_mcp/budget.py). Over -> 429 daily_limit, Retry-After: 3600 (:233-241, :336-344)
// Who is "one caller":
// - no key: the client address, IPv6 folded to its /64 (limiter_key). RateLimiter(capacity=20,
//   refill_per_second=0.5) (:123-127); daily 10,000 (MCP_PER_CLIENT_DAILY, src/ca_roads_mcp/server.py:2076-2078)
// - with a key: the account, `who = f"acct:{uid}"` (:326), so every key on an account (up to 5,
//   MAX_KEYS_PER_ACCOUNT) shares one bucket and one day. Tiers: src/ca_roads_mcp/apikeys.py:25-36
//   free 30 burst, 0.5/s, 2,000/day; pro 60 burst, 2/s, 10,000/day. Keyed answers carry
//   RateLimit-Limit and RateLimit-Remaining (:337-341, :350-356). An unknown key is a 401, never a keyless fallback (:319).

type Mode = "keyless" | "free" | "pro";
const TIERS: Record<Mode, { burst: number; rate: number; daily: number; who: string; label: string }> = {
  keyless: { burst: 20, rate: 0.5, daily: 10000, who: "your address", label: "No key" },
  free: { burst: 30, rate: 0.5, daily: 2000, who: "your account", label: "Free key" },
  pro: { burst: 60, rate: 2, daily: 10000, who: "your account", label: "Pro key" },
};
const KEYS = ["Laptop", "Server", "Assistant"];

type Line = { id: number; code: number; text: string; from?: string };
type Sim = { tokens: number; used: number; log: Line[]; seq: number; t: number };
const fresh = (m: Mode): Sim => ({ tokens: TIERS[m].burst, used: 0, log: [], seq: 0, t: 0 });

export default function RateLimit({ n = 6 }: { n?: number | string }) {
  const [mode, setMode] = useState<Mode>("keyless");
  const [key, setKey] = useState(0);
  const [sim, setSim] = useState<Sim>(() => fresh("keyless"));
  const T = TIERS[mode];
  const keyed = mode !== "keyless";

  const choose = (m: Mode) => {
    setMode(m);
    setSim(fresh(m));
  };
  const send = (count: number) =>
    setSim((s) => {
      let { tokens, used, seq } = s;
      const log = [...s.log];
      let ok = 0;
      let bucket = 0;
      let daily = 0;
      for (let i = 0; i < count; i++) {
        if (tokens < 1) bucket++;
        else {
          tokens -= 1;
          if (used >= T.daily) daily++;
          else {
            used++;
            ok++;
          }
        }
      }
      const from = keyed ? KEYS[key] : undefined;
      const rem = Math.max(0, T.daily - used);
      if (ok) log.push({ id: ++seq, code: 200, from, text: `${ok} × 200 OK${keyed ? ` · RateLimit-Remaining: ${rem}` : ""}` });
      if (bucket) log.push({ id: ++seq, code: 429, from, text: `${bucket} × 429 rate_limited · Retry-After: 2` });
      if (daily) log.push({ id: ++seq, code: 429, from, text: `${daily} × 429 daily_limit · Retry-After: 3600` });
      return { ...s, tokens, used, seq, log: log.slice(-4) };
    });
  const wait = (sec: number) =>
    setSim((s) => ({ ...s, t: s.t + sec, tokens: Math.min(T.burst, s.tokens + sec * T.rate), log: [...s.log, { id: s.seq + 1, code: 0, text: `waited ${sec} s · +${Math.min(T.burst - s.tokens, sec * T.rate).toFixed(0)} tokens` }].slice(-4), seq: s.seq + 1 }));
  const nearCap = () => setSim((s) => ({ ...s, used: Math.max(s.used, T.daily - 3), log: [...s.log, { id: s.seq + 1, code: 0, text: `later that day · ${T.daily - 3} used` }].slice(-4), seq: s.seq + 1 }));
  const midnight = () => setSim((s) => ({ ...s, used: 0, log: [...s.log, { id: s.seq + 1, code: 0, text: "00:00 UTC · daily count back to 0" }].slice(-4), seq: s.seq + 1 }));

  const full = Math.floor(sim.tokens);
  const dailyPct = (sim.used / T.daily) * 100;
  const readout = `${full} of ${T.burst} tokens · ${sim.used.toLocaleString("en-US")} of ${T.daily.toLocaleString("en-US")} today, per ${keyed ? "account" : "address"}`;

  return (
    <FigureFrame
      n={n}
      title="Two limits: a bucket and a day"
      className="csf-rate"
      hint="Pick a caller, then send requests"
      readout={readout}
      controls={
        <div className="rl-controls">
          <div className="csf-controls" role="group" aria-label="Simulate">
            <button type="button" className="csf-btn" data-primary="" onClick={() => send(1)}>
              Send 1
            </button>
            <button type="button" className="csf-btn" onClick={() => send(25)}>
              Send 25 at once
            </button>
            <button type="button" className="csf-btn" onClick={() => wait(10)}>
              Wait 10 s
            </button>
            <button type="button" className="csf-btn" onClick={nearCap}>
              Jump to late in the day
            </button>
            <button type="button" className="csf-btn" onClick={midnight}>
              UTC midnight
            </button>
          </div>
        </div>
      }
      caption={
        <>
          Every caller gets a bucket for bursts and a count for the day. Without a key the caller is your address; with a key it
          is your account, so all of an account&apos;s keys (up to five) draw from the same bucket and the same day. A request the
          bucket turns away does not count against the day. The day resets at midnight UTC.
        </>
      }
    >
      <div className="rl" data-mode={mode}>
        <div className="rl-top">
          <div className="csf-controls" role="group" aria-label="Who is calling">
            {(Object.keys(TIERS) as Mode[]).map((m) => (
              <button key={m} type="button" className="csf-chip" aria-pressed={mode === m} onClick={() => choose(m)}>
                {TIERS[m].label}
              </button>
            ))}
          </div>
        </div>
        <div className="rl-callers" aria-label={keyed ? "Keys on one account" : "One address"}>
          {keyed ? (
            <>
              <div className="csf-controls" role="group" aria-label="Send from key">
                {KEYS.map((k, i) => (
                  <button key={k} type="button" className="csf-chip rl-key" aria-pressed={key === i} onClick={() => setKey(i)}>
                    <span className="rl-key-glyph csf-mono" aria-hidden="true">
                      cs_live_…{["7a", "c2", "e9"][i]}
                    </span>
                    {k}
                  </button>
                ))}
              </div>
              <p className="rl-note">Three keys, one account: one bucket, one day.</p>
            </>
          ) : (
            <p className="rl-note">
              No key: limited per address <span className="csf-mono">(IPv6 by /64)</span>.
            </p>
          )}
        </div>

        <div className="rl-meters">
          <section className="rl-meter" aria-label="Burst bucket">
            <header>
              <b>Bucket</b>
              <span className="csf-mono">
                {T.burst} burst · refills {T.rate}/s ({T.rate * 60}/min)
              </span>
            </header>
            <div className="rl-cells" style={{ ["--cols" as string]: T.burst > 30 ? 20 : T.burst > 20 ? 15 : 10 }} aria-hidden="true">
              {Array.from({ length: T.burst }, (_, i) => (
                <span key={i} className="rl-cell" data-on={i < full ? "" : undefined} />
              ))}
            </div>
            <p className="rl-sub">
              {full === 0 ? "Empty: the next request gets 429 rate_limited, Retry-After: 2" : `${full} tokens ready`}
            </p>
          </section>
          <section className="rl-meter" aria-label="Daily count">
            <header>
              <b>Today (UTC)</b>
              <span className="csf-mono">{T.daily.toLocaleString("en-US")} per day</span>
            </header>
            <div className="rl-day" aria-hidden="true">
              <span style={{ transform: `scaleX(${Math.max(dailyPct, sim.used ? 0.6 : 0) / 100})` }} data-full={sim.used >= T.daily ? "" : undefined} />
            </div>
            <p className="rl-sub">
              {sim.used >= T.daily
                ? "Used up: 429 daily_limit, Retry-After: 3600, until midnight UTC"
                : `${sim.used.toLocaleString("en-US")} used · ${(T.daily - sim.used).toLocaleString("en-US")} left`}
            </p>
          </section>
        </div>

        <ol className="rl-log" aria-live="polite" aria-label="Responses">
          {sim.log.length === 0 && <li className="rl-line rl-empty">Responses appear here.</li>}
          {sim.log.map((l) => (
            <li key={l.id} className="rl-line csf-mono" data-code={l.code || undefined}>
              {l.from && <span className="rl-from">{l.from}</span>}
              {l.text}
            </li>
          ))}
        </ol>
      </div>
    </FigureFrame>
  );
}
