# Next.js Frontend Security Patterns

Read this when working on: Next.js App Router routes, server actions, route handlers, middleware, auth state management, fetch wrappers, login UI, protected pages, CSP, cookie handling, CSRF.

## Table of contents

1. Token storage model
2. The fetch wrapper (auto-refresh)
3. Server-side session validation
4. Middleware for route protection
5. CSRF defense
6. Content Security Policy
7. Cookie flags
8. Client/server boundary rules
9. Error handling on the client

---

## 1. Token storage model

This is the most contested topic in frontend security. The chosen model for SPEC FORGE:

- **Access token** → React state / context, in memory only. Lost on refresh; that's fine — the refresh token re-issues it.
- **Refresh token** → httpOnly cookie, `Secure`, `SameSite=Lax`, path=`/api/auth`.

**Never use `localStorage` or `sessionStorage` for tokens.** Any XSS in the app or any third-party script reads them. The httpOnly cookie is invisible to JS.

```typescript
// lib/auth/AuthContext.tsx
"use client";
import { createContext, useContext, useState, useEffect } from "react";

type AuthState = {
  accessToken: string | null;
  user: User | null;
  setAccessToken: (t: string | null) => void;
  setUser: (u: User | null) => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);

  // On mount, try to refresh — restores session if refresh cookie is valid
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/auth/refresh", {
          method: "POST",
          credentials: "include",
        });
        if (res.ok) {
          const { access_token } = await res.json();
          setAccessToken(access_token);
          const me = await fetch("/api/me", {
            headers: { Authorization: `Bearer ${access_token}` },
          }).then(r => r.json());
          setUser(me);
        }
      } catch {
        // Not logged in — leave state null
      }
    })();
  }, []);

  return (
    <AuthContext.Provider value={{ accessToken, user, setAccessToken, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be inside AuthProvider");
  return ctx;
}
```

## 2. The fetch wrapper (auto-refresh on 401)

```typescript
// lib/api/client.ts
import { useAuth } from "@/lib/auth/AuthContext";

let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;  // dedupe concurrent refreshes
  refreshInFlight = (async () => {
    try {
      const res = await fetch("/api/auth/refresh", {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) return null;
      const { access_token } = await res.json();
      return access_token;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

export function makeApiClient(getToken: () => string | null, setToken: (t: string | null) => void) {
  return async function apiFetch(input: string, init: RequestInit = {}) {
    const doFetch = (token: string | null) =>
      fetch(input, {
        ...init,
        credentials: "include",
        headers: {
          ...init.headers,
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });

    let res = await doFetch(getToken());
    if (res.status !== 401) return res;

    // Try refresh once
    const newToken = await refreshAccessToken();
    if (!newToken) {
      setToken(null);
      // Redirect to login or surface auth error
      window.location.href = "/login";
      return res;
    }
    setToken(newToken);
    res = await doFetch(newToken);
    return res;
  };
}
```

Usage in a component:
```typescript
const { accessToken, setAccessToken } = useAuth();
const api = useMemo(() => makeApiClient(() => accessToken, setAccessToken), [accessToken]);

const data = await api("/api/projects").then(r => r.json());
```

## 3. Server-side session validation

For SSR / server components that need user context, validate the refresh cookie server-side rather than relying on client state.

```typescript
// lib/auth/server.ts
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export async function getServerUser(): Promise<User | null> {
  const refreshToken = (await cookies()).get("refresh_token")?.value;
  if (!refreshToken) return null;

  const res = await fetch(`${process.env.API_INTERNAL_URL}/api/auth/refresh`, {
    method: "POST",
    headers: { Cookie: `refresh_token=${refreshToken}` },
    cache: "no-store",
  });
  if (!res.ok) return null;

  const { access_token } = await res.json();
  const me = await fetch(`${process.env.API_INTERNAL_URL}/api/me`, {
    headers: { Authorization: `Bearer ${access_token}` },
    cache: "no-store",
  });
  if (!me.ok) return null;
  return me.json();
}

export async function requireServerUser(): Promise<User> {
  const user = await getServerUser();
  if (!user) redirect("/login");
  return user;
}
```

Usage in a server component:
```typescript
// app/(dashboard)/page.tsx
import { requireServerUser } from "@/lib/auth/server";

export default async function Dashboard() {
  const user = await requireServerUser();
  return <h1>Welcome, {user.display_name}</h1>;
}
```

Note: this makes one refresh call per SSR. If that's expensive, cache the result in a server-side per-request memo, but **never** cache across requests.

## 4. Middleware for route protection

For coarse-grained gating (logged-in vs not), use Next.js middleware. Don't put fine-grained role checks here — those go in the backend.

```typescript
// middleware.ts
import { NextRequest, NextResponse } from "next/server";

const PUBLIC_ROUTES = ["/login", "/signup", "/password-reset", "/"];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (PUBLIC_ROUTES.includes(pathname) || pathname.startsWith("/_next")) {
    return NextResponse.next();
  }

  const hasRefresh = req.cookies.has("refresh_token");
  if (!hasRefresh) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("redirect", pathname);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
```

This is UX-level: even if a user bypasses the redirect, the backend still rejects requests without a valid access token. **The backend is the source of truth.**

## 5. CSRF defense

Because the refresh cookie is auto-sent on cross-site requests by default, you need CSRF protection on state-changing endpoints that rely on cookie auth.

**Two-layer defense:**

**Layer 1 — `SameSite=Lax` (or `Strict`) on cookies.** Modern browsers reject cross-site cookie sends for `POST`/`PUT`/`DELETE` with `SameSite=Lax`. This blocks the vast majority of CSRF.

**Layer 2 — Double-submit token** for endpoints where the refresh cookie is used.

```python
# Backend — issue CSRF cookie on login + refresh
csrf_token = secrets.token_urlsafe(32)
response.set_cookie(
    "csrf_token",
    csrf_token,
    httponly=False,  # readable by JS — that's the point
    secure=True,
    samesite="lax",
    path="/",
)
```

```python
# Backend — verify on state-changing endpoints
async def verify_csrf(request: Request):
    cookie_token = request.cookies.get("csrf_token")
    header_token = request.headers.get("X-CSRF-Token")
    if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(403, "CSRF token mismatch")
```

Apply to `/api/auth/refresh`, `/api/auth/logout`, and any cookie-authenticated mutation. (For Bearer-token endpoints, the attacker can't forge the `Authorization` header cross-origin, so CSRF is moot — but the refresh endpoint reads the cookie, so it needs CSRF.)

```typescript
// Frontend — read csrf cookie and send as header
function getCsrfToken(): string | null {
  const match = document.cookie.match(/(?:^|; )csrf_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

await fetch("/api/auth/refresh", {
  method: "POST",
  credentials: "include",
  headers: {
    "X-CSRF-Token": getCsrfToken() ?? "",
  },
});
```

**Alternative**: origin/referer header check on the backend. Cheaper but slightly less robust.

## 6. Content Security Policy

CSP in Next.js is set via the response headers in `next.config.js` or a middleware. Build a strict policy and relax only where needed.

```javascript
// next.config.js
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",   // 'unsafe-inline' needed for Next.js hydration; use nonces if upgrading
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: https://your-s3-bucket.s3.amazonaws.com",
  "font-src 'self' data:",
  "connect-src 'self' https://api.spec-forge.example.com",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

module.exports = {
  async headers() {
    return [{
      source: "/(.*)",
      headers: [
        { key: "Content-Security-Policy", value: csp },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      ],
    }];
  },
};
```

For Next.js apps that use inline scripts heavily, use a nonce-based CSP via middleware — it's more work but materially stronger. For SPEC FORGE's current scope, the above is acceptable.

## 7. Cookie flags

Every cookie set by the backend MUST have:
- `httponly=True` (unless explicitly needed by JS — e.g., CSRF token)
- `secure=True` (HTTPS only)
- `samesite="lax"` (default) or `"strict"` (for highly sensitive)
- `path=` scoped narrowly (e.g., `/api/auth` for refresh token)
- `max_age=` explicit

```python
response.set_cookie(
    "refresh_token",
    token,
    httponly=True,
    secure=True,
    samesite="lax",
    path="/api/auth",
    max_age=7 * 24 * 3600,
)
```

`SameSite=Strict` would prevent the cookie from being sent when the user follows a link from another site to the app, breaking SSO-like flows. `Lax` is the standard tradeoff.

## 8. Client/server boundary rules

- **Never** expose backend secrets to the client. Env vars without the `NEXT_PUBLIC_` prefix are server-only. **Anything with `NEXT_PUBLIC_` is shipped to the browser** — treat it as public.
- **Never** call third-party APIs that require secret keys from the client. Proxy through a Next.js route handler.
- **Never** trust client-side validation alone. Mirror every constraint server-side.
- Server components, route handlers, and server actions can hold secrets. Client components cannot.

```typescript
// app/api/imagen/route.ts — server-side proxy
import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  // Validate caller's session first
  const user = await getServerUser();
  if (!user) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const body = await req.json();
  // Call Google Imagen with server-only key
  const res = await fetch("https://aiplatform.googleapis.com/...", {
    method: "POST",
    headers: { Authorization: `Bearer ${process.env.GOOGLE_API_KEY}` },
    body: JSON.stringify(body),
  });
  return NextResponse.json(await res.json());
}
```

## 9. Error handling on the client

- Never display raw error responses from the backend — they may contain internal details.
- Surface generic messages with the `correlation_id` for support.
- Log client errors to a monitoring service (Sentry, Datadog RUM), not to console in production.

```typescript
try {
  const res = await api("/api/projects", { method: "POST", body: JSON.stringify(data) });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    showToast({
      type: "error",
      title: "Couldn't create project",
      message: `If this persists, contact support with ID: ${err.correlation_id ?? "n/a"}`,
    });
    return;
  }
} catch (e) {
  reportError(e);
  showToast({ type: "error", title: "Network error" });
}
```

## Quick checklist for any Next.js auth-touching code

- [ ] Access token stays in memory; never written to localStorage/sessionStorage.
- [ ] Refresh token is httpOnly cookie, set by backend, not readable by JS.
- [ ] All `fetch` to backend includes `credentials: "include"` when cookies are needed.
- [ ] CSRF token sent as `X-CSRF-Token` header on state-changing cookie-auth requests.
- [ ] Public env vars (`NEXT_PUBLIC_*`) contain nothing sensitive.
- [ ] Server-only calls to third-party APIs happen in route handlers or server components.
- [ ] Middleware redirect is UX only — backend enforces auth.
- [ ] Error toasts show generic message + correlation ID, never raw backend error.
