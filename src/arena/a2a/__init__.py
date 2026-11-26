"""A2A (agent-to-agent) layer on the official `a2a-sdk` (T362).

Two uses, both read-only with respect to the ledger and never public:

- the forecasting committee (`arena.agent.committee`): specialist agents the chair calls over A2A;
- `arena-oracle` (`arena.a2a.oracle`): the benchmark's published record as an A2A agent.

Agents run in-process (`arena.a2a.transport`, ASGI, no socket), or on localhost for development
(`arena a2a serve`). Facts about the protocol and the SDK, and the gaps in what could be
verified, are in `docs/SOURCES.md` (A2A section).
"""

from __future__ import annotations

from importlib import metadata

#: Protocol version this project declares on its Agent Cards (the SDK implements 1.0).
PROTOCOL_VERSION = "1.0"
DISCLAIMER = "Research project, not advice of any kind."


def sdk_version() -> str:
    """The installed `a2a-sdk` version, or "none" when the optional requirement is missing."""
    try:
        return metadata.version("a2a-sdk")
    except metadata.PackageNotFoundError:
        return "none"
