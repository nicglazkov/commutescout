import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // Static export: the build writes plain HTML/CSS/JS to out/, which the
  // Python app serves. No Node runs in production.
  output: "export",
  // The exported pages are served from the site root by Starlette.
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
