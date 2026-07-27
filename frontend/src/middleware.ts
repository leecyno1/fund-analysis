/**
 * Middleware to handle API requests
 * Note: Trailing slash handling is done in the route handler, not here
 */
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  // All API requests pass through to route handlers
  return NextResponse.next()
}

export const config = {
  matcher: ['/api/:path*'],
}