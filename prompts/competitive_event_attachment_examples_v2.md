Read one passage containing one Candidate occurrence and several Event options.

The Candidate is the exact text between `<candidate>` and `</candidate>`.
Each labeled Event option marks both that same Candidate occurrence and one Event between `<event>` and `</event>`.
When those ranges cross, the option shows separate Candidate and Event views of the same passage.

For each Event, consider the complete fact centered on the marked Event words.
Select the Event when the Candidate supplies part of that fact: a participant, affected thing, time, place, attribution, negation, uncertainty, purpose, comparison, or necessary clause content.
Follow grammatical references such as pronouns, descriptions, and relative clauses.
An introductory time phrase or connector applies only to the clauses it actually links.
Do not select an Event merely because the Candidate is nearby or appears in the same sentence.
Select every applicable Event; the Candidate may belong to no Event, one Event, or several Events.

Example 1:

Source: `During the hearing, Alex criticized Plan A and opposed Plan B.`
Candidate: `Alex`
E1 Event: `criticized`
E2 Event: `opposed`
Answer: `E1,E2`

Example 2:

Source: `During the hearing, Alex criticized Plan A and Riley opposed Plan B.`
Candidate: `Plan B`
E1 Event: `criticized`
E2 Event: `opposed`
Answer: `E2`

Example 3:

Source: `Alex criticized Plan A, Riley opposed Plan B, and Alex endorsed Plan C.`
Candidate: `Alex`
E1 Event: `criticized`
E2 Event: `opposed`
E3 Event: `endorsed`
Answer: `E1,E3`

Example 4:

Source: `[7] Acme launched Nova.`
Candidate: `[7]`
E1 Event: `launched`
Answer: `NONE`

Example 5:

Source: `Lena arrived, Omar criticized Plan A, Mira departed, and Omar praised Plan B.`
Candidate: `Omar`
E1 Event: `arrived`
E2 Event: `criticized`
E3 Event: `departed`
E4 Event: `praised`
Answer: `E2,E4`

Example 6:

Source: `As Mira testified, Rowan took notes, which Rowan filed the next day.`
Candidate: `As`
E1 Event: `testified`
E2 Event: `took`
E3 Event: `filed`
Answer: `E1,E2`

Example 7:

Source: `Mira rejected Northstar's claims, intensifying their dispute.`
Candidate: `Northstar`
E1 Event: `rejected`
E2 Event: `intensifying`
Answer: `E1,E2`

Return `NONE` when the Candidate belongs to no listed Event.
Return `UNCLEAR` when the passage does not decide which listed Events the Candidate belongs to.
Otherwise return only the applicable Event labels, separated by commas and in the order supplied, such as `E1,E3`.
Do not add an explanation.
