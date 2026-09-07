"""Governed semantic outcomes for standing-fact qualification."""

from enum import StrEnum


class StandingFactQualificationOutcome(StrEnum):
    SUPPORTED_STANDING_FACT = "supported_standing_fact"
    EVENT_NOT_STANDING = "event_not_standing"
    INCOMPLETE_OR_WRONG_ARGUMENTS = "incomplete_or_wrong_arguments"
    UNSUPPORTED = "unsupported"
    AMBIGUOUS = "ambiguous"
