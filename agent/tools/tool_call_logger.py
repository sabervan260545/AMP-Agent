# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Tool Call Logger - Record and Analyze LLM Tool Invocations
=============================================================

Tracks all tool invocations from the Qwen LLM agent for analysis and optimization.

Core Features:
1. Log every search_knowledge call with parameters and results
2. Calculate retrieval quality metrics (relevance distribution)
3. Analyze knowledge base usage patterns
4. Generate statistical reports in JSON format

Architecture:
- ToolCallLogger: Main logger class with session-based JSONL logging
- Global singleton pattern for cross-module access
- Real-time statistics aggregation (by tool, by knowledge type)
- Dedicated search_knowledge result analyzer

Usage:
    >>> from tool_call_logger import get_logger, log_call
    >>> logger = get_logger()
    >>> log_call("search_knowledge", params, result, latency)

Author: AMP Platform Team
Version: Production 1.0
License: MIT
"""

import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class ToolCallLogger:
    """
    Tool call logger with session-based tracking and quality metrics.
    
    Records all tool invocations to JSONL files with real-time statistics.
    Provides specialized analysis for search_knowledge results.
    
    Attributes:
        log_dir: Directory for log files (default: agent/logs)
        session_id: Unique session identifier (timestamp-based)
        session_log_file: JSONL log file for current session
        stats: Real-time statistics dictionary
            - total_calls: Total tool invocations
            - by_tool: Invocation count per tool
            - by_knowledge_type: Query count per knowledge type
            - avg_relevance: List of relevance scores
            - avg_latency: List of latency values (seconds)
    
    Examples:
        >>> logger = ToolCallLogger()
        >>> logger.log_tool_call("search_knowledge", params, result, 0.234)
        >>> stats = logger.get_session_stats()
        >>> logger.print_summary()
    """
    
    def __init__(self, log_dir: str = "/data/amp-generator-platform/agent/logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Current session log
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_log_file = self.log_dir / f"session_{self.session_id}.jsonl"
        
        # Statistics data
        self.stats = {
            "total_calls": 0,
            "by_tool": defaultdict(int),
            "by_knowledge_type": defaultdict(int),
            "avg_relevance": [],
            "avg_latency": []
        }
        
        logger.info(f"📊 Tool call logging system started: {self.session_log_file}")
    
    def log_tool_call(
        self,
        tool_name: str,
        params: Dict[str, Any],
        result: Any,
        latency: float,
        success: bool = True,
        error: Optional[str] = None
    ):
        """
        Log a single tool invocation with parameters, result, and timing.
        
        Args:
            tool_name: Name of the invoked tool (e.g., "search_knowledge")
            params: Tool parameters dictionary
            result: Tool execution result
            latency: Execution time in seconds
            success: Whether execution succeeded (default: True)
            error: Error message if execution failed (optional)
        
        Side Effects:
            - Appends log entry to session JSONL file
            - Updates statistics (total_calls, by_tool, avg_latency)
            - For search_knowledge: analyzes result and updates relevance stats
        
        Examples:
            >>> logger.log_tool_call(
            ...     "search_knowledge",
            ...     {"query": "AMP mechanisms", "top_k": 5},
            ...     {"success": True, "results": [...]},
            ...     0.234
            ... )
        """
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "tool_name": tool_name,
            "params": params,
            "success": success,
            "latency_ms": round(latency * 1000, 2),
            "error": error
        }
        
        # Special handling for search_knowledge
        if tool_name == "search_knowledge" and success:
            log_entry["result_stats"] = self._analyze_search_result(result)
        
        # Write to log file
        with open(self.session_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        
        # Update statistics
        self.stats["total_calls"] += 1
        self.stats["by_tool"][tool_name] += 1
        self.stats["avg_latency"].append(latency)
        
        if tool_name == "search_knowledge" and success:
            kb_type = params.get("knowledge_type", "unknown")
            self.stats["by_knowledge_type"][kb_type] += 1
            
            # Record relevance scores
            if result and "results" in result:
                for r in result["results"]:
                    if "relevance_score" in r:
                        self.stats["avg_relevance"].append(r["relevance_score"])
        
        logger.info(
            f"🔧 [{tool_name}] "
            f"{'✅' if success else '❌'} "
            f"{latency*1000:.0f}ms"
        )
    
    def _analyze_search_result(self, result: Dict) -> Dict:
        """
        Analyze search_knowledge result and extract quality metrics.
        
        Args:
            result: search_knowledge result dictionary
                Expected keys: success, results, query
                results[i]: {content, source, relevance_score}
        
        Returns:
            Analysis dictionary with keys:
                - total: Number of results
                - avg_relevance: Average relevance score
                - max_relevance: Maximum relevance score
                - min_relevance: Minimum relevance score
                - sources: List of unique sources
                - query: Original query string
                - error: Error message (if failed)
        
        Examples:
            >>> result = {
            ...     "success": True,
            ...     "results": [
            ...         {"relevance_score": 0.85, "source": "literature"},
            ...         {"relevance_score": 0.72, "source": "AMP"}
            ...     ]
            ... }
            >>> logger._analyze_search_result(result)
            {'total': 2, 'avg_relevance': 0.785, ...}
        """
        if not result or not result.get("success"):
            return {"error": result.get("error", "unknown")}
        
        results = result.get("results", [])
        if not results:
            return {"total": 0}
        
        relevances = [r.get("relevance_score", 0) for r in results]
        sources = [r.get("source", "unknown") for r in results]
        
        return {
            "total": len(results),
            "avg_relevance": round(sum(relevances) / len(relevances), 4) if relevances else 0,
            "max_relevance": round(max(relevances), 4) if relevances else 0,
            "min_relevance": round(min(relevances), 4) if relevances else 0,
            "sources": list(set(sources)),
            "query": result.get("query", "")
        }
    
    def get_session_stats(self) -> Dict:
        """
        Get current session statistics summary.
        
        Returns:
            Statistics dictionary with keys:
                - session_id: Current session identifier
                - total_calls: Total tool invocations
                - by_tool: Invocation count per tool
                - by_knowledge_type: Query count per knowledge type
                - avg_latency_ms: Average latency in milliseconds (if available)
                - avg_relevance: Average relevance score (if available)
                - total_searches: Total search_knowledge calls (if available)
        
        Examples:
            >>> stats = logger.get_session_stats()
            >>> stats['total_calls']
            15
            >>> stats['avg_relevance']
            0.7823
        """
        stats = {
            "session_id": self.session_id,
            "total_calls": self.stats["total_calls"],
            "by_tool": dict(self.stats["by_tool"]),
            "by_knowledge_type": dict(self.stats["by_knowledge_type"])
        }
        
        if self.stats["avg_latency"]:
            stats["avg_latency_ms"] = round(
                sum(self.stats["avg_latency"]) / len(self.stats["avg_latency"]) * 1000, 
                2
            )
        
        if self.stats["avg_relevance"]:
            stats["avg_relevance"] = round(
                sum(self.stats["avg_relevance"]) / len(self.stats["avg_relevance"]), 
                4
            )
            stats["total_searches"] = len(self.stats["avg_relevance"])
        
        return stats
    
    def print_summary(self):
        """
        Print formatted statistics summary to console.
        
        Displays:
            - Session ID
            - Total tool calls
            - Calls grouped by tool name
            - Calls grouped by knowledge type
            - Average latency (if available)
            - Average relevance and total searches (if available)
        
        Side Effects:
            Prints formatted text to stdout
        
        Examples:
            >>> logger.print_summary()
            ============================================================
            📊 Tool Call Statistics (Session: 20251213_143022)
            ============================================================
            Total Calls: 15
            ...
        """
        stats = self.get_session_stats()
        
        print("\n" + "=" * 60)
        print(f"📊 Tool Call Statistics (Session: {self.session_id})")
        print("=" * 60)
        print(f"\nTotal Calls: {stats['total_calls']}")
        
        if stats.get('by_tool'):
            print(f"\nBy Tool:")
            for tool, count in stats['by_tool'].items():
                print(f"  - {tool}: {count} calls")
        
        if stats.get('by_knowledge_type'):
            print(f"\nKnowledge Type:")
            for kb_type, count in stats['by_knowledge_type'].items():
                print(f"  - {kb_type}: {count} calls")
        
        if 'avg_latency_ms' in stats:
            print(f"\nAverage Latency: {stats['avg_latency_ms']:.2f}ms")
        
        if 'avg_relevance' in stats:
            print(f"\nRetrieval Quality:")
            print(f"  - Average Relevance: {stats['avg_relevance']:.4f}")
            print(f"  - Total Searches: {stats['total_searches']}")
        
        print("\n" + "=" * 60 + "\n")
    
    def export_report(self, output_file: Optional[str] = None) -> str:
        """
        Export detailed statistics report to JSON file.
        
        Args:
            output_file: Output file path (optional)
                Default: {log_dir}/report_{session_id}.json
        
        Returns:
            Path to exported report file
        
        Side Effects:
            Writes JSON report to file system
        
        Examples:
            >>> report_path = logger.export_report()
            >>> report_path
            '/data/amp-generator-platform/agent/logs/report_20251213_143022.json'
        """
        if output_file is None:
            output_file = self.log_dir / f"report_{self.session_id}.json"
        
        report = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "statistics": self.get_session_stats(),
            "log_file": str(self.session_log_file)
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 Report exported: {output_file}")
        return str(output_file)


# Global singleton
_global_logger: Optional[ToolCallLogger] = None


def get_logger() -> ToolCallLogger:
    """
    Get or create global logger singleton.
    
    Returns:
        Global ToolCallLogger instance
    
    Examples:
        >>> logger = get_logger()
        >>> logger.log_tool_call("search_knowledge", params, result, 0.234)
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = ToolCallLogger()
    return _global_logger


def log_call(tool_name: str, params: Dict, result: Any, latency: float, **kwargs):
    """
    Convenience function for logging tool calls via global logger.
    
    Args:
        tool_name: Name of the invoked tool
        params: Tool parameters dictionary
        result: Tool execution result
        latency: Execution time in seconds
        **kwargs: Additional arguments passed to log_tool_call
            (e.g., success=False, error="message")
    
    Examples:
        >>> log_call("search_knowledge", {"query": "test"}, result, 0.123)
        >>> log_call("generate_sequences", params, result, 1.5, success=False, error="Timeout")
    """
    get_logger().log_tool_call(tool_name, params, result, latency, **kwargs)


if __name__ == "__main__":
    # Test logging system
    call_logger = ToolCallLogger()
    
    # Simulate tool calls
    call_logger.log_tool_call(
        tool_name="search_knowledge",
        params={"query": "AMP mechanisms", "knowledge_type": "literature", "top_k": 5},
        result={
            "success": True,
            "total_found": 5,
            "query": "AMP mechanisms",
            "results": [
                {"content": "...", "source": "research_summary", "relevance_score": 0.85},
                {"content": "...", "source": "AMP", "relevance_score": 0.72}
            ]
        },
        latency=0.234
    )
    
    call_logger.log_tool_call(
        tool_name="search_knowledge",
        params={"query": "MIC < 1", "knowledge_type": "mic", "top_k": 3},
        result={
            "success": True,
            "total_found": 3,
            "query": "MIC < 1",
            "results": [
                {"content": "...", "source": "mic_data", "relevance_score": 0.68}
            ]
        },
        latency=0.156
    )
    
    # Print statistics
    call_logger.print_summary()
    
    # Export report
    call_logger.export_report()
