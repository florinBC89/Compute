"""The real research pipeline behind the human workspace (V0.2 slice).

Product logic, not SDK logic: packages/python-sdk stays generic and
dependency-free (a cache/reuse client any workflow can use, as
benchmarks/research-agent/workflow.py already proves for a fake topology);
Accurate's specific research pipeline belongs here, in apps/api, where the
other product-specific business logic already lives.
"""
