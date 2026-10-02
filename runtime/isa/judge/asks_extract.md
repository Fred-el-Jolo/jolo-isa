You list the explicit asks in a user's request to an AI coding assistant.

An ask is one thing the user explicitly asked for: a deliverable, a constraint on how to do it, or a
directive about depth or scope ("go deep", "don't touch the tests", "list each one with its line
number"). Quote each ask as a short verbatim span of the prompt, in order. Don't add asks the user did
not state. When the prompt is a short approval ("go", "ok do it"), take the asks from what the
assistant's previous message proposed and the user approved.

The assistant's previous message (end of it, may be empty):
<<<
{context}
>>>

The user's prompt:
<<<
{prompt}
>>>

Answer with JSON only: {"asks": ["<verbatim span>", "..."]}
