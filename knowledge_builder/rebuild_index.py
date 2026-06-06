#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Rebuild the AMP knowledge-base vector index (ChromaDB).
"""

import sys
import os

# Extend PYTHONPATH so the Agent modules are importable both inside the
# container (/app/agent) and when running from the host workspace.
sys.path.insert(0, '/app/agent')
sys.path.insert(0, '/data/amp-generator-platform/agent')

from knowledge_retriever import KnowledgeRetriever


def main():
    print("🚀 Rebuilding AMP knowledge-base vector index...")

    # Initialise the retriever (auto-creates an empty vector_store).
    retriever = KnowledgeRetriever()

    print("\n📚 Indexing literature knowledge...")
    retriever.index_literature_knowledge()

    print("\n💊 Indexing MIC data...")
    retriever.index_mic_data()

    print("\n🧬 Indexing CPP data...")
    retriever.index_cpp_data()

    print("\n🩸 Indexing hemolysis data...")
    retriever.index_hemolysis_data()

    print("\n✅ Indexing finished. Statistics:")
    stats = retriever.get_statistics()
    print(f"   Total documents: {stats['total_documents']}")
    for name, count in stats['collections'].items():
        print(f"   - {name}: {count}")

    print("\n✨ Knowledge-base rebuild complete!")


if __name__ == "__main__":
    main()
