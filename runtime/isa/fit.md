[ISA fit — what the ISA process solves]
An ISA pays off when "done" could drift: the work has an outcome someone will rely on, several
parts that could each be skipped, and an answer that can be checked against evidence. It fixes three
failure modes: settling for an easier neighbour of what was asked, leaving parts silently uncovered,
and claiming a result with no evidence behind it.

Fits (even with zero file changes): reviews and audits, investigations and root-cause analysis,
comparisons and evaluations, research that must reach a conclusion, plans, designs and specs,
migrations, anything asking for "all / every / complete / make sure".
Doesn't fit: a single fact, an explanation, a lookup, a yes/no, a status check, small talk.

How an ISA structures read-only work:
- Goal = the conclusion the work must reach, quoted from the prompt when possible.
- ISCs = the questions the answer must settle, one per part ("each module checked for X",
  "the three options compared on cost"), plus one `Anti:` for the lazy answer
  ("Anti: a finding is stated without a file:line or command output behind it").
- Verification = the evidence per ISC (quoted lines, file:line, command output).
- `Goal: yes` only when the answer delivers the conclusion that was asked for, not a nearby one.
