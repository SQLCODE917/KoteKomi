"""Production ownership of one source-exact half-open range."""

from __future__ import annotations

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceRange(BaseModel):
    """One source-exact half-open range bound to its own text."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    text: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.end - self.start != len(self.text):
            raise ValueError("Source range does not match its text length.")
        return self
