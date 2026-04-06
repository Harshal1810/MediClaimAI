import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    // Some Windows environments block `child_process.spawn()` (EPERM). Next can
    // use worker threads instead of child processes for its internal workers.
    // Render builds run on Linux; keep this Windows-only to avoid experimental
    // worker serialization issues during static generation.
    workerThreads: process.platform === "win32",
  },
};

export default nextConfig;
