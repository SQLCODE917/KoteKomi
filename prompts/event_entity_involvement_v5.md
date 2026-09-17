You will receive an ordered inventory of candidate copies of one source passage.
Every copy marks the same event expression inside `<event>` tags and one exact person or organization occurrence inside `<entity>` tags.
For each candidate, decide whether the marked entity occurrence belongs to the complete source proposition centered on the marked event expression.
The `<event>` tags may mark only the event head or a short source phrase, so use the grammar of the complete sentence to recover the proposition.
Follow coordination, relative clauses, possessives, attributed content, and implicit subjects controlled by another clause.
Use `Y` when the entity performs, experiences, causes, receives, owns, supplies, targets, or participates in the event.
Use `Y` when the entity is a counterparty or is explicitly named in the event's object, attributed content, or source-grounded qualification.
Use `N` when the entity belongs only to another event or neighboring clause.
Use `N` when the entity supplies only a title, employer, affiliation, time, or background description for a participant.
Use `N` when a person's name is nested only inside a participating group or organization expression and the source does not involve that person individually.
Use `U` only when the source passage genuinely permits both `Y` and `N`.
For example, `<entity>Atlas</entity> CEO Lee <event>criticized</event> Orion` is `N`.
For example, `The firms <entity>Atlas</entity> and Beta, which reached <event>agreements</event> with Orion` is `Y`.
For example, `The firms <entity>Atlas</entity> and Beta, which reached agreements to <event>avoid</event> sanctions` is `Y`.
For example, `Atlas partnered with <entity>Beta</entity>, a company that <event>offered</event> services` is `Y`.
For example, `Atlas <event>offered</event> services with <entity>Gamma Program</entity> authorization` is `Y`.
For example, `Lee <event>criticized</event> Orion, while <entity>Atlas</entity> met Beta` is `N`.
Return one `Y`, `N`, or `U` character for every candidate in the supplied order.
Return the characters as one line with no spaces, punctuation, labels, or explanation.
For example, if Candidate 1 is `Y`, Candidate 2 is `N`, and Candidate 3 is `U`, return `YNU`.
