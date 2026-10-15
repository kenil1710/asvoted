import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      { source: "/checks", destination: "/", permanent: false },
      { source: "/how-it-works", destination: "/docs", permanent: true },
    ];
  },
};

export default nextConfig;
