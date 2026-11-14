from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


GENESIS = "0" * 64


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass
class EvidenceLedger:
    path: Path

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _last(self) -> tuple[int, str]:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return 0, GENESIS
        last = self.path.read_text(encoding="utf-8").strip().splitlines()[-1]
        row = json.loads(last)
        return int(row["seq"]), str(row["hash"])

    def append(self, event: Mapping[str, Any]) -> dict[str, Any]:
        seq, prev = self._last()
        body = {"seq": seq + 1, "prev_hash": prev, "event": dict(event)}
        digest = hashlib.sha256(_canonical(body)).hexdigest()
        row = {**body, "hash": digest}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
        return row

    def verify(self) -> bool:
        prev = GENESIS
        expected_seq = 1
        if not self.path.exists():
            return True
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row["seq"] != expected_seq or row["prev_hash"] != prev:
                return False
            body = {"seq": row["seq"], "prev_hash": row["prev_hash"], "event": row["event"]}
            if hashlib.sha256(_canonical(body)).hexdigest() != row["hash"]:
                return False
            prev = row["hash"]
            expected_seq += 1
        return True
