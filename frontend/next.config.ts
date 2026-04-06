import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    // Some Windows environments block `child_process.spawn()` (EPERM). Next can
    // use worker threads instead of child processes for its internal workers.
    workerThreads: true,
  },
};

export default nextConfig;
