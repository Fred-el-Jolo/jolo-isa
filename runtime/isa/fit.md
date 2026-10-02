[ISA gate — what the per-prompt question protects]
The gate asks one question of every prompt (SPEC-v2 § 1.1):

  Is this a request for work with a checkable end state — something that will be either done or not
  done — rather than a question or a conversation?

Yes → the session is ON and the work gets an ISA, whether or not it changes files (a review, an
audit, a plan, a fix, an investigation of why the user's own system misbehaves). No → the session stays OFF and nothing from the ISA system reaches the model.

An ISA pays off wherever "done" could drift: it fixes three failure modes — settling for an easier
neighbour of what was asked, leaving parts silently uncovered, and claiming a result with no evidence
behind it.

fit.py's `prefilter` answers the obvious cases for free (greetings → no, work requests → yes); every
other prompt goes to the judge (judge.py, template gate.md).
