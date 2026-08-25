# computelayer

Deterministic incremental compute for AI agents.

```python
from computelayer import ComputeLayer

cl = ComputeLayer(api_key="cl_test_...", project="research-agent")

result = await cl.compute.run(
    name="financial_analysis",
    inputs={"company": "NVDA", "financials": financials},
    dependencies=[cl.dep("company:NVDA:financials", version="sha256:abc123")],
    fn=lambda: analyze_financials(financials),
)

print(result.cache_status)  # HIT | MISS | STALE | FORCED
print(result.value)
```

The core package has **no runtime dependencies**. Install extras only for what
you use:

```bash
pip install computelayer          # hashing, fingerprints, local backend
pip install 'computelayer[http]'  # talk to a ComputeLayer API
pip install 'computelayer[all]'   # + Redis stampede locking
```

Offline mode needs no infrastructure at all:

```python
cl = ComputeLayer(local=True)   # in-memory backend, same semantics
```

See the repository `docs/` directory for concepts, dependencies and
invalidation.
