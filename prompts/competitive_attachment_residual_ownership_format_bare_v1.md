The Candidate is the exact text between `<candidate>` and `</candidate>`.
The Target Event is the exact text between `<event>` and `</event>`.
The Candidate Remainder is the Candidate text outside the Target Event.
Each Candidate Remainder part is between `<remainder>` and `</remainder>`.
The Other Events are other event expressions in the same passage.

Decide whether each meaningful Candidate Remainder part belongs to the Target Event fact.

Answer `Y` when every meaningful Candidate Remainder part belongs to the Target Event fact.
Answer `N` when any meaningful Candidate Remainder part belongs only to a different fact in the passage.
Answer `U` when the passage does not make that distinction clear.

Example 1:

Passage with the Candidate occurrence:
<source>Jordan arrived before Casey <candidate>criticized the policy in March</candidate>.</source>

Target Event E2:
<source>Jordan arrived before Casey <event>criticized</event> the policy in March.</source>

Other Events in the passage:
E1: "arrived"

Candidate Remainder parts:
R1: <remainder> the policy in March</remainder>

Y

Example 2:

Passage with the Candidate occurrence:
<source>Jordan handed <candidate>the report to Casey, who criticized the policy</candidate>.</source>

Target Event E2:
<source>Jordan handed the report to Casey, who <event>criticized</event> the policy.</source>

Other Events in the passage:
E1: "handed"

Candidate Remainder parts:
R1: <remainder>the report to Casey, who </remainder>
R2: <remainder> the policy</remainder>

N
