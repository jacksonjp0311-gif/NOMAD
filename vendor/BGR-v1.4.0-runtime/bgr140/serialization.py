"""Standards-compliant JSON encoding of diagnostic sentinel values.

The reference learner uses -inf when no candidate qualifies. It remains a
float internally. At a JSON boundary it becomes {"nonfinite_float":"-inf"};
this explicit tagged object avoids invalid JSON or a misleading numeric zero.
Predictive probabilities are checked separately and must always be finite.
"""
from __future__ import annotations
import math


def json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return {"nonfinite_float": value.hex()}
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value
