You will decide whether one complete Candidate belongs entirely to one Target Event.
The Passage is the complete source text.
The Candidate is the exact text shown after `Candidate`.
The Target Event is the exact event expression shown after `Target Event`.
Contained Events are other event expressions that occur inside the Candidate.
Answer `Y` when every substantive part of the Candidate belongs to what the Passage says about the Target Event.
A Contained Event can belong when it is the object, reported content, purpose, or identifying detail of the Target Event.
Answer `N` when any substantive part of the Candidate belongs to a separate sibling event or proposition.
Answer `U` only when the Passage does not decide whether all Candidate content belongs.

Example 1:

Passage:
Rina denied the committee's cancellation of the contract.

Candidate:
"denied the committee's cancellation of the contract"

Target Event:
"denied"

Contained Events:
C1: "cancellation"

Answer: `Y`

Example 2:

Passage:
Rina approved the budget; the committee canceled the contract.

Candidate:
"approved the budget; the committee canceled the contract"

Target Event:
"approved"

Contained Events:
C1: "canceled"

Answer: `N`

Return exactly one answer character: `Y`, `N`, or `U`.
