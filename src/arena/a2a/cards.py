"""Agent Cards (T362): what each agent says about itself at `/.well-known/agent-card.json`.

Cards are built with the SDK's generated protobuf types, so a card that the SDK cannot serialise
cannot be built either. Every card carries the research-project disclaimer, declares no security
scheme (agents run in-process or on localhost only) and lists its skills with ids and modes.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from a2a.types import a2a_pb2 as pb
from a2a.utils.proto_utils import _validate_proto_required_fields_internal

from arena.a2a import DISCLAIMER, PROTOCOL_VERSION

JSON_MODE = "application/json"
TEXT_MODE = "text/plain"


@dataclass(frozen=True)
class SkillSpec:
    """One skill an agent offers (an A2A `AgentSkill`)."""

    id: str
    name: str
    description: str
    tags: tuple[str, ...] = ("forecasting",)
    examples: tuple[str, ...] = ()
    input_modes: tuple[str, ...] = (JSON_MODE,)
    output_modes: tuple[str, ...] = (JSON_MODE,)


@dataclass(frozen=True)
class AgentSpec:
    """Everything needed to build one Agent Card."""

    name: str
    description: str
    version: str
    skills: tuple[SkillSpec, ...]
    input_modes: tuple[str, ...] = (JSON_MODE, TEXT_MODE)
    output_modes: tuple[str, ...] = (JSON_MODE,)
    extra: dict[str, str] = field(default_factory=dict)


def build_card(spec: AgentSpec, url: str) -> pb.AgentCard:
    """The Agent Card for `spec`, served at `url` over JSON-RPC (protocol 1.0, no streaming)."""
    return pb.AgentCard(
        name=spec.name,
        description=f"{spec.description} {DISCLAIMER}",
        version=spec.version,
        supported_interfaces=[
            pb.AgentInterface(
                url=url, protocol_binding="JSONRPC", protocol_version=PROTOCOL_VERSION
            )
        ],
        capabilities=pb.AgentCapabilities(streaming=False, push_notifications=False),
        default_input_modes=list(spec.input_modes),
        default_output_modes=list(spec.output_modes),
        skills=[
            pb.AgentSkill(
                id=s.id,
                name=s.name,
                description=s.description,
                tags=list(s.tags),
                examples=list(s.examples),
                input_modes=list(s.input_modes),
                output_modes=list(s.output_modes),
            )
            for s in spec.skills
        ],
    )


def validate_card(card: pb.AgentCard) -> list[str]:
    """Problems with a card (empty when it is acceptable for this project).

    Includes the SDK's own check of the fields the protocol marks REQUIRED (read from the protobuf
    field annotations), so a card the SDK would warn about is not accepted here.
    """
    problems: list[str] = [
        f"required field missing: {e['field']}"
        for e in _validate_proto_required_fields_internal(card)
    ]
    if not card.name.strip():
        problems.append("name is empty")
    if not card.version.strip():
        problems.append("version is empty")
    if DISCLAIMER not in card.description:
        problems.append("description lacks the research-project disclaimer")
    if not card.supported_interfaces:
        problems.append("no supported interface")
    for i in card.supported_interfaces:
        if not i.url or i.protocol_binding != "JSONRPC" or i.protocol_version != PROTOCOL_VERSION:
            problems.append(f"interface {i.url!r} is not JSONRPC {PROTOCOL_VERSION}")
    if not card.skills:
        problems.append("no skills")
    ids = [s.id for s in card.skills]
    if len(set(ids)) != len(ids):
        problems.append("duplicate skill ids")
    for s in card.skills:
        if not (s.id and s.name and s.description):
            problems.append(f"skill {s.id!r} is incomplete")
    if not card.default_input_modes or not card.default_output_modes:
        problems.append("input or output modes missing")
    if len(card.security_schemes) or len(card.security_requirements):
        problems.append("a security scheme is declared, but agents here are local only")
    return problems


def skills_of(card: pb.AgentCard) -> Sequence[str]:
    """Skill ids of a card (for tests and the CLI)."""
    return [s.id for s in card.skills]
