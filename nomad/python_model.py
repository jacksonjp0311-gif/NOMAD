from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class PythonExample:
    inputs: Mapping[str, int]
    expected: int


@dataclass(frozen=True)
class PythonTask:
    task_id: str
    source: str
    examples: Sequence[PythonExample]
    function_name: str = "solve"
    family: str = "unknown"  # evaluator metadata only; solver never consumes it


@dataclass(frozen=True)
class PythonCandidate:
    source: str
    operator_family: str
    description: str
