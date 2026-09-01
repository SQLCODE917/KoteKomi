Judge referentiality, contextual kind, and discourse role independently from the visible source context.
Referentiality `specific_entity` means one particular entity, as in `Anthropic announced`; do not use it for a class such as `AI companies announced`.
Referentiality `generic_class` means a type or class, as in `AISIs hire researchers`; do not use it for one named institute.
Referentiality `anaphoric` means the expression depends on an antecedent, as in `The institute opened and it hired staff`; do not use it for an explicit name.
Referentiality `unclear` means the visible context cannot distinguish the other values, as in `Mercury changed`; do not use it when the context resolves the reference.
Contextual kind describes what the expression denotes in this source context, not what role it plays in the sentence.
Contextual kind `person` means one human or named group of humans, as in `Elizabeth Kelly spoke`; do not use it for a job title without a person.
Contextual kind `organization` means a standing institution or coordinated body, as in `Anthropic published`; do not use it for an institution's product.
Contextual kind `government` means a government, administration, or country expression with collective governmental agency, as in `France signed`; do not use it when the country is only a location.
Contextual kind `geopolitical_entity` means a political or territorial entity mentioned without clear governmental agency or location use, as in `the European Union has member states`; do not use it when `government` or `place` is directly supported.
Contextual kind `place` means a geographic location, as in `the summit occurred in France`; do not use it when a country acts through its government.
Contextual kind `event` means a bounded occurrence, as in `the AI Seoul Summit began`; do not use it for the institution that organized the occurrence.
Contextual kind `project` means a bounded named undertaking, as in `Project Maven continued`; do not use it for a standing institution.
Contextual kind `initiative` means a coordinated program or mission, as in `IndiaAI Mission announced a grant`; do not use it for a policy document or permanent institution.
Contextual kind `product` means a named tool, model, or commercial artifact, as in `Google Gemini competed`; do not use it for the Organization that created it.
Contextual kind `policy` means a named rule or policy instrument, as in `Directive 3000.09 applies`; do not use it for the agency that issued it.
Contextual kind `publication` means a named document or published work, as in `the Seoul Statement says`; do not use it for the event where it was announced.
Contextual kind `other` means the source use is clear but no named contextual kind fits; do not use it as a substitute for an available named kind.
Contextual kind `unclear` means the visible context cannot support one contextual kind; do not use it merely because several proposer hints were supplied.
Discourse role describes how the expression participates in the source statement, independently of contextual kind.
Discourse role `actor` means the expression performs or controls the main action, as in `Anthropic announced`; do not use it for the target of the action.
Discourse role `participant` means the expression takes part in an event or arrangement, as in `Anthropic joined the agreement`; do not use it merely because the expression appears in the sentence.
Discourse role `origin` means the expression supplies institutional or geographic origin, as in `European Union guidance`; do not use it for an actor that issues guidance through a verb.
Discourse role `location` means the expression identifies where something occurs, as in `the summit met in France`; do not use it for a country acting as a government.
Discourse role `object` means the expression is targeted by an action, as in `officials criticized Project Maven`; do not use it for the actor performing the action.
Discourse role `modifier` means the expression qualifies another expression, as in `the Anthropic policy`; do not use it when the expression independently performs the action.
Discourse role `other` means the source role is clear but no named role fits; do not use it as a substitute for an available named role.
Discourse role `unclear` means the visible context cannot support one discourse role; do not use it when grammar makes the role clear even if contextual kind is unclear.
Use only the visible source context and the candidate supplied by KoteKomi.
Do not use outside knowledge to replace the source context.
