import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // Static export: the build writes plain HTML/CSS/JS to out/, which the
  // Python app serves. No Node runs in production.
  output: "export",
  // Ruling (Task 8 fix round 1, Nic): served URLs are slash-less, to match
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
};

export default nextConfig;
