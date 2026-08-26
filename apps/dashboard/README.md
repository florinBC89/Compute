# Dashboard (spec §52)

Next.js (App Router) + TypeScript + Tailwind. The three required screens,
nothing more:

**Runs** (`/`) — a table: run, time, computations, reuse %, cost, saved,
status. Backed by `GET /v1/runs` (a list endpoint the spec's Runs table
implies but never defines — added alongside this dashboard, the same way
`POST /v1/runs` and the `/explain` endpoint were added for §34/§53).

**Run detail** (`/runs/[id]`) — the computation graph. Each node shows name,
HIT/MISS/STALE/FORCED/FAILED, cost, saved, latency, tokens. Backed by
`GET /v1/runs/{id}` and `GET /v1/runs/{id}/graph`.

**Project metrics** (`/metrics`) — total spend, estimated savings, reuse
rate, tokens avoided, LLM calls avoided. Backed by
`GET /v1/projects/{slug}/metrics`.

## Running it

```bash
npm install
npm run dev
```

With no environment variables set, the dashboard renders bundled demo data
shaped exactly like the research-agent benchmark's NVDA workflow (same ten
computations, same dependency graph) — a visible "Demo data" pill in the top
nav makes this explicit rather than silently faking a connection. To point it
at a real API:

```bash
cp .env.example .env.local
# then edit COMPUTELAYER_API_URL / _API_KEY / _PROJECT
```

The API is CORS-enabled for `http://localhost:3000` (`CORS_ORIGINS` in the
API's `.env`).

## Design

Rounded white cards on a warm neutral background, a black "meter" card for
the headline reuse-rate dial, one validated accent hue (`#eb6834` light /
`#d95926` dark) used sequentially rather than categorically since most of
this dashboard's charts encode one quantity's magnitude, not several
identities. Cache-status badges (HIT/MISS/STALE/FORCED/FAILED) use the
project's fixed status palette — icon plus label, never color alone. The
cost-breakdown rings and the run graph's node layout are both computed
(area-true radii; longest-path layering for the DAG), not hand-tuned.

Light and dark are both implemented (`prefers-color-scheme` + a `data-theme`
override hook); the reference mockups were light-only, so light is the
primary target.
