from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol


class SearchRunner(Protocol):
    def search(
        self,
        *,
        query: str,
        mode: str = "hybrid",
        filters: dict[str, Any] | None = None,
        limit: int = 5,
        resume: bool = False,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class GoldenQuery:
    name: str
    query_class: str
    query: str
    mode: str = "hybrid"
    filters: dict[str, Any] | None = None
    limit: int = 5
    resume: bool = False


@dataclass(frozen=True)
class BaselineGoldenResult:
    gmail_ids: list[str]


@dataclass
class QueryParityResult:
    name: str
    query_class: str
    passed: bool
    baseline_ids: list[str]
    adapter_ids: list[str]
    missing_ids: list[str]
    extra_ids: list[str]
    citations_ok: bool
    notes: list[str]


@dataclass
class ClassParitySummary:
    query_class: str
    total: int
    passed: int
    failed: int
    parity_score: float


@dataclass
class ParityReport:
    total: int
    passed: int
    failed: int
    parity_score: float
    by_class: list[ClassParitySummary]
    results: list[QueryParityResult]


def format_parity_report(report: ParityReport) -> str:
    lines = [
        f"Overall parity: {report.passed}/{report.total} ({report.parity_score:.1%})",
        "Class parity:",
    ]
    for row in report.by_class:
        lines.append(
            f"- {row.query_class}: {row.passed}/{row.total} passed ({row.parity_score:.1%})"
        )

    failed = [row for row in report.results if not row.passed]
    if failed:
        lines.append("Gaps:")
        for row in failed:
            note = "; ".join(row.notes) if row.notes else "unspecified mismatch"
            lines.append(f"- {row.name} [{row.query_class}]: {note}")
    else:
        lines.append("Gaps: none")
    return "\n".join(lines)


_GMAIL_LINK_RE = re.compile(r"^https://mail\.google\.com/mail/u/\d+/#(?:inbox|all)/[^\s]+$")


def _extract_gmail_ids(payload: dict[str, Any], *, limit: int) -> list[str]:
    out: list[str] = []
    for row in payload.get("results") or []:
        gmail_id = row.get("gmail_id")
        if not gmail_id:
            continue
        out.append(str(gmail_id))
        if len(out) >= limit:
            break
    return out


def _citations_ok(payload: dict[str, Any]) -> bool:
    for row in payload.get("results") or []:
        link = str(row.get("link") or "")
        if not link:
            return False
        if not _GMAIL_LINK_RE.match(link):
            return False
    return True


def _summarize_classes(results: list[QueryParityResult]) -> list[ClassParitySummary]:
    grouped: dict[str, dict[str, int]] = {}
    for row in results:
        bucket = grouped.setdefault(row.query_class, {"total": 0, "passed": 0})
        bucket["total"] += 1
        if row.passed:
            bucket["passed"] += 1

    summaries: list[ClassParitySummary] = []
    for query_class in sorted(grouped):
        total = grouped[query_class]["total"]
        passed = grouped[query_class]["passed"]
        failed = total - passed
        score = float(passed / total) if total else 0.0
        summaries.append(
            ClassParitySummary(
                query_class=query_class,
                total=total,
                passed=passed,
                failed=failed,
                parity_score=score,
            )
        )
    return summaries


def run_golden_parity(
    *,
    golden_queries: list[GoldenQuery],
    baseline_results: dict[str, BaselineGoldenResult],
    adapter_runner: SearchRunner,
) -> ParityReport:
    results: list[QueryParityResult] = []

    for query in golden_queries:
        baseline = baseline_results.get(query.name)
        if baseline is None:
            results.append(
                QueryParityResult(
                    name=query.name,
                    query_class=query.query_class,
                    passed=False,
                    baseline_ids=[],
                    adapter_ids=[],
                    missing_ids=[],
                    extra_ids=[],
                    citations_ok=False,
                    notes=["missing baseline result"],
                )
            )
            continue

        adapter_payload = adapter_runner.search(
            query=query.query,
            mode=query.mode,
            filters=query.filters,
            limit=query.limit,
            resume=query.resume,
        )
        adapter_ids = _extract_gmail_ids(adapter_payload, limit=query.limit)
        baseline_ids = list(baseline.gmail_ids)[: query.limit]

        missing_ids = [gid for gid in baseline_ids if gid not in adapter_ids]
        extra_ids = [gid for gid in adapter_ids if gid not in baseline_ids]
        same_order = adapter_ids == baseline_ids
        citations_ok = _citations_ok(adapter_payload)

        notes: list[str] = []
        if missing_ids:
            notes.append(f"missing ids vs baseline: {missing_ids}")
        if extra_ids:
            notes.append(f"extra ids vs baseline: {extra_ids}")
        if not same_order and not missing_ids and not extra_ids:
            notes.append("id ordering mismatch vs baseline")
        if not citations_ok:
            notes.append("citation link format mismatch")

        passed = same_order and citations_ok
        results.append(
            QueryParityResult(
                name=query.name,
                query_class=query.query_class,
                passed=passed,
                baseline_ids=baseline_ids,
                adapter_ids=adapter_ids,
                missing_ids=missing_ids,
                extra_ids=extra_ids,
                citations_ok=citations_ok,
                notes=notes,
            )
        )

    total = len(results)
    passed = sum(1 for row in results if row.passed)
    failed = total - passed
    score = float(passed / total) if total else 0.0

    return ParityReport(
        total=total,
        passed=passed,
        failed=failed,
        parity_score=score,
        by_class=_summarize_classes(results),
        results=results,
    )
