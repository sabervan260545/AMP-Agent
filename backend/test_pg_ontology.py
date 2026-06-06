#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""Test PostgreSQL ontology backend"""
import os
os.environ["ONTOLOGY_PG_DSN"] = "postgresql://amp_user:your_password_here@amp-postgres:5432/amp_ontology"

from database import DatabaseManager
import json

db = DatabaseManager()
overview = db.get_ontology_overview()

print("\n" + "=" * 60)
print("PostgreSQL Ontology Overview Test")
print("=" * 60)
print(f"\nDesign Principles: {len(overview['design_principles'])}")
for dp in overview['design_principles'][:3]:
    print(f"  - {dp['name']}: {dp['count']} docs")

print(f"\nAction Mechanisms: {len(overview['action_mechanisms'])}")
for mech in overview['action_mechanisms'][:3]:
    print(f"  - {mech['name']}: {mech['count']} docs")

print(f"\nTarget Organisms: {len(overview['target_organisms'])}")
for tgt in overview['target_organisms'][:3]:
    print(f"  - {tgt['name']}: {tgt['count']} docs")

print(f"\nMechanism×Target Matrix: {len(overview['mechanism_target_matrix'])} entries")
for mt in overview['mechanism_target_matrix'][:5]:
    print(f"  - {mt['mechanism']} × {mt['target']}: {mt['count']} co-occurrences")

print(f"\nExperimental Stats: {overview['experimental_values_stats']}")
print("\n✅ PostgreSQL ontology query successful!\n")
