import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export: the build writes plain HTML/CSS/JS to out/, which the
  // Python app serves. No Node runs in production.
  output: "export",
  // The exported pages are served from the site root by Starlette.
  trailingSlash: false,
  images: { unoptimized: true },
};

export default nextConfig;
