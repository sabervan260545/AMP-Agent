# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Migrate ontology/document data from SQLite to PostgreSQL
Run once to bootstrap the PostgreSQL Graph RAG database
"""
import sqlite3
import psycopg2
from psycopg2.extras import execute_batch, Json
import json
import sys
import os

SQLITE_PATH = "/data/amp-generator-platform/data/amp_platform.db"
# Docker 内部网络中，postgres 服务名就是 amp-postgres
PG_DSN = "postgresql://amp_user:your_password_here@amp-postgres:5432/amp_ontology"

TABLE_COLUMNS = {
    "ontology_entity": ["id", "type", "name", "description", "source", "extra_json", "created_at"],
    "ontology_relation": ["id", "subject_id", "predicate", "object_id", "extra_json", "source", "created_at"],
    "document": ["id", "source", "title", "year", "metadata", "created_at"],
    "document_chunk": ["id", "document_id", "section", "text", "embedding", "created_at"],
}

def normalize_row(table, row):
    """Normalize row data: convert JSON strings to dict for JSONB columns"""
    cols = TABLE_COLUMNS[table]
    as_dict = dict(zip(cols, row))
    
    # PostgreSQL JSONB 需要 dict，如果 SQLite 里存的是字符串，要先转
    for key in ["extra_json", "metadata"]:
        if key in as_dict and isinstance(as_dict[key], str):
            try:
                as_dict[key] = json.loads(as_dict[key]) if as_dict[key] else None
            except Exception:
                as_dict[key] = None
    
    # 包装 JSONB 字段为 psycopg2.extras.Json，其他字段保持原样
    result = []
    for c in cols:
        val = as_dict[c]
        if c in ["extra_json", "metadata"] and val is not None:
            result.append(Json(val))
        else:
            result.append(val)
    
    return tuple(result)

def migrate_table(sqlite_conn, pg_conn, table):
    """Migrate one table from SQLite to PostgreSQL"""
    cols = TABLE_COLUMNS[table]
    placeholders = ", ".join(["%s"] * len(cols))
    insert_sql = f"""
        INSERT INTO {table} ({", ".join(cols)})
        VALUES ({placeholders})
        ON CONFLICT (id) DO NOTHING
    """

    sq_cur = sqlite_conn.cursor()
    sq_cur.execute(f"SELECT {', '.join(cols)} FROM {table}")
    rows = sq_cur.fetchall()
    
    if not rows:
        print(f"  ⚠️  {table}: No data in SQLite, skipping")
        return 0
    
    norm_rows = [normalize_row(table, r) for r in rows]

    with pg_conn.cursor() as pg_cur:
        execute_batch(pg_cur, insert_sql, norm_rows, page_size=500)
    pg_conn.commit()
    
    print(f"  ✅ {table}: {len(norm_rows)} rows migrated")
    return len(norm_rows)

def main():
    print("=" * 60)
    print("Ontology Migration: SQLite → PostgreSQL + pgvector")
    print("=" * 60)
    
    # Check SQLite file exists
    if not os.path.exists(SQLITE_PATH):
        print(f"❌ SQLite database not found at {SQLITE_PATH}")
        sys.exit(1)
    
    print(f"\n📂 Source: {SQLITE_PATH}")
    print(f"🎯 Target: {PG_DSN}\n")
    
    try:
        sqlite_conn = sqlite3.connect(SQLITE_PATH)
        pg_conn = psycopg2.connect(PG_DSN)
        print("✅ Database connections established\n")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    migrated = {}
    total = 0
    
    print("🚀 Starting migration...\n")
    
    for table in TABLE_COLUMNS:
        count = migrate_table(sqlite_conn, pg_conn, table)
        migrated[table] = count
        total += count
    
    sqlite_conn.close()
    pg_conn.close()
    
    print("\n" + "=" * 60)
    print(f"✅ Migration complete! Total rows: {total}")
    print("=" * 60)
    print("\nSummary:")
    for table, count in migrated.items():
        print(f"  - {table}: {count} rows")
    print()

if __name__ == "__main__":
    main()
