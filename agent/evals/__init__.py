# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
AMP Agent Evaluation Harness
=============================

Regression testing infrastructure for the AMP Agent.

Layout:
    evals/
    ├── golden_prompts.yaml   # Benchmark prompts with expected behaviors
    ├── schema.py             # Data classes for test cases and results
    ├── scorers.py            # Scoring functions (pass/fail + numeric score)
    ├── runner.py             # CLI entry: load → run → score → dump JSON
    └── results/              # Per-run JSON outputs (baseline.json after first run)

Usage (CLI, dry run - no real Agent call):
    python -m agent.evals.runner --dry-run

Usage (CLI, full run):
    python -m agent.evals.runner --set golden_prompts.yaml

This module is purely additive - it does not modify any existing agent code.
"""

__version__ = "0.1.0"
