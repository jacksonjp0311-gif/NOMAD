"""External example loader.

Reads integer triples from a file and returns them as examples.
File format: one line per example, "x y expected".
Used by tools to pull new data into the cycle.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .genesis import IOExample

def load_examples(path: str | Path) -> tuple[IOExample, ...]:
    p = Path(path)
    if not p.exists():
        return ()
    out = []
    for line in p.read_text().splitlines():
        parts = line.strip().split()
        if len(parts) == 3:
            try:
                x, y, e = int(parts[0]), int(parts[1]), int(parts[2])
                out.append(IOExample(x, y, e))
            except ValueError:
                continue
    return tuple(out)

def write_examples(path: str | Path, examples: tuple[IOExample, ...]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{e.x} {e.y} {e.expected}" for e in examples]
    p.write_text("\n".join(lines) + "\n")
