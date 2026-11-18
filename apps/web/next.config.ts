import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  // A self-contained server bundle for the Docker image.
  output: "standalone",
  // Inside the Docker image only: skip the type check to keep `next build` within a small
  // Docker VM. CI runs `tsc --noEmit` and eslint separately. (Next 16 no longer lints in
  // `next build`, so there is no eslint switch to set.)
  typescript: { ignoreBuildErrors: process.env.DOCKER_BUILD === "1" },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default createNextIntlPlugin("./src/i18n/request.ts")(nextConfig);
