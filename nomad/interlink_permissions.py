"""NOMAD Interlink permissions.

Three layers. Tool preapproval is external. Body mutations are denied by
default. No self-authorization. A receipt cannot grant a mutation.
"""
from __future__ import annotations

import os

ALLOWED = {"inspect", "observe", "evidence"}
MUTATIONS = {"restart", "kill", "promote", "edit"}


def mutation_allowed(action: str) -> bool:
    """Mutations are denied unless explicitly enabled by operator."""
    if action not in MUTATIONS:
        return False
    return os.environ.get("NOMAD_INTERLINK_MUTATE", "off").lower() == "on"


def tool_allowed(name: str) -> bool:
    return name in ALLOWED or mutation_allowed(name)
