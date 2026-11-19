"""Field query.

Answers by reading the weight field. A question is checked for a domain
name first. If present, that domain packet is returned along with a
candidate expression produced by the synthesizer on the domain examples.
Otherwise the question is hashed and the strongest overlapping packet
supplies the answer. No free-form generation.
"""
from __future__ import annotations

import hashlib
from typing import Any

from .weights import readout, load_packets
from .genesis import SynthesisTask, synthesize, GrammarPrior
from .domain_tasks import examples_for

BITS = 4096
DOMAINS = (
    "mathematics", "science", "language", "reasoning",
    "understanding", "problem-solving", "logic", "evidence",
    "coding", "meta",
)

def _hash_bits(text: str, density: int = 64) -> set[int]:
    h = hashlib.sha256(text.encode()).digest()
    bits = set()
    for i in range(density):
        idx = int.from_bytes(h[i % 32:(i % 32) + 4], "big") % BITS
        bits.add(idx)
    return bits

def _candidate_for(domain: str) -> str | None:
    examples = examples_for(domain)
    task = SynthesisTask(
        task_id=f"query-{domain}",
        source="def solve(x, y):\n    return 0\n",
        public=examples,
        challenge=(),
        final=(),
    )
    prior = GrammarPrior()
    # Bias toward the domain operator.
    packets = load_packets()
    for p in packets:
        if p.label == f"domain:{domain}":
            op = p.receipt.get("context", {}).get("operator", "Add")
            prior.operator.update(0, op, True)
            break
    result = synthesize(task, prior=prior)
    return result.candidate

def query(question: str, k: int = 5) -> dict[str, Any]:
    """Answer a question from the field."""
    q = question.lower()
    for domain in DOMAINS:
        if domain in q:
            packets = load_packets()
            for p in packets:
                if p.label == f"domain:{domain}":
                    candidate = _candidate_for(domain)
                    return {
                        "question": question,
                        "answer": domain,
                        "operator": p.receipt.get("context", {}).get("operator"),
                        "candidate": candidate,
                        "overlap": len(p.bits),
                        "count": p.count,
                        "label": p.label,
                        "reason": "domain name match",
                    }
    bits = _hash_bits(question)
    context = readout(bits, k=k)
    if not context:
        return {"question": question, "answer": None, "reason": "empty field"}
    domain = [c for c in context if c.get("label", "").startswith("domain:")]
    chosen = domain[0] if domain else context[0]
    receipt = chosen.get("receipt", {})
    return {
        "question": question,
        "answer": receipt.get("context", {}).get("domain") or chosen.get("label"),
        "operator": receipt.get("context", {}).get("operator"),
        "overlap": chosen.get("overlap"),
        "count": chosen.get("count"),
        "label": chosen.get("label"),
        "reason": "field readout",
    }
