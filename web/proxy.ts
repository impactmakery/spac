import createIntlMiddleware from "next-intl/middleware";
import type { NextRequest } from "next/server";
import { routing } from "./i18n/routing";

const intl = createIntlMiddleware(routing);

export function proxy(request: NextRequest) {
  return intl(request);
}

export const config = {
  // Skip API routes, Next internals, and static files.
  matcher: "/((?!api|_next|_vercel|.*\\..*).*)",
};
