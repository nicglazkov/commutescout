// The one place the developer pages import workstream B's figures from
// components/figures. A figure that is not built yet renders nothing, so
// every page still builds and reads complete without it. All six have
// landed; an entry set back to null would hide that figure again.
// Figures are numbered per page (n), not by B's gallery order.
//
//   rate-limit      /developers  #keys
//   mcp-call        /mcp         #how
//   route-strip     /mcp         #how
//   departure-chart /mcp         #how
//   plugin-flow     /plugins     #topology
//   feed-cadence    /data-sources #freshness
import type { ComponentType } from "react";
import RateLimit from "@/components/figures/rate-limit";
import McpCall from "@/components/figures/mcp-call";
import RouteStrip from "@/components/figures/route-strip";
import DepartureChart from "@/components/figures/departure-chart";
import PluginFlow from "@/components/figures/plugin-flow";
import FeedCadence from "@/components/figures/feed-cadence";

export type FigureName =
  | "rate-limit"
  | "mcp-call"
  | "route-strip"
  | "departure-chart"
  | "plugin-flow"
  | "feed-cadence";

const FIGURES: Record<FigureName, ComponentType<{ n?: number | string }> | null> = {
  "rate-limit": RateLimit,
  "mcp-call": McpCall,
  "route-strip": RouteStrip,
  "departure-chart": DepartureChart,
  "plugin-flow": PluginFlow,
  "feed-cadence": FeedCadence,
};

export function DocFigure({ name, n = 1 }: { name: FigureName; n?: number }) {
  const Figure = FIGURES[name];
  if (!Figure) return null;
  return (
    <div className="dx-figure">
      <Figure n={n} />
    </div>
  );
}
