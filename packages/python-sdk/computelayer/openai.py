"""Import shim so ``from computelayer.openai import OpenAI`` works (spec §25).

The implementation lives in :mod:`computelayer.integrations.openai`.
"""

from computelayer.integrations.openai import (  # noqa: F401
    AsyncOpenAI,
    OpenAI,
    instrument,
)

__all__ = ["AsyncOpenAI", "OpenAI", "instrument"]
