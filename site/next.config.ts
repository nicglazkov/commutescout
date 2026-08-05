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
  turbopack: {
    root: path.join(__dirname, ".."),
  },
};

export default nextConfig;
