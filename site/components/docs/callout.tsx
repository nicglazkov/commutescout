import { Info, TriangleAlert } from "lucide-react";

export function Callout({ children, tone = "note" }: { children: React.ReactNode; tone?: "note" | "warn" }) {
  return (
    <div className={"dx-callout" + (tone === "warn" ? " dx-callout--warn" : "")} role="note">
      {tone === "warn" ? <TriangleAlert aria-hidden="true" /> : <Info aria-hidden="true" />}
      <div>{children}</div>
    </div>
  );
}
