# Research-agent benchmark (M5)

Measures whether incremental computation actually creates significant savings
on a real multi-step agent workflow (§41): repeated equity research on `NVDA`,
where only some information changes between executions.

Deterministic fixtures, a deterministic stand-in for the model, no network. Same
inputs, same numbers, on any machine.

```bash
make benchmark
# or
python benchmarks/research-agent/run_benchmark.py --all --steps
computelayer benchmark research-agent --scenario E
```

Exit code is non-zero if any scenario misses its §49 criteria, so this works as
a CI gate. The same scenarios also run as unit tests (`test_scenarios.py`).

## Results

All five scenarios pass.

| | scenario | executed | reused | cost reduction | target |
|---|---|---|---|---|---|
| A | cold run | 10 | 0 | — | baseline |
| B | identical rerun | 0 | 10 | **100.0%** | ≥95% |
| C | news update | 4 | 6 | **55.6%** | ≥40% |
| D | financials update | 4 | 6 | **50.5%** | ≥40% |
| E | upstream churn, stable output | 1 | 9 | **100.0%** | ≥95% |

Scenario E is the one worth reading twice. A restated filing — reordered keys, a
renamed field, figures in thousands rather than millions — forces `financials`
to re-execute. It normalizes to a byte-identical object, so its output hash does
not move, and all six downstream computations stay reusable. One step ran where
a dependency-version-based cache would have rerun the entire graph.

Absolute figures are small because the fixtures are small: a cold pass is ~6,800
tokens and $0.08 against frontier-model pricing, where a real research agent
carrying retrieved documents would be an order of magnitude larger. The
reductions are what the acceptance criteria are stated in, and those are
scale-invariant.

Latency is **modelled**, not measured — a fixed handshake plus per-output-token
decoding, rather than sleeping through real provider latency. Token counts,
costs, and every reuse decision come from the real code path.

## The negative control

A benchmark that cannot fail proves nothing. Reintroducing the §13 behaviour
this implementation deliberately deviates from — putting `computation_id` inside
the hashed compute reference — produces:

```
scenario B (IDENTICAL_RERUN):              FAIL  executed=6 reused=4
  ! recomputed without cause: competitive_analysis, final_report,
    financial_analysis, news_analysis, overview, valuation
  ! cost reduction 0.0% below the 95% target

scenario E (UPSTREAM_CHURN_STABLE_OUTPUT): FAIL  executed=7 reused=3
  ! cost reduction 0.0% below the 95% target
```

Two things follow. The benchmark detects broken propagation rather than
rubber-stamping it. And the spec as written would have reused nothing downstream
of any nested computation — `computation_id` is a fresh UUID per run, so it
poisons every fingerprint that contains it.

Scenario D is the complementary guard: it changes the figures for real, and
asserts that everything downstream of `financials` *does* recompute. Passing D
and E together is what distinguishes real propagation from a cache that reuses
too eagerly.

## Workflow (§42)

```
                     company_profile
                           │
                           ▼
                        overview
                           │
          ┌────────────────┼──────────────────┐
          ▼                ▼                  ▼
     financials        competitors           news
          │                │                  │
          ▼                ▼                  ▼
 financial_analysis competitive_analysis  news_analysis
          │                │                  │
          └──────────────┬─┴──────────────────┘
                         ▼
                     valuation
                         │
                         ▼
                    final_report
```

Ten computations: four fetches (counted as tool calls) and six analyses (one LLM
call each). §48's sample report shows seven LLM calls; the split here is six,
which changes nothing about the criteria.

Downstream edges are never declared. Passing a `ComputeResult` into another
computation's inputs registers the dependency automatically (§12).

Fixture versions are declared as **dependencies** rather than inputs. §43 lists
them as inputs, but a version identifies external state, not the question being
asked — and modelling them as dependencies is what makes D and E differ *only*
in whether the normalized output changes, which is precisely the thing being
measured.

## How a scenario is measured

Each scenario runs the workflow twice at the same world state:

- **baseline** — against an empty cache, so all ten computations execute. This
  is what the agent costs without ComputeLayer.
- **actual** — against a cache warmed at the *previous* world state.

Measuring the baseline per scenario rather than reusing scenario A's numbers
matters: after a fixture changes, the uncached cost of the run is not the cold
run's cost, and comparing against the wrong figure would flatter the result.

## Files

```
fixtures.py         versioned deterministic sources; the v2→v3 restatement
fake_llm.py         deterministic model stand-in, realistic token accounting
workflow.py         the ten steps wired through compute.run
metrics.py          baseline vs actual accounting (§47) and acceptance (§49)
scenarios.py        A–E
run_benchmark.py    CLI, prints the §48 report
test_scenarios.py   the acceptance criteria as unit tests
```

## Acceptance (§49)

| criterion | where it is checked |
|---|---|
| 1. identical rerun avoids ≥95% | scenario B |
| 2. single-branch update avoids ≥40% | scenarios C, D |
| 3. no reuse when a dependency hash changed | scenario D + SDK suite |
| 4. unchanged output hashes stop invalidation | scenario E |
| 5. failed computations never reused | SDK suite, conformance suite |
| 6. parallel identical executions collapse to one | SDK suite (10-way stampede) |
