"""ClawInboxRAG backend modules."""

from .legacy_adapter import LegacyGmailRagAdapter, LegacyValidationError
from .parity_harness import BaselineGoldenResult, GoldenQuery, format_parity_report, run_golden_parity

__all__ = [
    "LegacyGmailRagAdapter",
    "LegacyValidationError",
    "BaselineGoldenResult",
    "GoldenQuery",
    "run_golden_parity",
    "format_parity_report",
]
