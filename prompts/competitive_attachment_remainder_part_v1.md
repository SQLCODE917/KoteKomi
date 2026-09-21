The Passage is the exact text between `<source>` and `</source>`.
The Candidate is the exact text between `<candidate>` and `</candidate>`.
The Target Event is the exact text between `<event>` and `</event>`.
The Remainder Part is the exact text between `<remainder>` and `</remainder>`.
The Other Events are other event expressions in the Passage.

Decide whether the Remainder Part belongs to the fact centered on the Target Event.

Answer `Y` when removing the Remainder Part would lose part of what the Passage says about the Target Event.
This includes a participant, object, time, place, manner, purpose, negation, uncertainty, attribution, or comparison.
Answer `N` when the Remainder Part belongs only to another fact or connects the Target Event to another fact.
Answer `U` when the Passage does not make that distinction clear.

Example 1:

Passage with the Candidate occurrence:
<source>Jordan arrived before Casey <candidate>criticized the policy in March</candidate>.</source>

Target Event E2:
<source>Jordan arrived before Casey <event>criticized</event> the policy in March.</source>

Other Events in the Passage:
E1: "arrived"

Remainder Part:
<remainder> the policy in March</remainder>

Y

Example 2:

Passage with the Candidate occurrence:
<source>Jordan <candidate>handed the report to Casey, who criticized the policy</candidate>.</source>

Target Event E2:
<source>Jordan handed the report to Casey, who <event>criticized</event> the policy.</source>

Other Events in the Passage:
E1: "handed"

Remainder Part:
<remainder>handed the report to Casey, who </remainder>

N
