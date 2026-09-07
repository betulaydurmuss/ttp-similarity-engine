"""Stage 3 -- does the engine actually retrieve the right actor?

The test is a leave-some-out retrieval benchmark. For a known actor, draw a
random subset of ``k`` of its techniques, send that subset to the query path as
if it were fresh incident data, and check where the true actor lands in the
ranking. Repeat across actors, sample sizes and seeds.

Two headline numbers::

    top-1 accuracy  -- how often the true actor is ranked first
    top-3 accuracy  -- how often it is in the first three

plus mean reciprocal rank, and both broken down by sample size and by the
confidence level the engine reported. That last breakdown is the important one:
results labelled *high* must be right far more often than those labelled *low*,
otherwise the confidence score is decoration.

Caveat to keep in mind when reading the numbers: the subset is drawn from the
same ATT&CK records the engine indexed, so this measures retrieval consistency,
not real-world attribution accuracy. Real incident data is noisier, partial and
contains techniques no one attributed to the actor.

Owner: evaluation module. Depends on the engine query path only.
"""

from __future__ import annotations

__all__ = ["benchmark", "metrics", "sampling"]
