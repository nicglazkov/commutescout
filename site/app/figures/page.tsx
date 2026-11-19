import type { Metadata } from "next";
import FeedBench from "@/components/figures/feed-bench";
import UsCoverageMap from "@/components/figures/us-coverage-map";
import WatchChecks from "@/components/figures/watch-checks";
import RouteStrip from "@/components/figures/route-strip";
import DepartureChart from "@/components/figures/departure-chart";
import RateLimit from "@/components/figures/rate-limit";
import McpCall from "@/components/figures/mcp-call";
import PluginFlow from "@/components/figures/plugin-flow";
import FeedCadence from "@/components/figures/feed-cadence";

// Review gallery for workstream B's figures. Not linked from the site and not indexed.
// ?theme=dark or ?theme=light forces a theme for screenshots (sets data-theme on <html>).
export const metadata: Metadata = {
  title: "Figures (review)",
  robots: { index: false, follow: false },
};

const THEME_SCRIPT = `(function(){try{var t=new URLSearchParams(location.search).get("theme");if(t){document.documentElement.setAttribute("data-theme",t);document.documentElement.classList.toggle("dark",t==="dark");document.documentElement.classList.toggle("light",t==="light");document.documentElement.style.colorScheme=t;}var o=new URLSearchParams(location.search).get("only");if(o){var st=document.createElement("style");st.textContent="[data-fig]:not([data-fig='"+o.replace(/[^a-z0-9-]/g,"")+"']){display:none}";document.head.appendChild(st);}}catch(e){}})();`;

export default function FiguresPage() {
  return (
    <main style={{ background: "var(--cs-bg)", minHeight: "100vh" }}>
      <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      <div style={{ maxWidth: 1120, margin: "0 auto", padding: "48px 16px 96px", display: "grid", gap: 72 }}>
        <section data-fig="feed-bench" id="feed-bench"><FeedBench n={1} /></section>
        <section data-fig="us-coverage-map" id="us-coverage-map"><UsCoverageMap n={2} /></section>
        <section data-fig="watch-checks" id="watch-checks"><WatchChecks n={3} /></section>
        <section data-fig="route-strip" id="route-strip"><RouteStrip n={4} /></section>
        <section data-fig="departure-chart" id="departure-chart"><DepartureChart n={5} /></section>
        <section data-fig="rate-limit" id="rate-limit"><RateLimit n={6} /></section>
        <section data-fig="mcp-call" id="mcp-call"><McpCall n={7} /></section>
        <section data-fig="plugin-flow" id="plugin-flow"><PluginFlow n={8} /></section>
        <section data-fig="feed-cadence" id="feed-cadence"><FeedCadence n={9} /></section>
      </div>
    </main>
  );
}
