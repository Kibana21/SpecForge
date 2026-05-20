import { NextRequest, NextResponse } from 'next/server'

const PUBLIC_PATHS = new Set(['/login'])

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl

  // Let static assets and Next.js internals through
  if (
    pathname.startsWith('/_next') ||
    pathname.startsWith('/favicon') ||
    pathname === '/api/auth/login' ||
    pathname === '/api/auth/refresh' ||
    pathname === '/api/auth/password-reset'
  ) {
    return NextResponse.next()
  }

  if (PUBLIC_PATHS.has(pathname)) {
    // If already logged in, redirect to dashboard
    const hasSession = req.cookies.has('refresh_token')
    if (hasSession) {
      const redirect = req.nextUrl.searchParams.get('redirect') ?? '/'
      return NextResponse.redirect(new URL(redirect, req.url))
    }
    return NextResponse.next()
  }

  // Protected routes — check for refresh cookie (UX gate; backend enforces auth)
  const hasSession = req.cookies.has('refresh_token')
  if (!hasSession) {
    const url = req.nextUrl.clone()
    url.pathname = '/login'
    url.searchParams.set('redirect', pathname)
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
