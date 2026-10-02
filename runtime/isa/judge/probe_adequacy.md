You review the probes of an ISA (a task's definition of done). Each criterion (ISC) claims an end
state; its probe is a shell command that passes when it exits 0.

For each item, answer: would this probe, as written, FAIL (exit non-zero) if the criterion were false?
Say "no" when the probe can't fail (`true`, `echo ok`), checks something else than the claim (greps
for text instead of running the code it claims about, counts output lines without comparing the
count), or would pass on a trivially broken result. Say "yes" when a false criterion would make it
fail. Judge only what is written; don't assume files you can't see are wrong.

Items (ISC: criterion | probe):
<<<
{items}
>>>

Answer with JSON only: {"verdicts": [{"isc": "ISC-N", "verdict": "yes" | "no", "reason": "<one short line>"}, ...]}
