# Invalidation

## What invalidates a computation

Everything in the fingerprint (§15):

- the computation name
- any normalized input
- any dependency version
- the model
- the prompt (`prompt_hash`)
- the tool schemas (`tool_schema_hash`)
- the code version (`COMPUTELAYER_CODE_VERSION`)

And, separately from the fingerprint:

- TTL expiry — `expires_at <= now()`
- `reusable = false`
- `status != SUCCEEDED`

## What does *not* invalidate it

- dictionary key order
- whitespace or JSON formatting
- object identity or `repr`
- timezone representation of an equal instant
- an upstream that re-executed and produced the same output

That last one is the whole point.

## Propagation

Given `A → B → C`, suppose `A` is recomputed.

```
A.output_hash unchanged   →  B fingerprint unchanged  →  B HIT  →  C HIT
A.output_hash changed     →  B STALE, B executes
                             B.output_hash unchanged   →  C HIT
                             B.output_hash changed     →  C STALE
```

Invalidation stops at the first computation whose output did not actually move.
This is mandatory behaviour (§19), and it is what makes the difference between
"re-run the whole graph because one fixture changed" and "re-run the two nodes
that actually depend on the change".

## TTL

TTL is supplementary, not a substitute for dependencies:

```python
await cl.compute.run(name="latest_news", ttl=3600, ...)
```

A computation is reusable only if `reusable = true` **and**
`status = SUCCEEDED` **and** (`expires_at IS NULL` or `expires_at > now()`).
Lowering a `ttl=` argument takes effect on the next lookup rather than the next
write: the lookup applies the tighter of the two.

## Forcing

```python
await cl.compute.run(name="latest_news", force=True, ...)
```

Executes regardless, and the result becomes the latest valid computation.

## Debugging

```bash
computelayer explain <computation_id>
```

```
financial_analysis was recomputed because:

  dependency
    financials:NVDA
  changed:
    old:
      943fa1...
    new:
      03ec22...
```
