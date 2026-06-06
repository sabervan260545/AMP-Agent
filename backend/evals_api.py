# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Evals REST API helpers for the AMP Agent evaluation harness.

Endpoints (wired from backend/app.py):
    GET  /api/evals/cases       -> list all cases from the YAML set
    GET  /api/evals/runs        -> list all stored run summaries
    GET  /api/evals/runs/<id>   -> full JSON of a single run
    POST /api/evals/run         -> trigger one run (synchronous)
    GET  /api/evals/health      -> module health (yaml loadable, counts)

This module is pure-Python; no Flask coupling. It only manipulates files
in agent/evals/ and delegates execution to agent.evals.runner.

The helpers here are written to be safe on an empty results/ directory.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Locate the evals package; works in both host and container layouts.
_AGENT_CANDIDATES = [
    Path("/app/agent"),  # inside the backend container
    Path(__file__).resolve().parent.parent / "agent",  # host dev checkout
]
AGENT_ROOT: Optional[Path] = next((p for p in _AGENT_CANDIDATES if p.exists()), None)

if AGENT_ROOT and str(AGENT_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT.parent))

EVALS_DIR = AGENT_ROOT / "evals" if AGENT_ROOT else None
DEFAULT_SET = EVALS_DIR / "golden_prompts.yaml" if EVALS_DIR else None
RESULTS_DIR = EVALS_DIR / "results" if EVALS_DIR else None


def _import_runner():
    """Lazy import so Flask app can start even if evals module has issues."""
    from agent.evals.runner import (  # noqa: WPS433 (local import is intentional)
        DEFAULT_API_BASE,
        dump_run,
        load_eval_set,
        run as run_set,
    )

    return {
        "DEFAULT_API_BASE": DEFAULT_API_BASE,
        "dump_run": dump_run,
        "load_eval_set": load_eval_set,
        "run_set": run_set,
    }


# ---------------------------------------------------------------------------
# Case listing
# ---------------------------------------------------------------------------


def list_cases(set_path: Optional[Path] = None) -> Dict[str, Any]:
    """Return the case metadata from the YAML set."""
    target = Path(set_path) if set_path else DEFAULT_SET
    if target is None or not target.exists():
        return {"error": "eval set not found", "cases": []}

    r = _import_runner()
    cases = r["load_eval_set"](target)
    return {
        "set_file": target.name,
        "count": len(cases),
        "cases": [
            {
                "id": c.id,
                "category": c.category,
                "language": c.language,
                "prompt": c.prompt,
                "tags": c.tags,
                "timeout_sec": c.timeout_sec,
                "suite": getattr(c, "suite", "default"),
                "expected_behaviors": [
                    {"name": b.name, "scorer": b.scorer, "weight": b.weight}
                    for b in c.expected_behaviors
                ],
            }
            for c in cases
        ],
    }


# ---------------------------------------------------------------------------
# Run listing / retrieval
# ---------------------------------------------------------------------------


def list_runs(limit: int = 50) -> Dict[str, Any]:
    """Return a lightweight summary of every run JSON stored under results/."""
    if RESULTS_DIR is None or not RESULTS_DIR.exists():
        return {"runs": [], "count": 0}

    files = sorted(RESULTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    # Resolve current reference id once so we can tag the matching run cheaply.
    try:
        ref_info = get_reference()
        ref_run_id = (ref_info.get("reference") or {}).get("run_id")
    except Exception:  # noqa: BLE001
        ref_run_id = None
    runs: List[Dict[str, Any]] = []
    for f in files:
        # Skip the reference sidecar itself.
        if f.name == _REFERENCE_SIDECAR:
            continue
        try:
            with f.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            runs.append(
                {
                    "run_id": data.get("run_id"),
                    "mode": data.get("mode"),
                    "started_at": data.get("started_at"),
                    "finished_at": data.get("finished_at"),
                    "total_cases": data.get("total_cases"),
                    "passed_cases": data.get("passed_cases"),
                    "avg_score": data.get("avg_score"),
                    "set_file": (data.get("meta") or {}).get("set_file"),
                    "file_name": f.name,
                    "size_bytes": f.stat().st_size,
                    "is_reference": (data.get("run_id") == ref_run_id) if ref_run_id else False,
                }
            )
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"Skipping malformed run file {f.name}: {exc}")
    return {"runs": runs, "count": len(runs), "reference_run_id": ref_run_id}


def get_run_detail(run_id: str) -> Optional[Dict[str, Any]]:
    """Return the full JSON payload for a single run."""
    if RESULTS_DIR is None or not RESULTS_DIR.exists():
        return None

    # Accept either bare run_id or full file name.
    candidates = [
        RESULTS_DIR / run_id,
        RESULTS_DIR / f"dryrun_{run_id}.json",
        RESULTS_DIR / f"live_{run_id}.json",
    ]
    # Fallback: scan files whose filename contains run_id.
    if not any(c.exists() for c in candidates):
        for f in RESULTS_DIR.glob("*.json"):
            if run_id in f.name:
                candidates.append(f)
                break

    for c in candidates:
        if c.exists():
            with c.open("r", encoding="utf-8") as fh:
                return json.load(fh)
    return None


# ---------------------------------------------------------------------------
# Run execution
# ---------------------------------------------------------------------------


def execute_run(
    mode: str = "dryrun",
    categories: Optional[List[str]] = None,
    case_ids: Optional[List[str]] = None,
    api_base: Optional[str] = None,
    set_file: Optional[str] = None,
    retry: int = 0,
    suites: Optional[List[str]] = None,
    concurrency: int = 1,
) -> Dict[str, Any]:
    """
    Synchronously execute an eval run and persist the result.

    Args:
        mode: 'dryrun' or 'live'.
        categories: restrict to these categories.
        case_ids: restrict to these case ids.
        api_base: override backend URL (live mode only).
        set_file: override YAML set path (absolute or relative to evals dir).
        retry: per-case extra attempts on transport failure (default: 0).

    Returns:
        The full RunResult dict, including the output file path under 'file_path'.
    """
    if DEFAULT_SET is None:
        raise RuntimeError("Evals module not initialized (AGENT_ROOT missing).")

    set_path: Path
    if set_file:
        candidate = Path(set_file)
        if not candidate.is_absolute():
            candidate = EVALS_DIR / candidate
        set_path = candidate
    else:
        set_path = DEFAULT_SET

    if not set_path.exists():
        raise FileNotFoundError(f"Eval set not found: {set_path}")

    r = _import_runner()
    effective_api_base = api_base or r["DEFAULT_API_BASE"]

    run_result = r["run_set"](
        set_path,
        mode,
        api_base=effective_api_base,
        categories=categories,
        case_ids=case_ids,
        retry=retry,
        suites=suites,
        concurrency=concurrency,
    )
    out_path = r["dump_run"](run_result)
    payload = run_result.to_dict()
    payload["file_path"] = str(out_path)
    payload["file_name"] = out_path.name
    return payload


# ---------------------------------------------------------------------------
# Replay (recompute scorers on a stored run, no Agent invocation)
# ---------------------------------------------------------------------------
#
# Given an existing run_id, re-evaluate each case using:
#   * the response_full (or response_preview as fallback) and tool_calls saved
#     in that run,
#   * the CURRENT expected_behaviors from the YAML set file.
# This lets you change scorer weights / rubrics / llm_judge prompts and
# instantly see the effect WITHOUT re-running the (slow, expensive) Agent.

def replay_run(source_run_id: str, set_file: Optional[str] = None) -> Dict[str, Any]:
    if not source_run_id:
        raise ValueError("source_run_id required")
    src = get_run_detail(source_run_id)
    if src is None:
        raise FileNotFoundError(f"source run not found: {source_run_id}")

    # Resolve which yaml set to load (mirrors execute_run logic).
    if DEFAULT_SET is None:
        raise RuntimeError("Evals module not initialized (AGENT_ROOT missing).")
    if set_file:
        candidate = Path(set_file)
        if not candidate.is_absolute():
            candidate = EVALS_DIR / candidate
        set_path = candidate
    else:
        # Prefer the set the source run used; fallback to DEFAULT_SET.
        src_set = (src.get("meta") or {}).get("set_file")
        set_path = (EVALS_DIR / src_set) if src_set and EVALS_DIR else DEFAULT_SET
        if not set_path or not set_path.exists():
            set_path = DEFAULT_SET
    if not set_path.exists():
        raise FileNotFoundError(f"Eval set not found: {set_path}")

    r = _import_runner()
    cases = r["load_eval_set"](set_path)
    case_by_id = {c.id: c for c in cases}

    # Re-import schema/runner pieces for in-process scoring.
    from agent.evals.runner import score_case, new_run_id  # type: ignore
    import time as _time

    new_cases: List[Dict[str, Any]] = []
    fallback_count = 0
    missing_in_yaml: List[str] = []
    for src_case in (src.get("cases") or []):
        cid = src_case.get("case_id")
        case = case_by_id.get(cid)
        if case is None:
            missing_in_yaml.append(cid)
            new_cases.append({
                **src_case,
                "replay_note": "case_id no longer in yaml; original verdict preserved",
            })
            continue
        response = src_case.get("response_full")
        used_full = True
        if not response:
            response = src_case.get("response_preview") or ""
            used_full = False
            fallback_count += 1
        tool_calls = src_case.get("tool_calls") or []
        t0 = _time.time()
        verdicts, score, passed = score_case(case, response, tool_calls)
        new_cases.append({
            "case_id": cid,
            "passed": bool(passed),
            "score": round(float(score), 4),
            "latency_ms": round((_time.time() - t0) * 1000, 2),
            "verdicts": [
                {"name": v.name, "passed": v.passed, "score": v.score, "reason": v.reason}
                for v in verdicts
            ],
            "response_preview": (response[:200] if response else ""),
            "tool_calls": tool_calls,
            "error": None if used_full else "replay used response_preview (truncated to 200 chars)",
        })

    total = len(new_cases)
    passed_n = sum(1 for c in new_cases if c.get("passed"))
    avg = (sum(float(c.get("score") or 0.0) for c in new_cases) / total) if total else 0.0

    rid = new_run_id()
    payload = {
        "run_id": rid,
        "mode": "replay",
        "started_at": datetime.now().isoformat(),
        "finished_at": datetime.now().isoformat(),
        "total_cases": total,
        "passed_cases": passed_n,
        "avg_score": round(avg, 4),
        "cases": new_cases,
        "meta": {
            "set_file": set_path.name if set_path else None,
            "replay_of": source_run_id,
            "source_mode": src.get("mode"),
            "source_avg_score": src.get("avg_score"),
            "fallback_to_preview_count": fallback_count,
            "missing_case_ids": missing_in_yaml,
            "env": (src.get("meta") or {}).get("env"),  # carry forward provenance
        },
    }
    out_path = RESULTS_DIR / f"replay_{rid}.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    payload["file_path"] = str(out_path)
    payload["file_name"] = out_path.name
    return payload


# ---------------------------------------------------------------------------
# Snapshot baseline (reference run) & diff
# ---------------------------------------------------------------------------
#
# A "reference" run is simply a pointer to a previous run_id, stored in a
# lightweight sidecar JSON under results/. This keeps the mechanism zero
# intrusion: existing run files are untouched, and removing the sidecar
# restores default behaviour.

_REFERENCE_SIDECAR = "_reference.json"


def _reference_path() -> Optional[Path]:
    if RESULTS_DIR is None:
        return None
    return RESULTS_DIR / _REFERENCE_SIDECAR


def get_reference() -> Dict[str, Any]:
    """Return the currently marked reference run (or empty dict)."""
    p = _reference_path()
    if p is None or not p.exists():
        return {"reference": None}
    try:
        with p.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {"reference": None}

    # Enrich with the target run summary so the UI can render a one-liner.
    ref_id = data.get("run_id")
    summary = None
    if ref_id:
        detail = get_run_detail(ref_id)
        if detail:
            summary = {
                "run_id": detail.get("run_id"),
                "mode": detail.get("mode"),
                "started_at": detail.get("started_at"),
                "total_cases": detail.get("total_cases"),
                "passed_cases": detail.get("passed_cases"),
                "avg_score": detail.get("avg_score"),
                "set_file": (detail.get("meta") or {}).get("set_file"),
            }
    return {
        "reference": data,
        "summary": summary,
    }


def set_reference(run_id: str, note: Optional[str] = None) -> Dict[str, Any]:
    """Mark a given run as the reference baseline. Overwrites any previous one."""
    if not run_id:
        raise ValueError("run_id is required")
    detail = get_run_detail(run_id)
    if detail is None:
        raise FileNotFoundError(f"run not found: {run_id}")
    p = _reference_path()
    if p is None:
        raise RuntimeError("Evals results directory not initialized")
    payload = {
        "run_id": detail.get("run_id"),
        "marked_at": datetime.now().isoformat(),
        "note": note or "",
        "source_mode": detail.get("mode"),
        "source_set_file": (detail.get("meta") or {}).get("set_file"),
    }
    with p.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    return payload


def clear_reference() -> Dict[str, Any]:
    """Remove the reference marker. Idempotent."""
    p = _reference_path()
    existed = bool(p and p.exists())
    if existed:
        try:
            p.unlink()
        except OSError as exc:  # noqa: BLE001
            return {"cleared": False, "error": repr(exc)}
    return {"cleared": existed}


def _summarize_case(c: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "case_id": c.get("case_id"),
        "passed": bool(c.get("passed")),
        "score": float(c.get("score") or 0.0),
        "latency_ms": c.get("latency_ms"),
    }


def diff_runs(a_run_id: str, b_run_id: str) -> Dict[str, Any]:
    """Compute a case-level diff between two runs.

    Convention: A is the reference/older side, B is the current/newer side.
    Each diff entry carries delta = B.score - A.score so improvements are
    positive and regressions are negative.
    """
    if not a_run_id or not b_run_id:
        raise ValueError("Both a and b run_ids are required")
    da = get_run_detail(a_run_id)
    db = get_run_detail(b_run_id)
    if da is None:
        raise FileNotFoundError(f"run A not found: {a_run_id}")
    if db is None:
        raise FileNotFoundError(f"run B not found: {b_run_id}")

    a_by_id = {c.get("case_id"): c for c in (da.get("cases") or [])}
    b_by_id = {c.get("case_id"): c for c in (db.get("cases") or [])}
    all_ids = sorted(set(a_by_id) | set(b_by_id))

    entries: List[Dict[str, Any]] = []
    regressions = improvements = unchanged = only_in_a = only_in_b = 0
    for cid in all_ids:
        ca = a_by_id.get(cid)
        cb = b_by_id.get(cid)
        if ca and cb:
            a_score = float(ca.get("score") or 0.0)
            b_score = float(cb.get("score") or 0.0)
            delta = round(b_score - a_score, 4)
            a_passed = bool(ca.get("passed"))
            b_passed = bool(cb.get("passed"))
            # Severity: new failure > regression > improvement > unchanged
            if a_passed and not b_passed:
                severity = "new_failure"
                regressions += 1
            elif not a_passed and b_passed:
                severity = "new_pass"
                improvements += 1
            elif delta < -0.05:
                severity = "regression"
                regressions += 1
            elif delta > 0.05:
                severity = "improvement"
                improvements += 1
            else:
                severity = "unchanged"
                unchanged += 1
            entries.append({
                "case_id": cid,
                "severity": severity,
                "delta": delta,
                "a": _summarize_case(ca),
                "b": _summarize_case(cb),
            })
        elif ca and not cb:
            only_in_a += 1
            entries.append({
                "case_id": cid,
                "severity": "only_in_a",
                "delta": None,
                "a": _summarize_case(ca),
                "b": None,
            })
        elif cb and not ca:
            only_in_b += 1
            entries.append({
                "case_id": cid,
                "severity": "only_in_b",
                "delta": None,
                "a": None,
                "b": _summarize_case(cb),
            })

    # Sort: most-severe first, then by absolute delta
    severity_order = {
        "new_failure": 0, "regression": 1, "only_in_a": 2, "only_in_b": 3,
        "improvement": 4, "new_pass": 5, "unchanged": 6,
    }
    entries.sort(key=lambda e: (severity_order.get(e["severity"], 9), -abs(e["delta"] or 0)))

    return {
        "a": {
            "run_id": da.get("run_id"),
            "mode": da.get("mode"),
            "avg_score": da.get("avg_score"),
            "total_cases": da.get("total_cases"),
            "passed_cases": da.get("passed_cases"),
            "set_file": (da.get("meta") or {}).get("set_file"),
        },
        "b": {
            "run_id": db.get("run_id"),
            "mode": db.get("mode"),
            "avg_score": db.get("avg_score"),
            "total_cases": db.get("total_cases"),
            "passed_cases": db.get("passed_cases"),
            "set_file": (db.get("meta") or {}).get("set_file"),
        },
        "avg_delta": round(
            float(db.get("avg_score") or 0.0) - float(da.get("avg_score") or 0.0),
            4,
        ),
        "summary": {
            "regressions": regressions,
            "improvements": improvements,
            "unchanged": unchanged,
            "only_in_a": only_in_a,
            "only_in_b": only_in_b,
            "total": len(entries),
        },
        "entries": entries,
    }


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def evals_health() -> Dict[str, Any]:
    """Report whether the evals module can load its default set."""
    info: Dict[str, Any] = {
        "agent_root": str(AGENT_ROOT) if AGENT_ROOT else None,
        "evals_dir": str(EVALS_DIR) if EVALS_DIR else None,
        "results_dir": str(RESULTS_DIR) if RESULTS_DIR else None,
        "default_set": str(DEFAULT_SET) if DEFAULT_SET else None,
        "results_count": 0,
        "yaml_loadable": False,
        "case_count": 0,
        "error": None,
    }
    if RESULTS_DIR and RESULTS_DIR.exists():
        info["results_count"] = len(list(RESULTS_DIR.glob("*.json")))
    try:
        payload = list_cases()
        info["yaml_loadable"] = "error" not in payload
        info["case_count"] = payload.get("count", 0)
    except Exception as exc:  # noqa: BLE001
        info["error"] = repr(exc)
    return info


__all__ = [
    "list_cases",
    "list_runs",
    "get_run_detail",
    "execute_run",
    "evals_health",
    "get_reference",
    "set_reference",
    "clear_reference",
    "diff_runs",
    "DEFAULT_SET",
    "RESULTS_DIR",
]
