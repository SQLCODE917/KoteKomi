Read the passage inside `<source>` and `</source>`.

The Event is the text between `<event>` and `</event>`.
The Candidate is the text between `<candidate>` and `</candidate>`.

Answer `Y` when removing the exact Candidate words would lose part of what the passage says about the Event.

Answer `N` when the Candidate belongs to a different action or claim, or is unrelated.

Answer `U` when the passage does not make clear whether the Candidate belongs to the Event.

Examples:

`<source><candidate>Alex</candidate> criticized Plan A and <event>opposed</event> Plan B.</source>`

`Y`

`<source>Alex criticized Plan A and <event>opposed</event> <candidate>Plan B</candidate>.</source>`

`Y`

`<source>Alex <candidate>criticized</candidate> Plan A and <event>opposed</event> Plan B.</source>`

`N`

`<source>Alex criticized <candidate>Plan A</candidate> and <event>opposed</event> Plan B.</source>`

`N`

Return only `Y`, `N`, or `U`.
