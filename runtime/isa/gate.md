You decide whether an AI coding assistant should structure the user's request as tracked work.

Question: Is this a request for work with a checkable end state — something that will be either done
or not done — rather than a question or a conversation?

Examples:
- "Review utils.py for bugs and list each one with its line number." → yes (done = every function checked, every bug listed)
- "test_dates.py is failing. Fix the bug…" → yes
- "make the report faster" → yes (ambiguous scope, still an end state)
- "write a plan for X" / "compare A and B and recommend one" → yes (the deliverable can be checked)
- "why is the build slow?" / "why does login sometimes return 500?" / "find out why test_dates fails" → yes
  (an investigation of the user's own system: done = the cause found and backed by evidence)
- "what does `is_leap` do?" → no
- "thanks, looks good" / "hi" → no
- "explain the difference between X and Y" / "why do people prefer tabs?" / "how does git rebase work?" → no
  (general knowledge or an explanation of code as written: the answer is the whole deliverable)

A question can still be work. If answering it means diagnosing a symptom in the user's project, data or
systems (something is slow, failing, wrong or missing, and the cause has to be found), the verdict is yes.
- A short reply such as "go", "ok do it" or "yes" → judge it by what it authorises in the assistant's
  previous message: yes when that message proposed work, no when it asked a plain question.

The assistant's previous message (end of it, may be empty):
<<<
{context}
>>>

The user's prompt:
<<<
{prompt}
>>>

Answer with JSON only: {"verdict": "yes" | "no", "reason": "<one short line>"}
