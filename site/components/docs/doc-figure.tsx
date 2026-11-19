// The one place the developer pages import workstream B's figures from
// components/figures. A figure that is not built yet renders nothing, so
// every page still builds and reads complete without it. All five have
// landed; an entry set back to null would hide that figure again.
// Figures are numbered per page (n), not by B's gallery order.
//
//   mcp-call        /mcp         #how
//   route-strip     /mcp         #how
//   departure-chart /mcp         #how
//   plugin-flow     /plugins     #topology
//   map-layers      /data-sources #how
import type { ComponentType } from "react";
import McpCall from "@/components/figures/mcp-call";
import RouteStrip from "@/components/figures/route-strip";
import DepartureChart from "@/components/figures/departure-chart";
import PluginFlow from "@/components/figures/plugin-flow";
import MapLayers from "@/components/figures/map-layers";

export type FigureName =
  | "mcp-call"
  | "route-strip"
  | "departure-chart"
  | "plugin-flow"
  | "map-layers";

const FIGURES: Record<FigureName, ComponentType<{ n?: number | string }> | null> = {
  "mcp-call": McpCall,
  "route-strip": RouteStrip,
  "departure-chart": DepartureChart,
  "plugin-flow": PluginFlow,
  "map-layers": MapLayers,
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
