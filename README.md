# ComputeLayer

Deterministic incremental compute for AI agents.

Before an expensive agent step runs, ComputeLayer answers one question:

> Has this exact computation already been performed against the same effective
> inputs and dependencies?

If yes, the prior output is returned. If no, the step executes and its inputs,
dependencies, cost, output and provenance are recorded so the next run can
reuse it.

```python
from computelayer import ComputeLayer

cl = ComputeLayer(api_key="cl_test_...", project="research-agent")

result = await cl.compute.run(
    name="financial_analysis",
    inputs={"company": "NVDA", "financials": financials},
    dependencies=[cl.dep("company:NVDA:financials", version="sha256:abc123")],
    fn=lambda: analyze_financials(financials),
)

result.cache_status   # HIT | MISS | STALE | FORCED
result.value
result.saved_usd
```

---

## What is built

This repository implements milestones 1–6 of §59.

| | |
|---|---|
| **M1** Canonical serialization + hashing | done |
| **M2** Persistence, lookup, start, complete | done, SQL verified |
| **M3** Python SDK — `compute.run()` and `@cl.compute` | done |
| **M4** Dependency graph + output-hash propagation | done |
| **M5** Research benchmark | done, 5/5 scenarios pass |
| **M6** Trace viewer | done — API + Next.js dashboard, see `apps/dashboard/` |

The API layer has been executed end to end against a real PostgreSQL 16 (all
18 `test-api` cases pass; see **Running the API for the first time** below),
though only against a locally-provisioned instance, not yet through the
`docker compose` stack itself. The dashboard renders against that same API,
or against bundled demo data when no API is configured.

## Does it work?

The benchmark (§41–§49) is the answer §61 asks for. Repeated equity research on
`NVDA`, deterministic fixtures, no network:

| | scenario | executed | reused | cost reduction | target |
|---|---|---|---|---|---|
| A | cold run | 10 | 0 | — | baseline |
| B | identical rerun | 0 | 10 | **100.0%** | ≥95% |
| C | news update | 4 | 6 | **55.6%** | ≥40% |
| D | financials update | 4 | 6 | **50.5%** | ≥40% |
| E | upstream churn, stable output | 1 | 9 | **100.0%** | ≥95% |

```bash
make benchmark
```

Scenario E is the load-bearing one: a restated filing forces `financials` to
re-execute, it normalizes to a byte-identical object, and all six downstream
computations stay reusable. One step ran where a dependency-version cache would
have rerun the graph.

Reintroducing the §13 behaviour this implementation deviates from drops B and E
to 0% reduction with every downstream step recomputing — so the benchmark
detects broken propagation rather than rubber-stamping it. Details in
`benchmarks/research-agent/README.md`.

## Quickstart

```bash
git clone <this repo> && cd computelayer
cp .env.example .env
docker compose up            # postgres + redis + api, migrated and seeded
pip install -e packages/python-sdk
```

The API prints a project-scoped key on first start:

```bash
export COMPUTELAYER_API_URL=http://localhost:8000/v1
export COMPUTELAYER_API_KEY=cl_test_local_development_key
export COMPUTELAYER_PROJECT=research-agent
```

No infrastructure at all, for tests and offline work:

```python
cl = ComputeLayer(local=True)   # in-memory backend, identical semantics
```

## Layout

```
apps/api/                FastAPI + SQLAlchemy 2.x over PostgreSQL
apps/dashboard/          §52 — deliberately last (see §60)
packages/python-sdk/     the computelayer package
migrations/              Alembic
benchmarks/              research-agent (M5)
docs/                    concepts, quickstart, dependencies, invalidation
```

## Where the reuse rules live

`computelayer/semantics.py` — one module, pure standard library, imported by
**both** backends:

- `computelayer.testing.LocalBackend`, the in-memory reference implementation
- `apps/api/app/services/lookup.py`, the PostgreSQL implementation

`computelayer/conformance.py` defines the scenarios and the exact cache-status
trace a correct backend must produce, and both test suites run it. If the two
implementations ever disagree, one of them is reusing something it should not,
and the suite fails.

That arrangement exists because of §61: saving 70% while occasionally
returning invalid state is not a product. Saving 35% deterministically is.

## Running the API for the first time

The API is written and reviewed but has never been executed — it was built in an
environment without FastAPI or SQLAlchemy available. Expect to shake out real
bugs on the first run. In order:

```bash
docker compose up                 # postgres, redis, migrations, bootstrap, api
pip install -e packages/python-sdk
pip install -r apps/api/requirements-dev.txt

make test-api                     # the conformance suite against Postgres
```

`apps/api/tests/test_conformance.py` runs the same eight scenarios the reference
backend already passes. When it goes green, the Postgres path provably agrees
with the verified one, and everything downstream rests on solid ground.

## Tests

```bash
make test-sdk        # 80 tests, standard library only
make test-benchmark  # the 5 acceptance scenarios
make test-api        # needs a running Postgres
make test-lookup-sql # reuse SQL against a real database
```

The SDK suite covers every mandatory group in §50 that does not require a
database, including the §51 hashing cases, TTL expiry, failure isolation,
nested computation dependencies, output-hash propagation and a ten-way
stampede.

## Deviations from the specification

Six places where the written spec would not have worked, and what was done
instead. Each is commented at the site.

**1. `computation_id` is excluded from hashed compute references (§13).**
The spec renders an embedded `ComputeResult` as
`{"__compute_ref__": true, "output_hash": ..., "computation_id": ...}`.
`computation_id` is a fresh UUID on every run, so including it in the
fingerprint would make every downstream computation a permanent `MISS` and the
system would never reuse anything. Hashed forms carry `output_hash` only; the
linkage is recorded in `computation_dependencies.source_computation_id`, which
is what §12 asks for anyway.

This one is not a judgement call — reverting it and rerunning the benchmark
takes scenarios B and E from 100% cost reduction to 0%, with every computation
downstream of a nested result recomputing on every run.

**2. Logical keys reduce compute references to the upstream logical key (§16).**
If the logical key used the upstream `output_hash`, a changed upstream would
change the downstream identity too, and lookups would report `MISS` where they
should report `STALE`. Identity uses the upstream logical key, which is stable
across re-executions; the fingerprint uses the output hash. §13's `RefMode`
makes the distinction explicit.

**3. The dependency list in the fingerprint payload (§15).**
The snippet builds a one-element list from a loop variable that is never bound.
Implemented as intended: all dependencies, deduplicated by key, sorted by key.
Declaring one key twice with different versions raises rather than silently
picking a winner.

**4. A previous *failure* yields `MISS`, not `STALE` (§17).**
Step 2 says "if historical computation exists: STALE". A failed attempt
produced no result, so there is nothing for the new computation to be stale
against. Only successful computations make a logical key eligible for `STALE`.

**5. `CHAR(64)` digest columns became `TEXT` + a format check (§6.4).**
Two things went wrong with `CHAR(64)`, both found by running the schema against
PostgreSQL 16 with 200k rows and reading the query plans:

- `CHAR(64)` is `bpchar`, and comparing it against a text parameter — which is
  what any driver sends for a Python `str` — casts the *column* to text and
  makes its index unusable. The lookup fell back to scanning
  `idx_computations_created`: 24.5 ms over 50k rows, growing linearly, against
  the 100 ms p95 budget of §58.
- `CHAR(64)` never enforced that the value is a hex digest anyway.

`TEXT` plus `CHECK (fingerprint ~ '^[0-9a-f]{64}$')` gives the guarantee
`CHAR(64)` only implied, and keeps the indexes usable.

The same exercise turned up a second latency bug, this one purely ours: the
lookup was written with SQLAlchemy's `.is_(True)`, which emits
`reusable IS TRUE`. PostgreSQL does not prove that this implies a partial index
predicated on `reusable = TRUE`, so it silently chose a sequential scan. Fixed
in `services/lookup.py`, and the reason is commented there so nobody
"simplifies" it back.

Measured on PostgreSQL 16, 200k computations, after both fixes:

| lookup | plan | time |
|---|---|---|
| exact fingerprint, hit | index scan | 0.040 ms |
| exact fingerprint, miss | index scan | 0.024 ms |
| logical key (STALE detection) | index scan | 0.025 ms |

**6. "Newest" is resolved by a monotonic `seq`, not by `created_at`.**
`created_at` defaults to `now()`, which in PostgreSQL is *transaction* time —
every row written in a single transaction carries an identical value. With
`ORDER BY created_at DESC LIMIT 1` the sort is then unstable, and on tied
timestamps the database returned the **older** row on all eight attempts. That
breaks §21: a forced recomputation is supposed to become the latest valid
computation, and silently wouldn't. `computations.seq` is a `BIGINT IDENTITY`,
both partial indexes lead with it, and both lookups order by it.

Two things about this one are worth noting. It is invisible to the Python
suite — the in-memory backend was always correct here, because it happens to
tie-break on an insertion counter — so the conformance suite could not have
caught it. And `apps/api/tests/lookup_semantics.sql` now pins all nine cases
against a real database, including the tie:

```bash
createdb computelayer_lookup_check
psql -d computelayer_lookup_check -v ON_ERROR_STOP=1 \
     -f migrations/schema.sql -f apps/api/tests/lookup_semantics.sql
```

Additions the spec implies but does not define: `POST /v1/runs` and
`POST /v1/runs/{id}/finish` (the `runs` table exists and every endpoint takes a
`run_id`, but nothing opens one); an `api_keys` table (§56 requires hashed,
project-scoped keys); `GET /v1/computations/{id}/explain` (§53 specifies the
CLI output but no endpoint); `POST /v1/computations/lookup` recording the
hit it just served, so `GET /v1/runs/{id}` can report a reuse rate without a
second round-trip on the hot path; and `GET /v1/runs` (a run *list*, since
§52's Runs table needs one and the spec only ever defines
`GET /v1/runs/{id}`).

## What V0.1 is judged on

Not features, integrations or stars (§61). One experiment: take a real
multi-step agent workflow, run it repeatedly as inputs evolve, and compare how
much compute *should* logically remain reusable against how much ComputeLayer
actually reuses.

```
Correct reuse rate                 > 95%
Incorrect reuse                      0%
Cost reduction on incremental runs > 30%
```

The second line is the one that matters.

## License

MIT
