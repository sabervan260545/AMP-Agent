# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
search_knowledge Tool
Provides knowledge base retrieval capability for the Qwen Agent.

Features:
- Retrieve 575 curated AMP literature passages
- Semantic search that captures user intent
- Return top-k most relevant passages as Qwen references

Usage example:
User: "What is the mechanism of action of antimicrobial peptides?"
-> Qwen calls search_knowledge("AMP mechanism of action")
-> Retrieves 3-5 relevant passages
-> Qwen generates a professional answer grounded in retrieved context
"""

import sys
import os
import time

# Add parent directory to sys.path so top-level modules (e.g. knowledge_retriever) can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_retriever import KnowledgeRetriever
from typing import Dict, List, Any

# Import tool call logger (prefer packaged version)
try:
    from .tool_call_logger import log_call
except ImportError:
    try:
        from tool_call_logger import log_call  # Legacy fallback
    except ImportError:
        # No-op compatibility
        def log_call(*args, **kwargs):
            pass


# Global retriever singleton (avoids reloading the embedding model on every call)
_retriever = None


def get_retriever():
    """Return the global KnowledgeRetriever singleton, creating it on first use."""
    global _retriever
    if _retriever is None:
        _retriever = KnowledgeRetriever()
    return _retriever


def search_knowledge(
    query: str,
    knowledge_type: str = "literature",
    top_k: int = 5
) -> Dict[str, Any]:
    """
    Search the AMP knowledge base.

    Args:
        query: Natural-language query
        knowledge_type: Knowledge source
            - "literature": Literature corpus (default, 575 curated passages)
            - "mic": MIC activity data
            - "cpp": Cell-penetrating peptide data
            - "hemolysis": Hemolytic activity data
        top_k: Number of top relevant passages to return (default: 5)

    Returns:
        {
            "success": True/False,
            "results": [
                {
                    "content": "passage text",
                    "source": "source reference",
                    "relevance_score": 0.85,  # Cosine-like relevance
                },
                ...
            ],
            "total_found": 5,
            "query": "original query"
        }

    Examples:
        # Retrieve AMP design principles
        result = search_knowledge("How to design potent low-toxicity AMPs")

        # Retrieve MIC data
        result = search_knowledge("MIC below 1", knowledge_type="mic")
    """
    try:
        start_time = time.time()
        retriever = get_retriever()
        
        # Run retrieval
        results = retriever.search(
            query=query,
            knowledge_type=knowledge_type,
            top_k=top_k
        )
        
        # Format results
        formatted_results = []
        for r in results:
            formatted_results.append({
                "content": r["document"],
                "source": r["metadata"].get("source", "unknown"),
                "relevance_score": round(1 - r.get("distance", 1.0), 4),
                "type": r["metadata"].get("type", "unknown")
            })
        
        result = {
            "success": True,
            "results": formatted_results,
            "total_found": len(formatted_results),
            "query": query,
            "knowledge_type": knowledge_type
        }
        
        # Log successful call
        latency = time.time() - start_time
        log_call(
            tool_name="search_knowledge",
            params={"query": query, "knowledge_type": knowledge_type, "top_k": top_k},
            result=result,
            latency=latency,
            success=True
        )
        
        return result
        
    except Exception as e:
        latency = time.time() - start_time if 'start_time' in locals() else 0
        result = {
            "success": False,
            "error": str(e),
            "query": query,
            "results": []
        }
        
        # Log failed call
        log_call(
            tool_name="search_knowledge",
            params={"query": query, "knowledge_type": knowledge_type, "top_k": top_k},
            result=result,
            latency=latency,
            success=False,
            error=str(e)
        )
        
        return result


# Tool metadata (consumed by the Agent registration layer)
TOOL_METADATA = {
    "name": "search_knowledge",
    "description": """Retrieve from the AMP professional knowledge base.

Knowledge base contents:
- 575 curated literature passages (6 core papers)
- Topics: mechanisms of action, design strategies, QSAR models, clinical trials, production technologies, etc.
- Embedding model: all-mpnet-base-v2 (768-dim semantic vectors)

Applicable scenarios:
1. Answer theoretical AMP questions (mechanism, classification, properties)
2. Provide design recommendations (optimization, modification strategies)
3. Cite literature data (experimental results, statistics)
4. Explain professional concepts (MIC, hemolysis, CPP, etc.)

Usage guidelines:
- Phrase queries in natural language
- top_k=3-5 is usually sufficient
- Prefer the "literature" type (most comprehensive)""",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural-language query, e.g. 'What is the mechanism of action of AMPs?' or 'How to improve AMP stability?'"
            },
            "knowledge_type": {
                "type": "string",
                "enum": ["literature", "mic", "cpp", "hemolysis"],
                "default": "literature",
                "description": "Knowledge source. Default: 'literature' (curated literature corpus, recommended)."
            },
            "top_k": {
                "type": "integer",
                "default": 5,
                "minimum": 1,
                "maximum": 10,
                "description": "Number of results to return (default: 5)."
            }
        },
        "required": ["query"]
    }
}


if __name__ == "__main__":
    # Smoke tests
    print("🧪 Testing search_knowledge tool\n")

    test_queries = [
        ("What is the mechanism of action of antimicrobial peptides?", "literature", 3),
        ("How to improve AMP stability?", "literature", 3),
        ("Relationship between MIC and hydrophobicity", "literature", 3),
    ]

    for query, ktype, k in test_queries:
        print(f"📝 Query: {query}")
        result = search_knowledge(query, ktype, k)

        if result["success"]:
            print(f"   ✅ Found {result['total_found']} results")
            for i, r in enumerate(result["results"], 1):
                print(f"   [{i}] Relevance: {r['relevance_score']:.4f} | Source: {r['source']}")
                print(f"       {r['content'][:100]}...")
        else:
            print(f"   ❌ Error: {result['error']}")
        print()
