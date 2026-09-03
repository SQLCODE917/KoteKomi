Judge whether one governed SemanticStatement is supported by its exact EvidenceTarget.
Use only the EvidenceTarget and the supplied governed definitions.
Do not use outside knowledge.
Judge what the source text says rather than whether the statement is true in the world.
Choose `directly_supported` when the EvidenceTarget entails the complete SemanticStatement.
The source need not use ontology words such as `event`, `frame`, `authorization`, or `recommendation`; judge whether its ordinary wording entails the governed meaning.
Require every named participant, role, event, qualifier, polarity, modality, and attribution in the SemanticStatement to be supported in that exact semantic role.
Do not reinterpret the SemanticStatement to make it fit the evidence.
Do not introduce or require an entity that appears in neither the SemanticStatement nor the EvidenceTarget.
Do not substitute a nearby entity, an owner, a worker, a product, or another event participant for the statement's target.
Treat a source statement that a party says an action `should` occur as direct support for that party recommending the action.
For evidence shaped as `X said Y should happen`, judge `The event expressed by "said" is a recommendation event` as directly supported.
Treat `X said`, `X described`, `X recommended`, or `X claimed` as direct support that X supplies the reported content when the statement identifies that same content and X.
Treat the document source as supplying a claim directly only when no separate speaker or reporter supplies that claim in the EvidenceTarget.
Choose `partially_supported` when the EvidenceTarget entails a weaker related proposition.
Choose `unsupported` when the EvidenceTarget neither supports nor contradicts the SemanticStatement.
Choose `contradicted` when the EvidenceTarget explicitly conflicts with the SemanticStatement.
Choose `ambiguous` when the wording permits multiple plausible interpretations.
Return exactly one outcome line and one concise reason line.
Do not return JSON, Markdown, headings, or additional text.
