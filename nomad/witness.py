from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from typing import Iterable, Mapping


def _canonical(payload: Mapping[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest_values(values: Iterable[float]) -> str:
    vals = [float(v) for v in values]
    return sha256(_canonical({"values": vals})).hexdigest()


def _rmse(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    if len(a) != len(b) or not a:
        raise ValueError("vectors must have equal non-zero length")
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)) / len(a))


def _matches(a: tuple[float, ...], b: tuple[float, ...], tol: float) -> bool:
    return len(a) == len(b) and bool(a) and all(abs(x - y) <= tol for x, y in zip(a, b))


@dataclass(frozen=True)
class ConsequenceClaim:
    """A falsifiable claim about a transmission's externally observable consequence.

    WITNESS does not choose the goal and does not call an outcome good or bad.  It
    only checks whether the claimed consequence is supported by evidence that is
    independent of the search-time assertion.
    """

    kind: str = "matches_target"
    tolerance: float = 1e-9


@dataclass(frozen=True)
class WitnessReceipt:
    schema: str
    witness_id: str
    task_id: str
    transmission_id: str
    world_epoch: int
    claim_kind: str
    tolerance: float
    verdict: str
    public_match: bool
    challenge_match: bool
    public_rmse_before: float
    public_rmse_after: float
    challenge_rmse_before: float
    challenge_rmse_after: float
    public_evidence_digest: str
    challenge_evidence_digest: str
    effect_digest: str
    receipt_hash: str

    def payload_without_hash(self) -> dict[str, object]:
        raw = asdict(self)
        raw.pop("receipt_hash", None)
        return raw

    def verify_checksum(self) -> bool:
        return sha256(_canonical(self.payload_without_hash())).hexdigest() == self.receipt_hash

    @property
    def supported(self) -> bool:
        return self.verdict == "supported" and self.public_match and self.challenge_match


class Witness:
    """Independent consequence observer for NOMAD.

    The caller supplies observations, not a boolean success flag.  WITNESS
    recomputes whether the candidate behavior matches the declared target on
    public and withheld challenge evidence.  Its receipt is an integrity-checked
    fact record, not a digital signature or adversarial security boundary.
    """

    def __init__(self, witness_id: str = "nomad-witness-v0.6") -> None:
        self.witness_id = witness_id

    def attest(
        self,
        *,
        task_id: str,
        transmission_id: str,
        world_epoch: int,
        current_public: tuple[float, ...],
        target_public: tuple[float, ...],
        candidate_public: tuple[float, ...],
        current_challenge: tuple[float, ...],
        target_challenge: tuple[float, ...],
        candidate_challenge: tuple[float, ...],
        claim: ConsequenceClaim | None = None,
    ) -> WitnessReceipt:
        claim = claim or ConsequenceClaim()
        if claim.kind != "matches_target":
            raise ValueError(f"unsupported claim kind: {claim.kind}")
        vectors = (
            current_public,
            target_public,
            candidate_public,
            current_challenge,
            target_challenge,
            candidate_challenge,
        )
        if any(not v for v in vectors):
            raise ValueError("witness evidence vectors must be non-empty")
        if not (len(current_public) == len(target_public) == len(candidate_public)):
            raise ValueError("public evidence vectors must have equal length")
        if not (len(current_challenge) == len(target_challenge) == len(candidate_challenge)):
            raise ValueError("challenge evidence vectors must have equal length")

        public_match = _matches(candidate_public, target_public, claim.tolerance)
        challenge_match = _matches(candidate_challenge, target_challenge, claim.tolerance)
        verdict = "supported" if public_match and challenge_match else "contradicted"

        public_evidence_digest = sha256(_canonical({
            "current": list(current_public),
            "target": list(target_public),
            "candidate": list(candidate_public),
        })).hexdigest()
        challenge_evidence_digest = sha256(_canonical({
            "current": list(current_challenge),
            "target": list(target_challenge),
            "candidate": list(candidate_challenge),
        })).hexdigest()
        effect_digest = sha256(_canonical({
            "public_delta": [float(c - b) for b, c in zip(current_public, candidate_public)],
            "challenge_delta": [float(c - b) for b, c in zip(current_challenge, candidate_challenge)],
        })).hexdigest()

        body: dict[str, object] = {
            "schema": "nomad.v0.6.witness-receipt.v1",
            "witness_id": self.witness_id,
            "task_id": task_id,
            "transmission_id": transmission_id,
            "world_epoch": int(world_epoch),
            "claim_kind": claim.kind,
            "tolerance": float(claim.tolerance),
            "verdict": verdict,
            "public_match": public_match,
            "challenge_match": challenge_match,
            "public_rmse_before": _rmse(current_public, target_public),
            "public_rmse_after": _rmse(candidate_public, target_public),
            "challenge_rmse_before": _rmse(current_challenge, target_challenge),
            "challenge_rmse_after": _rmse(candidate_challenge, target_challenge),
            "public_evidence_digest": public_evidence_digest,
            "challenge_evidence_digest": challenge_evidence_digest,
            "effect_digest": effect_digest,
        }
        body["receipt_hash"] = sha256(_canonical(body)).hexdigest()
        return WitnessReceipt(**body)  # type: ignore[arg-type]

    def valid_for_context(
        self,
        receipt: WitnessReceipt,
        *,
        task_id: str,
        transmission_id: str,
        world_epoch: int,
    ) -> bool:
        """Check receipt integrity and exact world/transmission provenance."""
        return (
            receipt.witness_id == self.witness_id
            and receipt.verify_checksum()
            and receipt.task_id == task_id
            and receipt.transmission_id == transmission_id
            and receipt.world_epoch == int(world_epoch)
        )

    def authorize(
        self,
        receipt: WitnessReceipt,
        *,
        task_id: str,
        transmission_id: str,
        world_epoch: int,
    ) -> bool:
        """Return whether this exact receipt can support durable knowledge now.

        Epoch matching prevents a receipt for an earlier world state from being
        silently reused after the target/environment has changed.  This is a
        provenance rule, not a cryptographic trust boundary.
        """
        return self.valid_for_context(
            receipt,
            task_id=task_id,
            transmission_id=transmission_id,
            world_epoch=world_epoch,
        ) and receipt.supported


def receipt_to_event(receipt: WitnessReceipt) -> dict[str, object]:
    return {
        "kind": "witness_receipt",
        "schema": receipt.schema,
        "witness_id": receipt.witness_id,
        "task_id": receipt.task_id,
        "transmission_id": receipt.transmission_id,
        "world_epoch": receipt.world_epoch,
        "claim_kind": receipt.claim_kind,
        "verdict": receipt.verdict,
        "public_match": receipt.public_match,
        "challenge_match": receipt.challenge_match,
        "public_rmse_before": receipt.public_rmse_before,
        "public_rmse_after": receipt.public_rmse_after,
        "challenge_rmse_before": receipt.challenge_rmse_before,
        "challenge_rmse_after": receipt.challenge_rmse_after,
        "public_evidence_digest": receipt.public_evidence_digest,
        "challenge_evidence_digest": receipt.challenge_evidence_digest,
        "effect_digest": receipt.effect_digest,
        "receipt_hash": receipt.receipt_hash,
    }
