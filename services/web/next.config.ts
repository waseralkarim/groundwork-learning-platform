import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produces a self-contained server bundle. The runtime image then needs no
  // node_modules and no package manager — which is most of why it stays small.
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  outputFileTracingRoot: process.cwd(),
};

export default nextConfig;
