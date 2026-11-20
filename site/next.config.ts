import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // Static export: the build writes plain HTML/CSS/JS to out/, which the
  // Python app serves. No Node runs in production.
  output: "export",
  // Project ruling: served URLs are slash-less, to match
  // the Starlette route table exactly (every route is registered without a
  // trailing slash - /pricing, /about, /map, ...). trailingSlash: true was
  // tried and reverted: it made every internal link a trailing-slash URL
  // that had to 307 through Starlette's redirect_slashes to reach its
  // canonical (slash-less) route, and it broke canonical/og:url on the
  // pricing page (declared .../pricing/, which itself then redirected).
  // With trailingSlash: false, the export emits a flat "<page>.html"
  // sibling file per route instead of "<page>/index.html" (confirmed
  // against node_modules/next/dist/docs/01-app/02-guides/static-exports.md's
  // "Deploying" section). _site_response in app.py now serves that flat
  // layout directly, falling back to the nested layout if the flat file is
  // absent.
  trailingSlash: false,
  images: { unoptimized: true },
  // Local-only pages (app/lab/**/page.lab.tsx) and dev stand-ins for API
  // routes not yet deployed (route.lab.ts). The "lab.*"
  // extension is recognised only by the dev server, so production builds
  // and the static export never contain them.
  pageExtensions:
    process.env.NODE_ENV === "development"
      ? ["tsx", "ts", "jsx", "js", "lab.tsx", "lab.ts"]
      : ["tsx", "ts", "jsx", "js"],
  // site/ has its own package-lock.json, so Turbopack would otherwise
  // infer site/ as the project root and refuse to resolve the shared
  // token sheet at ../src/ca_roads_demo/static/tokens.css (imported
  // from app/globals.css), which lives one level above site/. Widen
  // the root to the repo root so that import resolves.
  //
  // Cost: this also widens Turbopack's filesystem watching scope and
  // reduces cache validation efficiency during `next dev`, since it now
  // has to consider the whole repo root instead of just site/. This repo
  // root contains a large .venv/ and other heavy directories, so expect
  // `next dev` to start slower and use more file watchers here than in a
  // plain single-app checkout, especially on Windows.
  turbopack: {
    root: path.join(__dirname, ".."),
  },
  // Dev only: /map, /watch and /trip are served by the Python app in
  // production, so the Next dev server 404s on them. Proxy them, and the
  // /static and /api paths they load, to the live site so the preview
  // works end to end. The key is absent from production builds, so the
  // static export (which cannot use rewrites) is unaffected.
  ...(process.env.NODE_ENV === "development"
    ? {
        async rewrites() {
          const live = "https://commutescout.com";
          return [
            "/map",
            "/watch",
            "/trip",
            "/health",
            "/sw.js",
            "/logo.svg",
            "/static/:path*",
            "/api/:path*",
          ].map((source) => ({ source, destination: live + source }));
        },
      }
    : {}),
};

export default nextConfig;
