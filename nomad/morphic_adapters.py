from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class CodeArtifact:
    expression: str


class CodeAdapter:
    name = "code"

    def observe(self, artifact: CodeArtifact, inputs: tuple[float, ...]) -> tuple[float, ...]:
        # The benchmark owns the expression strings and permits only this tiny DSL.
        expr = artifact.expression
        allowed = set("x0123456789+-*/(). ")
        if not set(expr) <= allowed:
            raise ValueError("unsupported code expression")
        return tuple(float(eval(expr, {"__builtins__": {}}, {"x": x})) for x in inputs)

    def transform(self, artifact: CodeArtifact, family: str) -> CodeArtifact:
        e = artifact.expression
        mapping = {
            "shift_up": f"({e}) + 1",
            "shift_down": f"({e}) - 1",
            "amplify": f"({e}) * 2",
            "dampen": f"({e}) / 2",
            "invert": f"-({e})",
        }
        return CodeArtifact(mapping[family])

    def describe(self, artifact: CodeArtifact) -> str:
        return f"def f(x): return {artifact.expression}"


@dataclass(frozen=True)
class MathArtifact:
    fn: Callable[[float], float]
    notation: str


class MathAdapter:
    name = "math"

    def observe(self, artifact: MathArtifact, inputs: tuple[float, ...]) -> tuple[float, ...]:
        return tuple(float(artifact.fn(x)) for x in inputs)

    def transform(self, artifact: MathArtifact, family: str) -> MathArtifact:
        f = artifact.fn
        if family == "shift_up":
            return MathArtifact(lambda x, f=f: f(x) + 1, f"({artifact.notation})+1")
        if family == "shift_down":
            return MathArtifact(lambda x, f=f: f(x) - 1, f"({artifact.notation})-1")
        if family == "amplify":
            return MathArtifact(lambda x, f=f: 2 * f(x), f"2({artifact.notation})")
        if family == "dampen":
            return MathArtifact(lambda x, f=f: f(x) / 2, f"({artifact.notation})/2")
        if family == "invert":
            return MathArtifact(lambda x, f=f: -f(x), f"-({artifact.notation})")
        raise KeyError(family)

    def describe(self, artifact: MathArtifact) -> str:
        return artifact.notation


@dataclass(frozen=True)
class DataArtifact:
    scale: float
    bias: float
    negate: bool = False


class DataAdapter:
    name = "data"

    def observe(self, artifact: DataArtifact, inputs: tuple[float, ...]) -> tuple[float, ...]:
        vals = tuple(artifact.scale * x + artifact.bias for x in inputs)
        return tuple(-v if artifact.negate else v for v in vals)

    def transform(self, artifact: DataArtifact, family: str) -> DataArtifact:
        # Transform the pipeline output, not the input schema.
        if family == "shift_up":
            return DataArtifact(artifact.scale, artifact.bias + (-1 if artifact.negate else 1), artifact.negate)
        if family == "shift_down":
            return DataArtifact(artifact.scale, artifact.bias + (1 if artifact.negate else -1), artifact.negate)
        if family == "amplify":
            return DataArtifact(artifact.scale * 2, artifact.bias * 2, artifact.negate)
        if family == "dampen":
            return DataArtifact(artifact.scale / 2, artifact.bias / 2, artifact.negate)
        if family == "invert":
            return DataArtifact(artifact.scale, artifact.bias, not artifact.negate)
        raise KeyError(family)

    def describe(self, artifact: DataArtifact) -> str:
        return f"pipeline(scale={artifact.scale}, bias={artifact.bias}, negate={artifact.negate})"


@dataclass(frozen=True)
class WorkflowArtifact:
    gain: float
    offset: float
    sign: float = 1.0


class WorkflowAdapter:
    name = "workflow"

    def observe(self, artifact: WorkflowArtifact, inputs: tuple[float, ...]) -> tuple[float, ...]:
        # A tiny deterministic workflow: input -> transform edge -> terminal score.
        return tuple(artifact.sign * (artifact.gain * x + artifact.offset) for x in inputs)

    def transform(self, artifact: WorkflowArtifact, family: str) -> WorkflowArtifact:
        if family == "shift_up":
            return WorkflowArtifact(artifact.gain, artifact.offset + (1 / artifact.sign), artifact.sign)
        if family == "shift_down":
            return WorkflowArtifact(artifact.gain, artifact.offset - (1 / artifact.sign), artifact.sign)
        if family == "amplify":
            return WorkflowArtifact(artifact.gain * 2, artifact.offset * 2, artifact.sign)
        if family == "dampen":
            return WorkflowArtifact(artifact.gain / 2, artifact.offset / 2, artifact.sign)
        if family == "invert":
            return WorkflowArtifact(artifact.gain, artifact.offset, -artifact.sign)
        raise KeyError(family)

    def describe(self, artifact: WorkflowArtifact) -> str:
        return f"start -> edge(gain={artifact.gain}, offset={artifact.offset}, sign={artifact.sign}) -> goal"


ADAPTERS = {
    "code": CodeAdapter(),
    "math": MathAdapter(),
    "data": DataAdapter(),
    "workflow": WorkflowAdapter(),
}
