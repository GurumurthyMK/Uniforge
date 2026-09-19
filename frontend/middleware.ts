import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/** UX-level gate for /app/*. The API enforces real authorization per request;
 *  this only redirects obviously-anonymous browsers to /login sooner. */
export function middleware(req: NextRequest) {
  const token = req.cookies.get("uf_token")?.value;
  if (!token) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/app/:path*"],
};
