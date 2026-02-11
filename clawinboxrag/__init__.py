"""ClawInboxRAG backend modules."""

from .legacy_adapter import LegacyGmailRagAdapter, LegacyValidationError

__all__ = ["LegacyGmailRagAdapter", "LegacyValidationError"]
