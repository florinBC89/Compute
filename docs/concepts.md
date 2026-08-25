# Concepts

## Computation

The central abstraction (§2). A computation has an identity, inputs,
dependencies, an execution definition, an output, a status, a cost and
provenance.

```python
result = await cl.compute.run(
    name="analyze_financials",
    inputs={"company": "NVDA", "period": "FY2025"},
    dependencies=[cl.dep("financials:NVDA", version="sha256:abc123")],
    fn=analyze_financials,
)
```

## Fingerprint vs logical key

Two hashes, two different questions.

**Fingerprint** — *is this exact computation reusable?* It covers the name, the
normalized inputs, every dependency version, and the execution parameters:
model, prompt hash, tool schema hash, code version. Any of those moving means
the stored result no longer describes what you are asking for.

**Logical key** — *is there an older version of this same logical computation?*
It covers the name and the identity inputs only. It is what separates `STALE`
(you have run this before, the world moved) from `MISS` (you have never run
this).

The distinction matters most for nested computations. When an upstream result
is embedded in your inputs, the fingerprint sees its **output hash** and the
logical key sees its **logical key**. So an upstream that re-executes still
counts as the same downstream computation — just an outdated one.

## Execution states

| | |
|---|---|
| `HIT` | An identical valid computation exists. Nothing executes. |
| `MISS` | Nothing matching exists. The function executes. |
| `STALE` | A previous version exists but something changed. The function executes. |
| `FORCED` | Recomputation was explicitly requested. |
| `FAILED` | Execution failed. Never reused. |

## Output hashing

Every successful result is hashed. This is what makes change propagation cheap:
a computation can execute again and produce the *same* output, in which case
nothing downstream needs to move.

```
raw market data changed
        ↓
normalized rental yield remains 5.40%
        ↓
output hash unchanged
        ↓
downstream computations stay HIT
```

## Resources

Versioned external state, tracked separately from computations:

```
company:NVDA:profile
company:NVDA:financials
market:semiconductors
document:10k:NVDA:2025
```

`POST /v1/resources/upsert` returns `changed: true|false`, so an agent can skip
a branch before computing a fingerprint at all.
