# Story 7.4: Implement Access Token Authentication

Status: done

## Story

As a **user**,
I want the dashboard to require an access token when configured,
So that my Mission Control instance is not accessible to anyone on the network.

## Acceptance Criteria

1. **Given** the `MC_ACCESS_TOKEN` environment variable is set, **When** the user navigates to `localhost:3000` without a valid session, **Then** they are redirected to `/login` — a page with an access token input field
2. **Given** the login page is displayed, **Then** it uses ShadCN components (Card, Input, Button) consistent with the design system
3. **Given** the user enters the correct access token, **When** they submit the form, **Then** a cookie-based session is created (NFR19) and they are redirected to the main dashboard
4. **Given** the user enters the correct access token, **Then** subsequent requests are authenticated via the session cookie without re-prompting
5. **Given** the user enters an incorrect token, **When** they submit the form, **Then** an error message displays: "Invalid access token" and no session is created
6. **Given** `MC_ACCESS_TOKEN` is NOT set, **When** the user navigates to `localhost:3000`, **Then** the dashboard loads directly without authentication (localhost convenience mode)
7. **And** `dashboard/middleware.ts` validates the session token on all routes except `/login`
8. **And** `dashboard/app/login/page.tsx` is created with the token input form
9. **And** Convex deployment key authenticates the Python SDK (separate from dashboard auth)
10. **And** Vitest tests exist for the login page component

## Tasks / Subtasks

- [ ] Task 1: Create Next.js API route for token validation (AC: #3, #4, #5)
  - [ ] 1.1: Create `dashboard/app/api/auth/route.ts` with a POST handler
  - [ ] 1.2: POST handler reads `MC_ACCESS_TOKEN` from `process.env`
  - [ ] 1.3: Compare submitted token against the environment variable
  - [ ] 1.4: If match, set an `HttpOnly` cookie (`mc_session`) with a signed value and return 200
  - [ ] 1.5: If mismatch, return 401 with `{ error: "Invalid access token" }`
  - [ ] 1.6: Cookie should be `Secure` only in production (not on localhost), `SameSite=Lax`, `Path=/`

- [ ] Task 2: Create the login page (AC: #1, #2, #5, #8)
  - [ ] 2.1: Create `dashboard/app/login/page.tsx` with `"use client"` directive
  - [ ] 2.2: Render a centered Card with: heading "Mission Control", subheading "Enter your access token", token Input (type="password"), Submit Button
  - [ ] 2.3: Use ShadCN `Card`, `CardHeader`, `CardContent`, `Input`, `Button`, `Label`
  - [ ] 2.4: On form submit, POST to `/api/auth` with the token
  - [ ] 2.5: If 200 response, redirect to `/` using `router.push("/")`
  - [ ] 2.6: If 401 response, show error message "Invalid access token" below the input in `text-red-500 text-sm`
  - [ ] 2.7: Disable the button and show loading state during submission
  - [ ] 2.8: Support Enter key submission

- [ ] Task 3: Create middleware for route protection (AC: #1, #6, #7)
  - [ ] 3.1: Create `dashboard/middleware.ts` using Next.js middleware API
  - [ ] 3.2: Check if `MC_ACCESS_TOKEN` is set in `process.env` — if not, allow all requests (convenience mode)
  - [ ] 3.3: If token is configured, check for valid `mc_session` cookie on every request
  - [ ] 3.4: Exclude `/login`, `/api/auth`, `/_next/*`, `/favicon.ico` from protection
  - [ ] 3.5: If no valid session cookie, redirect to `/login`
  - [ ] 3.6: Export `config.matcher` to specify which paths the middleware applies to

- [ ] Task 4: Add logout capability (AC: #4)
  - [ ] 4.1: Create `dashboard/app/api/auth/logout/route.ts` with a POST handler
  - [ ] 4.2: Clear the `mc_session` cookie and return 200
  - [ ] 4.3: Optionally add a logout button to the DashboardLayout header (low priority for MVP)

- [ ] Task 5: Write Vitest tests (AC: #10)
  - [ ] 5.1: Create `dashboard/app/login/LoginPage.test.tsx`
  - [ ] 5.2: Test login page renders with token input and submit button
  - [ ] 5.3: Test submitting with correct token redirects to dashboard
  - [ ] 5.4: Test submitting with incorrect token shows error message
  - [ ] 5.5: Test Enter key triggers form submission
  - [ ] 5.6: Test button shows loading state during submission

## Dev Notes

### Critical Architecture Requirements

- **Simple access token, not a full auth system**: This is MVP access control for localhost deployment. No user accounts, roles, or sessions in a database. The token is a shared secret in an environment variable.
- **Convenience mode**: When `MC_ACCESS_TOKEN` is not set, the dashboard is fully open. This is the default for local development.
- **Cookie-based session**: After the user enters the correct token once, a session cookie persists so they don't need to re-enter it on every page load. The cookie is validated by middleware.
- **Separate from Convex auth**: The Python SDK authenticates to Convex via the deployment key. Dashboard auth is independent — it's a gate on the Next.js frontend, not on Convex queries.
- **No need for JWT or complex tokens**: A simple HMAC-signed cookie value is sufficient. The middleware checks that the cookie was signed with the same secret.

### Session Cookie Pattern

Use a simple approach: hash the access token to create a session value, then verify the cookie contains the correct hash.

```typescript
// dashboard/app/api/auth/route.ts
import { NextRequest, NextResponse } from "next/server";
import { createHash } from "crypto";

const TOKEN_COOKIE_NAME = "mc_session";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 7; // 7 days

function hashToken(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}

export async function POST(request: NextRequest) {
  const { token } = await request.json();
  const expectedToken = process.env.MC_ACCESS_TOKEN;

  if (!expectedToken) {
    return NextResponse.json({ error: "Auth not configured" }, { status: 500 });
  }

  if (token !== expectedToken) {
    return NextResponse.json({ error: "Invalid access token" }, { status: 401 });
  }

  const sessionValue = hashToken(expectedToken);
  const response = NextResponse.json({ success: true });
  response.cookies.set(TOKEN_COOKIE_NAME, sessionValue, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: COOKIE_MAX_AGE,
  });

  return response;
}
```

### Middleware Pattern

```typescript
// dashboard/middleware.ts
import { NextRequest, NextResponse } from "next/server";
import { createHash } from "crypto";

const TOKEN_COOKIE_NAME = "mc_session";

function hashToken(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}

export function middleware(request: NextRequest) {
  const accessToken = process.env.MC_ACCESS_TOKEN;

  // Convenience mode: no token configured, allow everything
  if (!accessToken) {
    return NextResponse.next();
  }

  const sessionCookie = request.cookies.get(TOKEN_COOKIE_NAME)?.value;
  const expectedHash = hashToken(accessToken);

  if (sessionCookie === expectedHash) {
    return NextResponse.next();
  }

  // No valid session — redirect to login
  const loginUrl = new URL("/login", request.url);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - /login (login page itself)
     * - /api/auth (auth API route)
     * - /_next (Next.js internals)
     * - /favicon.ico
     */
    "/((?!login|api/auth|_next|favicon\\.ico).*)",
  ],
};
```

### Login Page Pattern

```tsx
// dashboard/app/login/page.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

export default function LoginPage() {
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });

      if (res.ok) {
        router.push("/");
      } else {
        const data = await res.json();
        setError(data.error || "Invalid access token");
      }
    } catch {
      setError("Connection failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-slate-50">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle>Mission Control</CardTitle>
          <p className="text-sm text-slate-500">Enter your access token</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="token">Access Token</Label>
              <Input
                id="token"
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Enter token..."
                disabled={loading}
              />
            </div>
            {error && <p className="text-red-500 text-sm">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Authenticating..." : "Sign In"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
```

### Environment Variable Configuration

The `MC_ACCESS_TOKEN` variable is already defined in `.env.example`:

```
# Optional: Access token for dashboard authentication
# If not set, dashboard runs without authentication (localhost mode)
MC_ACCESS_TOKEN=
```

When set in `.env.local`, the middleware activates and requires authentication. When empty or absent, the dashboard is fully open.

### Common LLM Developer Mistakes to Avoid

1. **DO NOT use Convex Auth or a third-party auth library** — This is a simple shared-secret access token, not a user authentication system. No database sessions, no user accounts.

2. **DO NOT store the session in Convex** — The session is a cookie on the browser. Middleware validates it on each request. No server-side session store needed.

3. **DO NOT protect Convex queries/mutations** — Dashboard auth is a Next.js middleware concern. Convex queries are authenticated via the deployment key, not the access token.

4. **DO NOT make the login page a client component that wraps ConvexProvider** — The login page does NOT need Convex. It's a simple form that POSTs to a Next.js API route.

5. **DO NOT forget convenience mode** — When `MC_ACCESS_TOKEN` is not set, the middleware MUST allow all requests through. No authentication prompt in dev mode by default.

6. **DO NOT use `localStorage` for the session** — Use an `HttpOnly` cookie for security. The middleware can read cookies but not localStorage.

7. **DO NOT redirect `/login` to `/login`** — The middleware must exclude the login page and auth API route from protection, or you get an infinite redirect loop.

8. **DO NOT use `next-auth`** — This is not a NextAuth use case. Simple middleware + cookie is sufficient.

### What This Story Does NOT Include

- **User accounts or roles** — Single shared access token for all users
- **Convex-level authentication** — Python SDK uses deployment key separately
- **Token rotation or expiry** — Token is static in the environment variable
- **Multi-user sessions** — One token, one gate
- **OAuth or social login** — Post-MVP

### Files Created in This Story

| File | Purpose |
|------|---------|
| `dashboard/middleware.ts` | Next.js middleware for route protection |
| `dashboard/app/login/page.tsx` | Login page with token input form |
| `dashboard/app/api/auth/route.ts` | API route for token validation + cookie setting |
| `dashboard/app/api/auth/logout/route.ts` | API route for session clearing |
| `dashboard/app/login/LoginPage.test.tsx` | Vitest tests for login page |

### Files Modified in This Story

| File | Changes |
|------|---------|
| (none — all new files) | |

### Verification Steps

1. Set `MC_ACCESS_TOKEN=test123` in `.env.local` — restart dev server
2. Navigate to `localhost:3000` — verify redirect to `/login`
3. Enter wrong token — verify "Invalid access token" error
4. Enter correct token — verify redirect to dashboard
5. Refresh page — verify dashboard loads without re-prompting (cookie session)
6. Clear cookies — verify redirect back to `/login`
7. Remove `MC_ACCESS_TOKEN` from `.env.local` — restart — verify dashboard loads directly
8. Run `cd dashboard && npx vitest run` — tests pass

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 7.4`] — Original story definition
- [Source: `_bmad-output/planning-artifacts/prd.md#NFR19`] — Dashboard requires access token auth
- [Source: `_bmad-output/planning-artifacts/architecture.md#Authentication & Security`] — MVP simple access token pattern
- [Source: `_bmad-output/planning-artifacts/architecture.md#Routing`] — `/login` route defined
- [Source: `dashboard/.env.example`] — MC_ACCESS_TOKEN placeholder already exists

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References
- TypeScript check: `npx tsc --noEmit` — passed clean, zero errors
- Vitest: `npx vitest run app/login/LoginPage.test.tsx` — 5/5 tests passed
- Installed @radix-ui/react-label (new dependency for ShadCN Label component)
- Installed @testing-library/user-event (new dev dependency for tests)

### Completion Notes List
- All 5 tasks from the story completed
- Task 1: Created `app/api/auth/route.ts` — POST handler validates token, sets HttpOnly cookie with SHA-256 hash
- Task 2: Created `app/login/page.tsx` — ShadCN-based login form with loading state, error display, Enter key support
- Task 3: Created `middleware.ts` — route protection with convenience mode (no auth when MC_ACCESS_TOKEN unset)
- Task 4: Created `app/api/auth/logout/route.ts` — clears session cookie
- Task 5: Created `app/login/LoginPage.test.tsx` — 5 Vitest tests covering render, success redirect, error display, Enter key, loading state
- Created `components/ui/label.tsx` — ShadCN Label component (was missing from existing UI components)
- Used `bg-background` instead of `bg-slate-50` on login page to respect dark mode theming

### File List
| File | Action |
|------|--------|
| `dashboard/middleware.ts` | Created — Next.js middleware for route protection |
| `dashboard/app/login/page.tsx` | Created — Login page with token input form |
| `dashboard/app/api/auth/route.ts` | Created — API route for token validation + cookie setting |
| `dashboard/app/api/auth/logout/route.ts` | Created — API route for session clearing |
| `dashboard/app/login/LoginPage.test.tsx` | Created — Vitest tests for login page |
| `dashboard/components/ui/label.tsx` | Created — ShadCN Label component |
| `dashboard/package.json` | Modified — added @radix-ui/react-label, @testing-library/user-event |
