import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

const nextConfig: NextConfig = {
  experimental: {
    serverActions: {
      // Uploads travel to the server as Server Action bodies, and the default
      // ceiling is 1 MB — well under the 25 MB the platform advertises and the
      // API enforces. Anything larger never left the browser, and failed
      // without reaching any of our code, so nothing could report it.
      bodySizeLimit: "25mb",
    },
  },
};

export default withNextIntl(nextConfig);
