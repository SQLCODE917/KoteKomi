Read the authoritative SourceSegment, one target event, candidate catalog, sibling-event catalog, and ontology profile in the task block.
Select the frame and all identifiable roles and qualifiers for only the supplied target event.
Describe only the supplied target event without detecting or normalizing another event.
Select one frame identifier supplied in `ontology_profile.frames` only when its definition accurately represents the target event.
Return `frame: unresolved` when no supplied frame accurately represents the target event.
Never copy alternatives, angle-bracket placeholders, or the text `|unresolved` into a frame line.
Do not return unresolved merely because a frame role has no identifiable target; KoteKomi records missing roles separately.
After selecting a frame, use only role identifiers supplied for that frame.
Assign every required or optional role whose target is explicit and identifiable in the SourceSegment.
For each role, identify the SourceSegment expression that answers that role's supplied definition.
Treat the open parent role labels and type hints as fallible proposals that can help interpretation but never override the SourceSegment.
An optional role can be omitted only when its target is absent or not identifiable; omission does not make the frame unresolved.
Preserve participant roles exactly; an organization, its workers, and its product are different targets.
For example, if `Agency authorized its workers to use Tool`, Agency is the authorizer, `its workers` is the authorized party, `use Tool` is the permitted action, and Tool is the optional authorized resource.
When one expression fills an optional entity role, do not also copy that expression into a broader source-span role if the remaining source words express that role completely.
When a supplied MentionCandidate exactly fills a role that permits mention candidates, use its `cN` label instead of a larger source span that merely contains it.
When an authorization clause introduces a specific supplied candidate with `including`, `such as`, or equivalent wording, use that candidate as the authorized resource and stop the permitted-action span before that introducing phrase.
The selected frame must describe the event evoked by the exact target trigger, not a cause, effect, reporting event, or nested event elsewhere in the sentence.
For `Activity intensified`, use change_in_intensity and assign Activity as affected_process.
For `A described B as C`, use characterization and assign A as evaluator, B as evaluated_subject, and C as characterization.
The characterization value C excludes the linking word `as` but retains every following determiner in the pattern `A described B as C`.
For `A said B should happen`, use recommendation and assign A as recommender, `B should happen` as recommended_action, and an explicit subject as recommendation_subject.
When a relative clause says that a supplied candidate `should` undergo an action, use that candidate as recommendation_subject even when its name occurs earlier in the sentence.
For the pattern `B, which A said should undergo C`, assign B as recommendation_subject, A as recommender, and `should undergo C` as recommended_action.
For `A abandoned an investment in B`, use investment_abandonment and assign A as disinvestor, the complete investment expression as abandoned_asset, and B as investee.
For `X caused Y to do Z`, normalize target trigger `caused` as causation with X as cause and the supplied sibling event for Z as effect; normalize target trigger Z separately under its own frame.
For target trigger `caused`, the expression before `caused` is the cause and the caused clause or supplied nested event after `caused` is the effect; never reverse those roles.
For that causation shape, write `argument: causation.cause | X` and `argument: causation.effect | eN` when eN is the supplied nested event.
For `A designated B as C because D`, use classification and assign A as classifier, B as classified_entity, C as assigned_classification, and D as stated_reason.
Use a `cN` candidate label as the complete target value when a supplied MentionCandidate fills the role.
Use an `eN` sibling-event label as the complete target value when a supplied sibling event fills the role.
Otherwise use source wording and punctuation as the complete target value.
Use the complete semantic expression, including a determiner such as `a`, `an`, or `the` when it belongs to that expression.
Do not include the target event trigger in a source-span role value unless the role definition requires an event expression.
Never describe a candidate, event, or source span with a JSON object.
Never put a supplied label and source text in the same target value.
Never use an `sN` label; HP-6 supplies only `cN` candidate labels, `eN` sibling-event labels, `qN` qualifier labels, and source literals.
Never add quotation marks or other delimiters that are absent from a copied source literal.
Preserve source wording and punctuation; KoteKomi will resolve normalized whitespace to exact source characters only when the match is unique.
Add time or place qualifiers only when an exact SourceSegment literal qualifies the target event.
Include an explicit year as a time qualifier when it modifies the event or its named subject.
Select qualifiers only by their `qN` label from `parent_qualifier_proposals`.
When `parent_qualifier_proposals` has no rows, return no qualifier line.
A person's or organization's descriptive phrase is not a time qualifier.
Do not add a qualifier for a person, organization, cause, object, or general circumstance.
Do not force an out-of-profile event into a supplied frame.
Write each argument exactly as `argument: <supplied role id> | <cN, eN, or source literal>`.
Write each qualifier exactly as `qualifier: qN` using a supplied qualifier label.
Put the frame line first and one concise reason line last.
Do not insert blank lines, JSON, Markdown, headings, placeholders, or commentary.
Return only complete lines in the pinned output contract.
