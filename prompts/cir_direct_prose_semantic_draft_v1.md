Read the paragraph marked `[direct_prose]`.

Decide whether that paragraph supports one atomic relationship claim.

Use only that paragraph as direct evidence.

Do not use a heading, nearby paragraph, reference list, or outside knowledge as direct evidence.

Return exactly one plain-text response.

Return a claim only when the paragraph names the subject and object exactly.

Copy each claim `subject` and organization `object` as an exact contiguous substring of the
direct prose. Preserve spelling, capitalization, and abbreviations. Do not expand, shorten,
or normalize a name.

For a supported relationship, return exactly these five ordered lines and stop after the fifth line.

```text
outcome: claim
subject: <organization name from the direct prose>
relation: <ordinary-language relation label>
object_kind: organization
object: <organization name from the direct prose>
```

Use `object_kind: literal` only when the direct prose supports a literal object.

For a literal object, replace only the `object_kind` and `object` values.

For no supported relationship, return exactly these two ordered lines and stop after the second line.

```text
outcome: abstain
reason: <non-empty reason>
```

Do not return JSON, Markdown, a code fence, an evidence identifier, a KoteKomi identifier,
an offset, a source range, or an explanation.

Do not add blank lines before, between, or after the required lines.
