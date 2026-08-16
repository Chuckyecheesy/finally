import path from "node:path";
import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";

// Production is a static export served by FastAPI on the same origin, so
// `/api/*` needs no proxying there. The dev server has no backend behind it,
// hence the rewrite — declared only in dev, since an export ignores rewrites.
const devOnly = isDev
  ? {
      async rewrites() {
        return [{ source: "/api/:path*", destination: "http://localhost:8000/api/:path*" }];
      },
    }
  : { output: "export" as const };

const nextConfig: NextConfig = {
  ...devOnly,
  images: { unoptimized: true },
  outputFileTracingRoot: path.join(import.meta.dirname, ".."),
};

export default nextConfig;
