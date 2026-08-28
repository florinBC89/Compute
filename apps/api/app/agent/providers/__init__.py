"""One module per LLM provider, each exposing an async complete() that calls
computelayer.context.record_llm_call() so the reuse engine's cost ledger
picks it up with zero changes (see providers/openai.py for the exact shape).
"""
