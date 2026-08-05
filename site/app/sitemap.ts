import type { MetadataRoute } from "next";

// Required by this Next version's static export: sitemap.ts is treated as
// a route handler, and `output: "export"` refuses to build one without an
// explicit static/revalidate declaration (confirmed against the build
// error pointing at
// https://nextjs.org/docs/advanced-features/static-html-export). Nothing
// here reads the request or varies per build, so force-static is exact,
// not a workaround.
export const dynamic = "force-static";

// Renders to a static sitemap.xml at build time (see the "Route Handlers"
// section of node_modules/next/dist/docs/.../static-exports.md: this file
// type is treated the same way and is fully supported under
// output: "export" as long as it does not read the request). Served in
// production by the /sitemap.xml route in src/ca_roads_demo/app.py,
// through the same SITE_DIR/REPO_SITE_OUT resolution as the other
// exported pages.
const BASE_URL = "https://commutescout.com";

// The six marketing pages (see the URL map in
// docs/superpowers/specs/2026-08-05-saas-shell-redesign-design.md) plus
// /map. /map is not a page in this Next app - it is the Leaflet map,
// served straight from src/ca_roads_demo/static/map.html - so it is
// listed here by hand alongside the exported routes below.
const MARKETING_PATHS = ["", "/pricing", "/about", "/contact", "/privacy",
  "/terms"];

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();
  const marketing: MetadataRoute.Sitemap = MARKETING_PATHS.map((path) => ({
    url: `${BASE_URL}${path}`,
    lastModified,
    changeFrequency: path === "" ? "weekly" : "monthly",
    priority: path === "" ? 1 : 0.8,
  }));
  return [
    ...marketing,
    {
      url: `${BASE_URL}/map`,
      lastModified,
      changeFrequency: "daily",
      priority: 0.9,
    },
  ];
}
