# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Agent Package Initialization
============================
Exports key modules for easy importing
"""

# Export key classes and functions for backward compatibility
try:
    from utils.language_texts import TEXTS
    from utils.context_engine import ContextEngine
    from utils.docker_utils import DockerUtils
    from utils.knowledge_retriever import KnowledgeRetriever
    
    # Re-export to root agent namespace
    __all__ = [
        'TEXTS',
        'ContextEngine',
        'DockerUtils', 
        'KnowledgeRetriever'
    ]
except ImportError as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"⚠️ Some agent modules not available: {e}")
