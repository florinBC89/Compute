# Dependencies

A dependency is a *versioned* thing a computation relies on. ComputeLayer never
inspects the thing itself — it compares versions.

## Explicit

```python
await cl.compute.run(
    name="analysis",
    inputs={"ticker": "NVDA"},
    dependencies=[cl.dep("financials:NVDA", version="sha256:abc123")],
    fn=analyze,
)
```

Let the SDK hash the content when you have it in hand:

```python
cl.dep("financials:NVDA", content=financials)
```

## Types

`EXTERNAL`, `COMPUTATION`, `FILE`, `API`, `DATABASE`, `MANUAL` (§6.5). V0.1
does not infer any of these automatically except `COMPUTATION` — automatic
instrumentation of database queries, HTTP responses and files is V0.2 (§62).

## Computation-as-dependency

Pass a `ComputeResult` into another computation's inputs and the edge is
recorded for you:

```python
financials = await cl.compute.run(name="financials", inputs={"ticker": "NVDA"}, fn=fetch)
analysis   = await cl.compute.run(name="analysis",
                                  inputs={"ticker": "NVDA", "financials": financials},
                                  fn=analyze)
```

ComputeLayer registers:

```
dependency_type       = COMPUTATION
dependency_version    = financials.output_hash
source_computation_id = financials.computation_id
```

so `financials ──► analysis` exists in the graph without you declaring
anything.

### Why the key is not the computation id

The dependency key is built from the upstream *logical key*, not its
`computation_id`. A `computation_id` is a fresh UUID on every run; using it as
the key would change the downstream fingerprint on every run and nothing would
ever be reused. The id is still recorded — in `source_computation_id`, where it
belongs — and that is what draws the graph.

## One key, one version

Declaring the same dependency key twice with different versions raises
`DuplicateDependencyError`. `computation_dependencies` is unique on
`(computation_id, dependency_key)`, and quietly picking a winner is how a
system starts reusing results it should not.

## Resources

For external state that many computations share, register it once:

```python
changed = await cl.upsert_resource("company:NVDA:financials", content=payload)
if not changed["changed"]:
    ...  # nothing downstream can have moved
```
