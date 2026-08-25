# Quickstart

## 1. Bring up the stack

```bash
cp .env.example .env
docker compose up
```

Postgres, Redis and the API, migrated and seeded. The API prints a
project-scoped key.

## 2. Install the SDK

```bash
pip install -e packages/python-sdk
export COMPUTELAYER_API_URL=http://localhost:8000/v1
export COMPUTELAYER_API_KEY=cl_test_local_development_key
export COMPUTELAYER_PROJECT=research-agent
```

## 3. Cache your first computation

```python
import asyncio
from computelayer import ComputeLayer

cl = ComputeLayer()

async def main():
    async with cl.run() as run:
        for _ in range(2):
            result = await cl.compute.run(
                name="financials",
                inputs={"ticker": "NVDA"},
                fn=lambda: {"revenue": 130_500},
            )
            print(result.cache_status, result.value)
        print(run.id)

    print(run.summary)

asyncio.run(main())
```

```
MISS {'revenue': 130500}
HIT  {'revenue': 130500}
```

## 4. Instrument your LLM calls

```python
from computelayer.openai import AsyncOpenAI

llm = AsyncOpenAI(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
)

async def overview(profile):
    response = await llm.chat.completions.create(
        model="openai/gpt-4o",
        messages=[{"role": "user", "content": f"Summarize: {profile}"}],
    )
    return response["choices"][0]["message"]["content"]

result = await cl.compute.run(
    name="overview",
    inputs={"profile": profile},
    model="openai/gpt-4o",
    prompt=SYSTEM_PROMPT,
    fn=lambda: overview(profile),
)
```

The LLM request itself is not cached. The computation around it is — so on a
`HIT` the request never happens, and `result.saved_usd` is what it would have
cost.

## 5. Use the decorator instead

```python
@cl.compute(name="financial_analysis", ttl=86_400)
async def financial_analysis(company: str, financials: dict) -> dict:
    ...

report = await financial_analysis("NVDA", financials)     # value
result = await financial_analysis.compute_run("NVDA", financials)  # ComputeResult
```

## 6. No infrastructure

```python
cl = ComputeLayer(local=True)
```

Identical semantics, in memory. This is what the test suite runs against.

## 7. Inspect

```bash
computelayer run show <run_id>
computelayer explain <computation_id>
```
