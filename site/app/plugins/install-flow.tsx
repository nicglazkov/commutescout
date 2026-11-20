import { Bell, Check, Puzzle, Volume2 } from "lucide-react";

// How a person turns a plugin on, drawn as the three screens they meet,
// in order. Every label is the product's own: the marketplace tile and its
// Install button (components/marketplace.tsx), the notice a plugin that is
// not reviewed shows at install (UNREVIEWED_NOTICE in src/ca_roads/flare.py),
// and the two per-plugin switches under Settings > Alerts in the apps.
// Static markup: nothing here needs script, and it reads the same with
// motion reduced.
const NOTICE =
  "This plugin hasn't been reviewed by CommuteScout. Its alerts come from its operator, not from official sources.";

export function InstallFlow() {
  return (
    <figure className="pg-flow" aria-labelledby="pg-flow-cap">
      <ol className="pg-flow-steps">
        <li className="pg-step">
          <p className="pg-step-k">
            <span className="pg-step-n" aria-hidden="true">1</span> Find it in the marketplace
          </p>
          <div className="pg-mock" aria-hidden="true">
            <div className="pg-tile">
              <span className="pg-tile-icon">
                <Puzzle />
              </span>
              <span className="pg-tile-name">
                <b>Example Alerts</b>
                <small>Run by its community</small>
              </span>
              <span className="pg-tile-btn">Install</span>
            </div>
            <span className="pg-badge" data-tier="unreviewed">
              Public, not reviewed
            </span>
          </div>
          <p className="pg-step-d">
            Each tile says what the plugin shows, where it covers, who runs it, and its trust level.
          </p>
        </li>

        <li className="pg-step">
          <p className="pg-step-k">
            <span className="pg-step-n" aria-hidden="true">2</span> Install, and tick the notice
          </p>
          <div className="pg-mock" aria-hidden="true">
            <div className="pg-notice">
              <span className="pg-check">
                <Check />
              </span>
              <span className="pg-notice-text">{NOTICE}</span>
            </div>
          </div>
          <p className="pg-step-d">
            Only plugins CommuteScout has not reviewed ask for this. Approved plugins install with no notice.
          </p>
        </li>

        <li className="pg-step">
          <p className="pg-step-k">
            <span className="pg-step-n" aria-hidden="true">3</span> Choose how it alerts you
          </p>
          <div className="pg-mock" aria-hidden="true">
            <div className="pg-switches">
              <p className="pg-switches-h">Settings &gt; Alerts &gt; Example Alerts</p>
              <span className="pg-switch-row">
                <Bell /> Alerts <span className="pg-switch" data-on="" />
              </span>
              <span className="pg-switch-row">
                <Volume2 /> Speak its alerts <span className="pg-switch" />
              </span>
            </div>
          </div>
          <p className="pg-step-d">
            Two switches per plugin in the iOS and Android apps. Speaking stays off until you turn it on.
          </p>
        </li>
      </ol>
      <figcaption id="pg-flow-cap" className="pg-flow-cap">
        On the website, Install turns the plugin&apos;s layer on for the map in this browser. The apps keep their own
        switch on each phone, and plugin alerts are never sent as push notifications.
      </figcaption>
    </figure>
  );
}
