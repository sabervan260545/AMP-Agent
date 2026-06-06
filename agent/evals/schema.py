# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Data classes for the evaluation harness.

All structures are plain dataclasses so they can serialize to JSON/YAML
without any external dependency (beyond the standard library).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ExpectedBehavior:
    """
    A single expected behavior for a test case.

    Attributes:
        name: Behavior identifier (e.g. "calls_three_generators").
        scorer: Name of the scorer function to dispatch to.
        params: Scorer-specific parameters.
        weight: Weight when aggregating into the case-level score.
    """

    name: str
    scorer: str
    params: Dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0


@dataclass
class TestCase:
    """
    A single benchmark case.

    Attributes:
        id: Stable identifier used in reports (e.g. "bench_003").
        category: Loose grouping label (e.g. "generation", "rag").
        prompt: The user message sent to the Agent.
        language: Target language hint ("en" or "zh"), forwarded to the Agent.
        expected_behaviors: List of behaviors that must hold on the response.
        tags: Optional free-form tags for filtering runs.
        timeout_sec: Per-case timeout when invoking the Agent.
        suite: Bundle label for tiered runs (e.g. "smoke", "nightly", "release").
            Defaults to "default" when a case does not declare one. Cases without
            an explicit suite are still included in unfiltered runs.
    """

    id: str
    category: str
    prompt: str
    language: str = "en"
    expected_behaviors: List[ExpectedBehavior] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    timeout_sec: int = 180
    suite: str = "default"


@dataclass
class BehaviorVerdict:
    """Per-behavior scoring result."""

    name: str
    passed: bool
    score: float
    reason: str


@dataclass
class CaseResult:
    """Per-case aggregated result."""

    case_id: str
    passed: bool
    score: float
    latency_ms: float
    verdicts: List[BehaviorVerdict] = field(default_factory=list)
    response_preview: str = ""
    response_full: Optional[str] = None  # full text, retained for replay/judge re-runs
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class RunResult:
    """
    Top-level result object for a full eval run.

    Attributes:
        run_id: Timestamp-based identifier (e.g. "20260430_120000").
        started_at: ISO-8601 start time.
        finished_at: ISO-8601 finish time.
        mode: "dryrun" or "live".
        total_cases: Number of cases attempted.
        passed_cases: Number of cases that passed overall.
        avg_score: Mean case-level score across all cases.
        cases: Per-case detailed results.
        meta: Arbitrary metadata (eval set name, agent version, etc.).
    """

    run_id: str
    started_at: str
    finished_at: str
    mode: str
    total_cases: int
    passed_cases: int
    avg_score: float
    cases: List[CaseResult] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def new_run_id() -> str:
    """Timestamp-based run identifier, safe for filenames."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")
