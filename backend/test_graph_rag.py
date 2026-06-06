#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""Test Graph RAG query interface"""
import os
os.environ["ONTOLOGY_PG_DSN"] = "postgresql://amp_user:your_password_here@amp-postgres:5432/amp_ontology"

from graph_rag import GraphRAGQuery
import json

q = GraphRAGQuery()

print("\n" + "=" * 70)
print("Graph RAG Query Examples")
print("=" * 70)

# 查询 1：针对 E.coli 的机制
print("\n🔍 Query 1: Mechanisms effective against E.coli")
print("-" * 70)
mechs = q.query_mechanism_by_target("E.coli", limit=5)
for m in mechs:
    print(f"  • {m['mechanism']}: {m['doc_count']} documents")
    print(f"    Evidence: {', '.join(m['evidence_docs'][:3])}")

# 查询 2：与膜破坏机制共现的设计原则
print("\n🔍 Query 2: Design principles for membrane_disruption")
print("-" * 70)
principles = q.query_design_principles_for_mechanism("membrane_disruption", limit=5)
for p in principles:
    print(f"  • {p['principle']}: {p['doc_count']} documents")
    print(f"    Evidence: {', '.join(p['evidence_docs'][:3])}")

# 查询 3：S.aureus 相关的三元组路径
print("\n🔍 Query 3: Document triplets for S.aureus")
print("-" * 70)
triplets = q.query_triplet_path("S.aureus", "Organism", "has_target", "Document", limit=3)
for t in triplets:
    print(f"  • {t['subject']} --[{t['predicate']}]--> {t['object']}")

print("\n" + "=" * 70)
print("✅ All Graph RAG queries successful!")
print("=" * 70 + "\n")
