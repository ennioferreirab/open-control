import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  webpack: (config) => {
    config.watchOptions = {
      ...config.watchOptions,
      // Enable polling for Docker on macOS (bind mount FS events unreliable)
      poll: process.env.WATCHPACK_POLLING ? 1000 : undefined,
      ignored: [
        ...(Array.isArray(config.watchOptions?.ignored) ? config.watchOptions.ignored : []),
        "**/convex/_generated/**",
        "**/node_modules/**",
      ],
    };
    return config;
  },
};

export default nextConfig;
