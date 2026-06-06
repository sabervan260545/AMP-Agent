# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Evaluation runner (Step 2a: dry-run + live mode against the real Agent API).

Usage:
    # Dry run - no real Agent calls, uses a fixed mock response.
    python -m agent.evals.runner --dry-run

    # Live mode - POST each prompt to /api/chat, stream SSE, and reconstruct
    # tool calls from the tool_call_logger JSONL files (time-window scan).
    python -m agent.evals.runner --live --api-base http://localhost:5000

Design:
    1. Load the YAML eval set into TestCase objects.
    2. For each case:
         - dry-run  -> use MOCK_RESPONSE below (skeleton validation only).
         - live     -> POST to /api/chat (SSE) and collect the streamed text,
                      then scan agent/logs/session_*.jsonl for tool invocations
                      whose timestamps fall inside the request window.
       Apply every expected_behavior scorer to produce BehaviorVerdicts.
       Aggregate into a CaseResult.
    3. Aggregate CaseResults into a RunResult and dump to results/<run_id>.json.

This file is pure stdlib + PyYAML. It has zero coupling to the running Agent
code paths and therefore cannot break any existing service.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Allow running as `python -m agent.evals.runner` or direct script.
_HERE = Path(__file__).resolve().parent
if str(_HERE.parent.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent.parent))

from agent.evals.schema import (  # noqa: E402
    BehaviorVerdict,
    CaseResult,
    ExpectedBehavior,
    RunResult,
    TestCase,
    new_run_id,
)
from agent.evals.scorers import SCORER_REGISTRY  # noqa: E402

logger = logging.getLogger("evals.runner")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEFAULT_SET = _HERE / "golden_prompts.yaml"
RESULTS_DIR = _HERE / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# tool_call_logger writes JSONL session files under this directory (hardcoded).
# The same path is available on the host and inside the backend container.
TOOL_LOG_DIR_PRIMARY = Path("/data/amp-generator-platform/agent/logs")
TOOL_LOG_DIR_FALLBACK = Path("/app/agent/logs")  # mounted volume alias inside container

DEFAULT_API_BASE = os.environ.get("EVALS_API_BASE", "http://localhost:5000")


# ---------------------------------------------------------------------------
# Environment fingerprint (recorded in every RunResult.meta.env for traceability)
# ---------------------------------------------------------------------------

_CACHED_ENV: Optional[Dict[str, Any]] = None


def _safe_call(cmd: List[str], cwd: Optional[Path] = None) -> Optional[str]:
    """Run a subprocess and return stripped stdout, or None on any failure."""
    try:
        out = subprocess.check_output(
            cmd,
            stderr=subprocess.DEVNULL,
            cwd=str(cwd) if cwd else None,
            timeout=3,
        )
        return out.decode("utf-8", errors="replace").strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def capture_env_fingerprint() -> Dict[str, Any]:
    """Collect a lightweight reproducibility fingerprint for the current process.

    Fields are all best-effort: any probe that fails becomes None rather than
    raising. The result is cached so repeated evals in one process pay the
    probe cost only once.
    """
    global _CACHED_ENV
    if _CACHED_ENV is not None:
        return dict(_CACHED_ENV)

    # Walk up from this file to find a .git directory. If none is found
    # (common inside minimal Docker images where .git is not mounted),
    # fall back to a list of well-known host paths.
    here = Path(__file__).resolve()
    repo_root: Optional[Path] = None
    for parent in [here, *here.parents]:
        if (parent / ".git").exists():
            repo_root = parent
            break
    if repo_root is None:
        for candidate in (
            Path("/data/amp-generator-platform"),
            Path("/workspace"),
            Path.cwd(),
        ):
            if (candidate / ".git").exists():
                repo_root = candidate
                break

    # Allow explicit override via environment variable for CI and containers
    # where git is unavailable (e.g. set EVALS_GIT_COMMIT in docker-compose).
    git_commit = os.environ.get("EVALS_GIT_COMMIT") or (
        _safe_call(["git", "rev-parse", "--short", "HEAD"], cwd=repo_root) if repo_root else None
    )
    git_branch = os.environ.get("EVALS_GIT_BRANCH") or (
        _safe_call(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root) if repo_root else None
    )
    git_dirty_raw = (
        _safe_call(["git", "status", "--porcelain"], cwd=repo_root) if repo_root else None
    )
    git_dirty: Optional[bool] = (bool(git_dirty_raw) if git_dirty_raw is not None else None)

    env: Dict[str, Any] = {
        "git_commit": git_commit,
        "git_branch": git_branch,
        "git_dirty": git_dirty,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
        "user": os.environ.get("USER") or os.environ.get("USERNAME"),
        "captured_at": datetime.now().isoformat(),
    }
    # Optional: system-prompt fingerprint. Gives a deterministic version tag
    # for the Agent's instruction template, so a regression can be attributed
    # to a prompt change vs. a code change. Best-effort: a failure here is
    # never fatal for the run.
    try:
        import hashlib
        prompt_text: Optional[str] = None
        prompt_source: Optional[str] = None

        # Strategy A: try calling build_system_prompt() for the most accurate
        # runtime fingerprint. Several candidate module paths are tried because
        # this repo has relocated the context engine a few times.
        for mod_path in (
            "agent.utils.context_engine",
            "agent.context_engine",
            "utils.context_engine",
            "context_engine",
        ):
            try:
                import importlib
                mod = importlib.import_module(mod_path)
                fn = getattr(mod, "build_system_prompt", None)
                if callable(fn):
                    prompt_text = fn("en")
                    prompt_source = f"{mod_path}.build_system_prompt()"
                    break
            except Exception:  # noqa: BLE001
                continue

        # Strategy B: fall back to hashing the source file(s) that define the
        # system prompt. This still catches prompt changes committed to the
        # repo, even when the live module cannot be imported (missing deps).
        if not prompt_text:
            search_roots = []
            here = Path(__file__).resolve()
            # Walk up to find an 'agent' dir
            for parent in here.parents:
                agent_dir = parent / "agent"
                if agent_dir.is_dir():
                    search_roots.append(agent_dir)
                    break
            for cand in (
                Path("/app/agent"),
                Path("/data/amp-generator-platform/agent"),
            ):
                if cand.is_dir() and cand not in search_roots:
                    search_roots.append(cand)

            src_hits: List[Path] = []
            for root in search_roots:
                for name in ("utils/context_engine.py", "context_engine.py",
                              "core/__init__.py"):
                    p = root / name
                    if p.is_file():
                        src_hits.append(p)
                # don't scan more than one root once we have hits
                if src_hits:
                    break

            if src_hits:
                blob = b"\n".join(p.read_bytes() for p in src_hits)
                prompt_text = blob.decode("utf-8", errors="replace")
                prompt_source = "source-hash:" + ",".join(p.name for p in src_hits)

        if prompt_text:
            h = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:12]
            env["prompt"] = {
                "source": prompt_source,
                "sha256_12": h,
                "length": len(prompt_text),
                "version": os.environ.get("EVALS_PROMPT_VERSION"),
            }
    except Exception as exc:  # noqa: BLE001
        logger.debug("prompt fingerprint failed: %r", exc)
    _CACHED_ENV = env
    return dict(env)

# Fixed mock response used in --dry-run so the skeleton can be validated end-to-end.
MOCK_RESPONSE = (
    "Here is a quick comparison of three generators: AMP-Designer, HydrAMP and "
    "Diff-AMP. They all target Gram-negative bacteria but differ in 优点 / 缺点. "
    "The membrane-disrupting mechanism involves lipid bilayer pore formation. "
    "Designed 5 peptides successfully."
)
MOCK_TOOL_CALLS = [
    {"name": "tool_generate_amp", "params": {"generator": "amp_designer"}},
    {"name": "tool_generate_amp", "params": {"generator": "hydramp"}},
    {"name": "tool_generate_amp", "params": {"generator": "diff_amp"}},
    {"name": "search_knowledge", "params": {"query": "AMP mechanism"}},
    {"name": "tool_batch_evaluate", "params": {}},
]


def load_eval_set(path: Path) -> List[TestCase]:
    """Load a YAML eval set into a list of TestCase objects."""
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    cases_raw = raw.get("cases", [])
    cases: List[TestCase] = []
    for c in cases_raw:
        behaviors = [ExpectedBehavior(**b) for b in c.get("expected_behaviors", [])]
        cases.append(
            TestCase(
                id=c["id"],
                category=c.get("category", "uncategorized"),
                prompt=c["prompt"],
                language=c.get("language", "en"),
                expected_behaviors=behaviors,
                tags=c.get("tags", []),
                timeout_sec=int(c.get("timeout_sec", 180)),
                suite=str(c.get("suite", "default")),
            )
        )
    logger.info(f"Loaded {len(cases)} case(s) from {path.name}")
    return cases


def invoke_agent(
    case: TestCase,
    mode: str,
    api_base: str = DEFAULT_API_BASE,
    run_id: Optional[str] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Dispatch the actual invocation.

    Returns:
        (response_text, tool_calls)

    dry-run mode returns a fixed mock. live mode POSTs to /api/chat and then
    reconstructs tool_calls from tool_call_logger JSONL files using a time
    window around the request. When run_id is supplied, it is forwarded as
    the X-Eval-Run-Id header so tool-call logs can later be joined back to
    the owning eval run without any backend change (headers are merely
    informational; unknown headers are ignored by the Flask handler).
    """
    if mode == "dryrun":
        # Simulate a small latency so latency_ms is non-zero in reports.
        time.sleep(0.05)
        return MOCK_RESPONSE, list(MOCK_TOOL_CALLS)

    if mode == "live":
        return _live_invoke(case, api_base, run_id=run_id)

    raise ValueError(f"Unknown mode: {mode}")


def _resolve_log_dir() -> Optional[Path]:
    """Return the first existing tool-call-logger directory, or None."""
    for candidate in (TOOL_LOG_DIR_PRIMARY, TOOL_LOG_DIR_FALLBACK):
        if candidate.exists():
            return candidate
    return None


def _live_invoke(
    case: TestCase,
    api_base: str,
    run_id: Optional[str] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """POST the prompt to /api/chat (SSE), collect text, reconstruct tool_calls.

    Optional run_id is echoed in an X-Eval-Run-Id header so downstream
    log pipelines can correlate tool-call entries with the originating run.
    """
    url = api_base.rstrip("/") + "/api/chat"
    payload = json.dumps({"message": case.prompt}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if run_id:
        headers["X-Eval-Run-Id"] = str(run_id)
        headers["X-Eval-Case-Id"] = str(case.id)
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers=headers,
    )

    # Capture wall-clock window so we can filter tool-logger entries afterwards.
    start_wall = datetime.now()
    time.sleep(0.01)  # tiny nudge so we never collide with pre-existing entries

    response_chunks: List[str] = []
    try:
        with urllib.request.urlopen(req, timeout=case.timeout_sec) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                try:
                    obj = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                ctype = obj.get("type")
                if ctype == "text":
                    content = obj.get("content", "")
                    if isinstance(content, str):
                        response_chunks.append(content)
                elif ctype == "end":
                    break
                elif ctype == "error":
                    raise RuntimeError(f"Agent error: {obj.get('content')}")
                # html_table / pdb_data / plotly_html are ignored for scoring purposes
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to reach {url}: {exc}") from exc

    end_wall = datetime.now()

    tool_calls = _collect_tool_calls(start_wall, end_wall)
    full_text = "".join(response_chunks)
    return full_text, tool_calls


def _collect_tool_calls(start: datetime, end: datetime) -> List[Dict[str, Any]]:
    """Scan tool_call_logger JSONL files for entries timestamped within [start, end]."""
    log_dir = _resolve_log_dir()
    if log_dir is None:
        logger.warning("No tool-logger directory found; tool_calls will be empty.")
        return []

    # Only inspect the most recent session files (avoids scanning years of history).
    files = sorted(
        log_dir.glob("session_*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:5]

    calls: List[Dict[str, Any]] = []
    for f in files:
        try:
            with f.open("r", encoding="utf-8") as fh:
                for raw in fh:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        e = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    ts_str = e.get("timestamp")
                    if not ts_str:
                        continue
                    try:
                        ts = datetime.fromisoformat(ts_str)
                    except ValueError:
                        continue
                    if start <= ts <= end:
                        calls.append(
                            {
                                "name": e.get("tool_name", "unknown"),
                                "params": e.get("params", {}),
                                "success": e.get("success", True),
                                "latency_ms": e.get("latency_ms", 0),
                                "timestamp": ts_str,
                            }
                        )
        except OSError:
            continue

    calls.sort(key=lambda c: c.get("timestamp", ""))
    return calls


def score_case(
    case: TestCase,
    response: str,
    tool_calls: List[Dict[str, Any]],
) -> Tuple[List[BehaviorVerdict], float, bool]:
    """Apply every expected_behavior scorer to the response/tool_calls."""
    verdicts: List[BehaviorVerdict] = []
    total_weight = 0.0
    weighted_score = 0.0

    for beh in case.expected_behaviors:
        scorer = SCORER_REGISTRY.get(beh.scorer)
        if scorer is None:
            verdicts.append(
                BehaviorVerdict(
                    name=beh.name,
                    passed=False,
                    score=0.0,
                    reason=f"Unknown scorer: {beh.scorer}",
                )
            )
            total_weight += beh.weight
            continue

        # Auto-inject the user prompt so llm_judge (and any future context-aware
        # scorer) can evaluate the response against the original ask without
        # requiring every YAML entry to duplicate it.
        params = dict(beh.params or {})
        if "user_prompt" not in params:
            params["user_prompt"] = case.prompt
        passed, score, reason = scorer(response, tool_calls, params)
        verdicts.append(
            BehaviorVerdict(name=beh.name, passed=passed, score=score, reason=reason)
        )
        total_weight += beh.weight
        weighted_score += score * beh.weight

    case_score = weighted_score / total_weight if total_weight > 0 else 0.0
    case_passed = all(v.passed for v in verdicts) if verdicts else False
    return verdicts, case_score, case_passed


def run_case(
    case: TestCase,
    mode: str,
    api_base: str = DEFAULT_API_BASE,
    retry: int = 0,
    run_id: Optional[str] = None,
) -> CaseResult:
    """Run a single case and return its CaseResult.

    Args:
        retry: number of additional attempts on failure (not on scorer fail).
            retry=0 keeps legacy behaviour (single attempt, no retry).
        run_id: optional owning run id, forwarded to invoke_agent for
            observability headers (X-Eval-Run-Id).
    """
    attempts = max(1, retry + 1)
    last_exc: Optional[BaseException] = None
    for attempt in range(1, attempts + 1):
        start = time.time()
        try:
            response, tool_calls = invoke_agent(case, mode, api_base=api_base, run_id=run_id)
            verdicts, score, passed = score_case(case, response, tool_calls)
            return CaseResult(
                case_id=case.id,
                passed=passed,
                score=round(score, 4),
                latency_ms=round((time.time() - start) * 1000, 2),
                verdicts=verdicts,
                response_preview=response[:200],
                response_full=response,
                tool_calls=tool_calls,
                # Surface attempt metadata only when more than one attempt was needed.
                error=(f"succeeded on attempt {attempt}/{attempts}" if attempt > 1 else None),
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < attempts:
                logger.warning(
                    f"    attempt {attempt}/{attempts} failed for {case.id}: {exc!r}; retrying..."
                )
                continue
            return CaseResult(
                case_id=case.id,
                passed=False,
                score=0.0,
                latency_ms=round((time.time() - start) * 1000, 2),
                verdicts=[],
                response_preview="",
                tool_calls=[],
                error=f"{exc!r} (after {attempts} attempts)" if attempts > 1 else repr(exc),
            )
    # Defensive: loop should always return. Re-raise the last exception if it slips through.
    raise RuntimeError(f"run_case exhausted without result: {last_exc!r}")


def run(
    set_path: Path,
    mode: str,
    api_base: str = DEFAULT_API_BASE,
    categories: Optional[List[str]] = None,
    case_ids: Optional[List[str]] = None,
    retry: int = 0,
    suites: Optional[List[str]] = None,
    concurrency: int = 1,
) -> RunResult:
    """Run an entire eval set and return the aggregated RunResult.

    Args:
        concurrency: Max number of cases to run in parallel. Default 1
            (sequential, identical to historical behaviour). Values > 1 use a
            ThreadPoolExecutor; useful for live mode where each case is mostly
            blocked on the agent's HTTP/SSE call. Be mindful of upstream LLM
            rate limits.
    """
    cases = load_eval_set(set_path)

    if categories:
        wanted = {c.strip() for c in categories if c.strip()}
        cases = [c for c in cases if c.category in wanted]
    if case_ids:
        wanted_ids = {c.strip() for c in case_ids if c.strip()}
        cases = [c for c in cases if c.id in wanted_ids]
    if suites:
        wanted_suites = {s.strip() for s in suites if s.strip()}
        cases = [c for c in cases if getattr(c, "suite", "default") in wanted_suites]

    started = datetime.now().isoformat()
    # Generate the run id up-front so each live request can echo it back
    # via the X-Eval-Run-Id header for cross-log correlation.
    this_run_id = new_run_id()

    # Defensive clamp: 1..16 makes sense for IO-bound HTTP fan-out.
    effective_concurrency = max(1, min(int(concurrency or 1), 16))
    case_results: List[CaseResult] = [None] * len(cases)  # type: ignore[list-item]

    if effective_concurrency == 1 or len(cases) <= 1:
        # Sequential path: identical semantics to v1 for backward compatibility.
        for i, case in enumerate(cases, start=1):
            logger.info(f"[{i}/{len(cases)}] Running case: {case.id}")
            result = run_case(case, mode, api_base=api_base, retry=retry, run_id=this_run_id)
            status = "PASS" if result.passed else "FAIL"
            logger.info(f"    -> {status}  score={result.score:.3f}  {result.latency_ms:.0f}ms")
            case_results[i - 1] = result
    else:
        # Parallel path: run cases concurrently via ThreadPoolExecutor.
        # Results are stored at their original index so the output order matches
        # YAML order regardless of completion order.
        from concurrent.futures import ThreadPoolExecutor, as_completed
        logger.info(f"Running {len(cases)} cases with concurrency={effective_concurrency}")
        with ThreadPoolExecutor(max_workers=effective_concurrency,
                                 thread_name_prefix="eval-case") as pool:
            future_to_idx = {
                pool.submit(
                    run_case, case, mode,
                    api_base=api_base, retry=retry, run_id=this_run_id,
                ): idx
                for idx, case in enumerate(cases)
            }
            done = 0
            for fut in as_completed(future_to_idx):
                idx = future_to_idx[fut]
                case = cases[idx]
                done += 1
                try:
                    result = fut.result()
                except Exception as exc:  # noqa: BLE001
                    logger.error(f"  case {case.id} crashed in worker: {exc!r}")
                    result = CaseResult(
                        case_id=case.id, passed=False, score=0.0, latency_ms=0.0,
                        verdicts=[], response_preview="",
                        response_full=None, tool_calls=[],
                        error=f"worker crash: {exc!r}",
                    )
                status = "PASS" if result.passed else "FAIL"
                logger.info(
                    f"  [{done}/{len(cases)}] {case.id} -> {status} "
                    f"score={result.score:.3f}  {result.latency_ms:.0f}ms"
                )
                case_results[idx] = result

    finished = datetime.now().isoformat()
    total = len(case_results)
    passed = sum(1 for r in case_results if r.passed)
    avg = round(sum(r.score for r in case_results) / total, 4) if total else 0.0

    meta: Dict[str, Any] = {"set_file": set_path.name, "env": capture_env_fingerprint()}
    if mode == "live":
        meta["api_base"] = api_base
    if categories:
        meta["filter_categories"] = list(categories)
    if case_ids:
        meta["filter_case_ids"] = list(case_ids)
    if retry > 0:
        meta["retry"] = retry
    if suites:
        meta["filter_suites"] = list(suites)
    if effective_concurrency > 1:
        meta["concurrency"] = effective_concurrency

    return RunResult(
        run_id=this_run_id,
        started_at=started,
        finished_at=finished,
        mode=mode,
        total_cases=total,
        passed_cases=passed,
        avg_score=avg,
        cases=case_results,
        meta=meta,
    )


def dump_run(run_result: RunResult) -> Path:
    """Persist a RunResult as JSON under results/."""
    suffix = "dryrun" if run_result.mode == "dryrun" else "live"
    out = RESULTS_DIR / f"{suffix}_{run_result.run_id}.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(run_result.to_dict(), f, indent=2, ensure_ascii=False)
    return out


def print_summary(run_result: RunResult, out_path: Path) -> None:
    """Human-readable summary to stdout."""
    print()
    print("=" * 64)
    print(f"Eval Run Summary  ({run_result.mode.upper()})")
    print("=" * 64)
    print(f"Run ID         : {run_result.run_id}")
    print(f"Set            : {run_result.meta.get('set_file')}")
    print(f"Total cases    : {run_result.total_cases}")
    print(f"Passed         : {run_result.passed_cases}/{run_result.total_cases}")
    print(f"Average score  : {run_result.avg_score:.3f}")
    print(f"Output JSON    : {out_path}")
    print("-" * 64)
    for c in run_result.cases:
        mark = "PASS" if c.passed else "FAIL"
        print(f"  [{mark}] {c.case_id:<40} score={c.score:.3f}  ({c.latency_ms:.0f}ms)")
        for v in c.verdicts:
            vmark = "  +" if v.passed else "  -"
            print(f"{vmark} {v.name:<35} score={v.score:.2f}  :: {v.reason}")
    print("=" * 64)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AMP Agent evaluation harness (Step 1 skeleton)."
    )
    parser.add_argument(
        "--set",
        default=str(DEFAULT_SET),
        help="Path to the eval set YAML file.",
    )
    mode_group = parser.add_mutually_exclusive_group(required=False)
    mode_group.add_argument(
        "--dry-run",
        action="store_const",
        const="dryrun",
        dest="mode",
        help="Skeleton validation with a fixed mock response (default).",
    )
    mode_group.add_argument(
        "--live",
        action="store_const",
        const="live",
        dest="mode",
        help="Invoke the real Agent via /api/chat (SSE).",
    )
    parser.add_argument(
        "--api-base",
        default=DEFAULT_API_BASE,
        help=f"Backend base URL for live mode (default: {DEFAULT_API_BASE}).",
    )
    parser.add_argument(
        "--category",
        action="append",
        default=None,
        help="Only run cases whose category matches. Repeatable.",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=None,
        help="Only run cases whose id matches. Repeatable.",
    )
    parser.add_argument(
        "--retry",
        type=int,
        default=0,
        help="Retry each case this many extra times on transport failure (default: 0).",
    )
    parser.add_argument(
        "--suite",
        action="append",
        default=None,
        help="Only run cases whose suite matches (e.g. smoke, nightly). Repeatable.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Run cases in parallel (default 1, max 16). Mind upstream LLM rate limits.",
    )
    parser.set_defaults(mode="dryrun")
    args = parser.parse_args()

    set_path = Path(args.set)
    if not set_path.is_absolute():
        set_path = _HERE / set_path
    if not set_path.exists():
        logger.error(f"Eval set not found: {set_path}")
        return 2

    run_result = run(
        set_path,
        args.mode,
        api_base=args.api_base,
        categories=args.category,
        case_ids=args.case_id,
        retry=args.retry,
        suites=args.suite,
        concurrency=args.concurrency,
    )
    out_path = dump_run(run_result)
    print_summary(run_result, out_path)

    # Exit non-zero if any case failed, so CI can react.
    return 0 if run_result.passed_cases == run_result.total_cases else 1


if __name__ == "__main__":
    sys.exit(main())
