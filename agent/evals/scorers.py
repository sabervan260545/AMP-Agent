# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Generic scorers for the evaluation harness.

Each scorer is a callable with signature:
    scorer(response_text: str, tool_calls: list[dict], params: dict) -> (bool, float, str)

Return tuple: (passed, score in [0, 1], human-readable reason).

Add new scorers by decorating a function with @register("name") and relying
on SCORER_REGISTRY for dispatch inside the runner.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

ScorerFn = Callable[[str, List[Dict[str, Any]], Dict[str, Any]], Tuple[bool, float, str]]

SCORER_REGISTRY: Dict[str, ScorerFn] = {}


def register(name: str) -> Callable[[ScorerFn], ScorerFn]:
    """Decorator: register a scorer under the given name."""

    def _decorator(fn: ScorerFn) -> ScorerFn:
        SCORER_REGISTRY[name] = fn
        return fn

    return _decorator


# ---------------------------------------------------------------------------
# Built-in scorers
# ---------------------------------------------------------------------------


@register("tool_name_count")
def tool_name_count(
    response: str,
    tool_calls: List[Dict[str, Any]],
    params: Dict[str, Any],
) -> Tuple[bool, float, str]:
    """
    Pass if tool_calls contains at least `min_count` invocations of `tool`.

    Params:
        tool (str): Tool name to match.
        min_count (int): Minimum required invocations (default 1).
    """
    target = params.get("tool")
    min_count = int(params.get("min_count", 1))
    if not target:
        return False, 0.0, "Missing 'tool' parameter"

    hits = sum(1 for c in tool_calls if c.get("name") == target)
    passed = hits >= min_count
    score = min(1.0, hits / max(min_count, 1))
    reason = f"Found {hits} call(s) to '{target}', required >= {min_count}"
    return passed, score, reason


@register("response_contains_any")
def response_contains_any(
    response: str,
    tool_calls: List[Dict[str, Any]],
    params: Dict[str, Any],
) -> Tuple[bool, float, str]:
    """
    Pass if the response contains ANY of `any_of`, or ALL of `all_of`.

    Params:
        any_of (list[str]): Pass when at least one substring is present.
        all_of (list[str]): Pass when every substring is present.
        case_sensitive (bool): Default True. When False, both the response and
            the keywords are lower-cased before comparison.
    """
    any_of = params.get("any_of") or []
    all_of = params.get("all_of") or []
    case_sensitive = bool(params.get("case_sensitive", True))
    text = response or ""

    if not case_sensitive:
        text_cmp = text.lower()
        any_of_cmp = [kw.lower() for kw in any_of]
        all_of_cmp = [kw.lower() for kw in all_of]
    else:
        text_cmp = text
        any_of_cmp = list(any_of)
        all_of_cmp = list(all_of)

    if all_of_cmp:
        hits = [orig for orig, cmp in zip(all_of, all_of_cmp) if cmp in text_cmp]
        passed = len(hits) == len(all_of_cmp)
        score = len(hits) / max(len(all_of_cmp), 1)
        return passed, score, f"all_of: matched {len(hits)}/{len(all_of_cmp)} ({hits})"

    if any_of_cmp:
        hits = [orig for orig, cmp in zip(any_of, any_of_cmp) if cmp in text_cmp]
        passed = len(hits) > 0
        score = 1.0 if passed else 0.0
        return passed, score, f"any_of: matched {hits}"

    return False, 0.0, "Neither 'any_of' nor 'all_of' provided"

@register("always_pass")
def always_pass(
    response: str,
    tool_calls: List[Dict[str, Any]],
    params: Dict[str, Any],
) -> Tuple[bool, float, str]:
    """Debug scorer: always returns pass with score 1.0."""
    return True, 1.0, "always_pass"


# ---------------------------------------------------------------------------
# LLM-as-judge scorer
# ---------------------------------------------------------------------------
#
# Uses the project's DashScope/Qwen OpenAI-compatible endpoint to semantically
# score a response against a natural-language rubric. Fails closed by default:
# if the LLM is unreachable, the case is marked as failed with an explicit
# reason, so regressions cannot be hidden by infrastructure flakiness.

_LLM_JUDGE_SYSTEM_PROMPT = (
    "You are a strict evaluator for an AI agent. Given a USER prompt, the "
    "AGENT response, and a RUBRIC, rate how well the response satisfies the "
    "rubric on a continuous scale from 0.0 to 1.0.\n\n"
    "Rules:\n"
    " - Score 1.0: fully satisfies the rubric with clear, correct, on-topic content.\n"
    " - Score 0.7: satisfies main intent, minor gaps or phrasing issues.\n"
    " - Score 0.4: partially relevant but misses key requirements.\n"
    " - Score 0.0: off-topic, refuses, or factually wrong.\n"
    " - Be harsh on hallucinations and missing-requested-content.\n\n"
    "Return STRICT JSON only, no markdown, no preamble: "
    '{"score": <float 0-1>, "reason": "<one concise sentence>"}'
)

_JSON_RE = re.compile(r"\{[^{}]*\"score\"[^{}]*\}", re.DOTALL)


def _build_judge_client() -> Optional[Any]:
    """Return an OpenAI-compatible client, or None if unavailable."""
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    try:
        return OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("llm_judge: failed to init OpenAI client: %r", exc)
        return None


def _parse_judge_json(raw: str) -> Optional[Dict[str, Any]]:
    """Tolerant parser: accept raw JSON or JSON embedded in text."""
    if not raw:
        return None
    # direct parse
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        pass
    # regex fallback: first {..."score"...}
    m = _JSON_RE.search(raw)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:  # noqa: BLE001
            return None
    return None


@register("llm_judge")
def llm_judge(
    response: str,
    tool_calls: List[Dict[str, Any]],
    params: Dict[str, Any],
) -> Tuple[bool, float, str]:
    """
    Score a response semantically via an LLM, using a natural-language rubric.

    Params:
        rubric (str, required): Plain-language description of what a good
            response must contain / avoid.
        threshold (float): Pass threshold on the 0-1 score. Default 0.7.
        user_prompt (str): Optional. The original user prompt, used to give the
            judge more context. Recommended for QA/RAG cases.
        model (str): Judge model name. Default 'qwen-plus'.
        on_error (str): What to do when the judge is unreachable. One of
            'fail' (default), 'skip' (passed=True, score=0.0, warning),
            'pass_with_warning' (passed=True, score=0.5, warning).
    """
    rubric = (params.get("rubric") or "").strip()
    if not rubric:
        return False, 0.0, "llm_judge: missing 'rubric' parameter"

    threshold = float(params.get("threshold", 0.7))
    model = params.get("model", "qwen-plus")
    on_error = str(params.get("on_error", "fail")).lower()
    user_prompt = params.get("user_prompt") or ""

    def _error_result(msg: str) -> Tuple[bool, float, str]:
        if on_error == "skip":
            return True, 0.0, f"llm_judge SKIPPED: {msg}"
        if on_error == "pass_with_warning":
            return True, 0.5, f"llm_judge UNAVAILABLE (passed with warning): {msg}"
        return False, 0.0, f"llm_judge FAILED: {msg}"

    client = _build_judge_client()
    if client is None:
        return _error_result("DASHSCOPE_API_KEY missing or openai not installed")

    # Truncate overly long responses to protect the judge's context.
    resp_text = (response or "").strip()
    max_chars = int(params.get("max_response_chars", 4000))
    if len(resp_text) > max_chars:
        resp_text = resp_text[:max_chars] + "\n[...truncated]"

    content = (
        f"RUBRIC:\n{rubric}\n\n"
        f"USER PROMPT:\n{user_prompt or '(not provided)'}\n\n"
        f"AGENT RESPONSE:\n{resp_text}\n\n"
        "Reminder: Return STRICT JSON only, shape {\"score\": float, \"reason\": str}."
    )

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _LLM_JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            temperature=0.0,
            max_tokens=256,
            timeout=30,
        )
        raw = completion.choices[0].message.content if completion.choices else ""
    except Exception as exc:  # noqa: BLE001
        return _error_result(f"API call failed: {exc!r}")

    parsed = _parse_judge_json(raw)
    if parsed is None:
        return _error_result(f"could not parse JSON from judge output: {raw[:200]!r}")

    try:
        score = float(parsed.get("score", 0.0))
    except (TypeError, ValueError):
        return _error_result(f"non-numeric score in judge output: {parsed!r}")
    score = max(0.0, min(1.0, score))
    reason = str(parsed.get("reason", ""))[:500]

    passed = score >= threshold
    return passed, score, (
        f"llm_judge score={score:.2f} (thr={threshold:.2f}) :: {reason}"
    )


__all__ = ["SCORER_REGISTRY", "register", "ScorerFn"]
