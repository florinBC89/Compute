# Workspace (V0.2 human workspace slice)

Next.js (App Router) + TypeScript + Tailwind + Supabase Auth. The
non-technical, consumer-facing counterpart to `apps/dashboard` (which stays
the engineer-facing surface, unauthenticated, one API key baked in per
deploy). This app has real per-user login instead — a fully separate app
rather than a route added to the dashboard, since bolting multi-user
sessions onto an app built around a single server-side API key would have
been the bigger, riskier change.

**Phase 2 scope** (see `/Users/florinbostan/.claude/plans/jolly-sniffing-conway.md`):
login only. Magic-link sign-in (`/login`) → a protected shell (`/`) that
calls the API's `GET /v1/me`, proving a Supabase session reaches the API and
resolves to a real, auto-provisioned workspace. Task input, the project
tree, and the result screen are later phases, once the job/worker/SSE
plumbing and the real research pipeline exist to back them.

## Running it

```bash
npm install
cp .env.example .env.local
# fill in NEXT_PUBLIC_SUPABASE_URL / _PUBLISHABLE_KEY from
# Settings -> API in your Supabase project
npm run dev
```

Runs on port 3200 (apps/dashboard already uses 3000). The API
(`COMPUTELAYER_API_URL`) must have a matching `SUPABASE_URL` configured —
see the root `.env.example` — since it verifies the same project's JWTs.

Add `http://localhost:3200/auth/callback` (and the deployed URL's
equivalent) to Supabase's Auth → URL Configuration → Redirect URLs, or the
magic-link callback will be rejected.

## Auth

`@supabase/ssr`, following Supabase's current App Router guidance:
`lib/supabase/client.ts` (browser), `lib/supabase/server.ts` (Server
Components / Route Handlers / Server Actions), `lib/supabase/middleware.ts`
(session refresh + route protection via `getClaims()`, which verifies the
JWT locally on every request rather than trusting the cookie unread). No
password: `app/login/actions.ts` sends a magic link instead — the spec's
whole premise is that a researcher or writer "should not need to understand
APIs ... or caching," and a password to remember/reset is exactly that kind
of incidental complexity.
