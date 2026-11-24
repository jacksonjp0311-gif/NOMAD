# LOGOS integration plan

LOGOS is a semantic engine. It asks how a learner can infer the meaning of an
unfamiliar command from its observable consequences, decide which question to
ask next, and transfer what it learns to a recipient with a different encoding.
No pretrained language weights. Finite experiments. Compositional predictive
semantics.

NOMAD is a field. Sparse binary packets. Twin measurement. WITNESS gate.
MEANING is word-to-concept retrieval. It is not language understanding.

## What transfers

The probe. A linguistic claim with a correct answer and distractors. The field
encodes the claim as a bit set. The packet is a sparse binary set over the same
universe. Overlap scores the packet against the claim. The twin is cold versus
field. Certification requires WITNESS and final correct. The cold start must
fail. The field must succeed.

The question selection. LOGOS chooses the next question by expected reduction
in decision risk. NOMAD can use the same rule for which probe to run next.
The choice is a suggestion. The body decides.

The transfer. LOGOS transfers across encodings when the intertwining property
holds. NOMAD can test whether a packet certified on one claim certifies a
claim with a different encoding. If it does and the cold start does not, the
transfer is causal.

## What does not transfer

The finite state engine. The tabular transition learner. The specific
experiments. The white paper claims. LOGOS is a separate research line. NOMAD
is the field. The integration is the probe and the question selection, not
the engine.

## Plan

1. A `logos/` folder in the NOMAD root. Contains the probe encoding, the
   question selection rule, and the transfer test. Does not contain the LOGOS
   engine.
2. A sealed linguistic probe suite. Claims that are not in the training set.
   Correct answers and distractors. Generated before any field arm runs.
3. A twin measurement. Cold versus field. Certification only if field succeeds
   and cold fails.
4. A composition rule. Two packets certified on different claims can be unioned.
   The composed packet is tested on a claim neither trained. If it certifies
   and neither alone does, the composition is causal.
5. A question selection rule. The next probe is the one that most reduces
   decision risk given the current field. The choice is a suggestion. The body
   decides.

## Boundary

Not language understanding. Not grammar. Not meaning. A sealed probe that is
a linguistic claim and a packet that is certified only when it answers the
claim and the cold start does not. The measurement says whether the packet
means something. The architecture is the same. The content is different.
LOGOS supplies the probe shape. NOMAD supplies the field and the gate.
