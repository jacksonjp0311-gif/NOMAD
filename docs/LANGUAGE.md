# Language understanding plan

MEANING is word-to-concept retrieval. It passed its sealed judge. It is not
language understanding. The next rung is a probe that is a linguistic claim.

## What exists

MEANING links words in a task description to a certified program. A new task
described in words retrieves the concept before search. The gain is memory-borne
and word-borne. The association is bag-of-words counts over templated English.
Relational words overlap by design. Concepts are only those the field already
certified. Variable roles are found by trying renamings, not read from the words.

## What is missing

A probe that is a sentence, a meaning, a grammar. A packet that is certified
only if it answers the claim correctly and the cold start does not. That is
the sealed evidence that the packet means something.

## Architecture

The same twin. The same WITNESS gate. Different content.

A linguistic probe is a claim with a correct answer and a set of distractors.
The field encodes the claim as a bit set. The packet is a sparse binary set
over the same universe. Overlap scores the packet against the claim. The twin
is cold versus field on the same claim. Certification requires WITNESS and
final correct. The cold start must fail. The field must succeed.

## Math

The claim is a set of tokens. The packet is a set of bits. The score is
integer overlap. The prior is the lexicon counts from MEANING. The twin is
the same paired measurement. The gate is the same. No embeddings. No
transformer. No floating-point.

## Plan

1. A sealed linguistic probe suite. Claims that are not in the training set.
   Correct answers and distractors. Generated before any field arm runs.
2. A packet encoding for a claim. Bit set from tokens. Same universe.
3. A twin measurement. Cold versus field. Certification only if field succeeds
   and cold fails.
4. A composition rule. If two packets are certified on different claims, their
   bit sets can be unioned. The composed packet is tested on a claim that
   neither trained. If it certifies and neither alone does, the composition
   is causal.

## Boundary

Not language understanding. Not grammar. Not meaning. A sealed probe that is
a linguistic claim and a packet that is certified only when it answers the
claim and the cold start does not. The measurement says whether the packet
means something. The architecture is the same. The content is different.
