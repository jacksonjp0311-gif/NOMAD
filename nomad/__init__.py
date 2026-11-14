"""NOMAD: evidence-bounded transformation intelligence."""

__version__ = "0.17.0"

from .engine import NomadEngine, SolveResult
from .learner import ContextualOperatorLearner
from .model import CodeTask, Example
from .search import MultiNomadEngine, MultiSolveResult, SearchStep
from .skills import SkillRegistry
from .python_search import ResonanceSearchEngine, PythonSolveResult
from .resonance import ResonanceState, encode_resonance
from .resonance_learner import ResonanceOperatorLearner
from .witness import ConsequenceClaim, Witness, WitnessReceipt
from .witness_skills import WitnessedSkillRegistry

__all__ = [
    "NomadEngine",
    "SolveResult",
    "MultiNomadEngine",
    "MultiSolveResult",
    "SearchStep",
    "SkillRegistry",
    "ContextualOperatorLearner",
    "CodeTask",
    "ResonanceSearchEngine",
    "PythonSolveResult",
    "ResonanceState",
    "encode_resonance",
    "ResonanceOperatorLearner",
    "Example",
    "EchoMapEncoder",
    "EchoPoint",
    "EchoRecord",
    "EchoMapEngine",
    "EchoResult",
    "ConsequenceClaim",
    "Witness",
    "WitnessReceipt",
    "WitnessedSkillRegistry",
    "CausalSkill",
    "CausalSkillRegistry",
    "CodeWorldTask",
    "CodeWorldResult",
    "solve_codeworld_task",
    "IOExample", "SynthesisTask", "GrammarPrior", "SynthesisRun", "synthesize", "evaluate_task",
]

from .echo_map import EchoMapEncoder, EchoPoint, EchoRecord
from .echo_engine import EchoMapEngine, EchoResult

from .causal_skills import CausalSkill, CausalSkillRegistry
from .codeworld import CodeWorldTask, CodeWorldResult, solve_task as solve_codeworld_task

from .genesis import IOExample, SynthesisTask, GrammarPrior, SynthesisRun, synthesize, evaluate_task
