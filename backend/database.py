# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Database Models and Management (Production Ready)
===================================================

Provides persistent storage for sequence results and tool logs with dual backend support.

Key Features:
- Sequence asset persistence with full evaluation metrics
- Tool execution logging with performance tracking
- Session management and statistics
- Ontology and literature knowledge management
- Dual backend support:
  * SQLite (default): Fast development and single-server deployment
  * PostgreSQL + pgvector (production): Graph RAG with vector search

Backend Selection:
- Set ONTOLOGY_PG_DSN environment variable to enable PostgreSQL ontology backend
- Automatic path detection for Docker and host environments

Author: AMP Platform Team
Version: Production 1.0
License: MIT
"""
import sqlite3
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
import json
import pandas as pd
import uuid
import logging

logger = logging.getLogger(__name__)

# Optional: PostgreSQL support
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, Json
    _HAS_PSYCOPG2 = True
except ImportError:
    _HAS_PSYCOPG2 = False
    logger.warning("⚠️  psycopg2 not available, PostgreSQL ontology queries disabled")


class DatabaseManager:
    """
    Database manager for sequence and log persistence with dual backend support.
    
    Manages SQLite database for sequence assets and tool logs, with optional
    PostgreSQL backend for production-grade Graph RAG ontology queries.
    
    Backends:
    - **SQLite** (default): Fast development, embedded database
    - **PostgreSQL + pgvector** (production): Scalable Graph RAG with pgvector extension
    
    Attributes:
        db_path: SQLite database file path
        pg_dsn: PostgreSQL connection string (optional)
        use_postgres_ontology: Whether PostgreSQL ontology backend is enabled
    
    Examples:
        >>> # SQLite only
        >>> db = DatabaseManager()
        >>> 
        >>> # With PostgreSQL ontology
        >>> os.environ['ONTOLOGY_PG_DSN'] = 'postgresql://user:pass@host/dbname'
        >>> db = DatabaseManager()
        >>> db.use_postgres_ontology
        True
    
    Notes:
        - Automatic path detection for Docker containers and host environments
        - Uses /app/data/ in containers, ../data/ on host
    """
    
    def __init__(self, db_path: str = None):
        # [Fix] Automatic path detection, compatible with container and host environments
        if db_path is None:
            # 🔥 Prioritize environment variable, then detect container environment
            if os.path.exists('/app/data'):
                # Docker container: database in /app/data/
                self.db_path = Path('/app/data/amp_platform.db')
            else:
                # Host environment: relative to backend/ parent directory
                base_dir = Path(__file__).resolve().parent.parent # backend -> root
                self.db_path = base_dir / "data" / "amp_platform.db"
        else:
            self.db_path = Path(db_path)
            
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # PostgreSQL ontology backend (optional)
        self.pg_dsn = os.getenv("ONTOLOGY_PG_DSN")
        self.use_postgres_ontology = _HAS_PSYCOPG2 and self.pg_dsn is not None
        
        if self.use_postgres_ontology:
            logger.info(f"✅ PostgreSQL ontology backend enabled: {self.pg_dsn.split('@')[-1]}")
        else:
            logger.info("ℹ️  Using SQLite ontology backend")
        
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables and indices."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Sequence results table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sequences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sequence TEXT NOT NULL,
                    generator TEXT NOT NULL,
                    mic_value REAL,
                    mic_log REAL,
                    mic_unit TEXT,
                    hemolysis_score REAL,
                    is_toxic INTEGER,
                    cpp_score REAL,
                    is_cpp INTEGER,
                    is_amp INTEGER,
                    amp_score REAL,
                    is_pareto_optimal INTEGER,
                    target TEXT,
                    session_id TEXT,
                    verified INTEGER DEFAULT 0,
                    experimental_mic REAL,
                    experimental_hemolysis REAL,
                    experimental_notes TEXT,
                    verified_at TIMESTAMP,
                    exported_to_ontology INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(sequence, generator, session_id)
                )
            """)
            
            # Tool logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tool_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_ms REAL,
                    input_args TEXT,
                    output_summary TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Session metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_sequences INTEGER DEFAULT 0,
                    total_tool_calls INTEGER DEFAULT 0
                )
            """)

            # Tool failure logs table (for Auto-Debug data)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tool_failure_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_name TEXT NOT NULL,
                    params TEXT,
                    error_history TEXT,
                    auto_fixed INTEGER DEFAULT 0,
                    fix_strategy TEXT,
                    session_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Ontology and literature tables (SQLite Fallback)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ontology_entity (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    source TEXT,
                    extra_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ontology_relation (
                    id TEXT PRIMARY KEY,
                    subject_id TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    extra_json TEXT,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(subject_id) REFERENCES ontology_entity(id),
                    FOREIGN KEY(object_id) REFERENCES ontology_entity(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    title TEXT,
                    year INTEGER,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document_chunk (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    section TEXT,
                    text TEXT NOT NULL,
                    embedding BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(document_id) REFERENCES document(id)
                )
            """)
            
            # Create indices
            indices = [
                "idx_seq_generator ON sequences(generator)",
                "idx_seq_session ON sequences(session_id)",
                "idx_seq_created ON sequences(created_at)",
                "idx_log_session ON tool_logs(session_id)",
                "idx_log_tool ON tool_logs(tool_name)",
                "idx_log_timestamp ON tool_logs(timestamp)"
            ]
            for idx in indices:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx}")
            
            conn.commit()

    # [Fix] Safe type conversion function
    def _safe_float(self, value: Any) -> Optional[float]:
        """
        Safe conversion to float, handling 'N/A', None, and string inputs.
        
        Args:
            value: Value to convert (int, float, str, or None)
        
        Returns:
            Float value or None if conversion fails
        
        Examples:
            >>> db._safe_float("12.5")
            12.5
            >>> db._safe_float("N/A")
            None
            >>> db._safe_float(None)
            None
        """
        if value is None:
            return None
        if isinstance(value, (float, int)):
            return float(value)
        if isinstance(value, str):
            value = value.strip()
            if not value or value.lower() in ['n/a', 'none', 'null', 'nan']:
                return None
            try:
                return float(value)
            except ValueError:
                return None
        return None
    
    # ==================== Sequence Results Management ====================
    
    def save_sequences(self, sequences: List[Dict], session_id: str = "default") -> int:
        """Save sequences to database with evaluation metrics.
        
        Args:
            sequences: List of sequence dicts with evaluation results
            session_id: Session identifier for grouping
        
        Returns:
            Number of sequences successfully saved
        
        Examples:
            >>> sequences = [{"sequence": "KKLFKKILKYL", "generator": "AMP-Designer", "mic_value": 8.5}]
            >>> count = db.save_sequences(sequences, session_id="test_001")
            >>> count
            1
        """
        if not sequences:
            return 0
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            saved_count = 0
            
            for seq in sequences:
                try:
                    # [Fix] Use safe conversion
                    mic_val = self._safe_float(seq.get('mic_value'))
                    hemo_val = self._safe_float(seq.get('hemolysis_score'))
                    cpp_val = self._safe_float(seq.get('cpp_score'))
                    amp_val = self._safe_float(seq.get('amp_score'))
                    exp_mic = self._safe_float(seq.get('experimental_mic'))

                    import json as _json
                    sf = seq.get('struct_features') or {}
                    sf_json = _json.dumps(sf) if sf else None
                    helix_val = self._safe_float(sf.get('helix_fraction')) if sf else None
                    plddt_val = self._safe_float(sf.get('mean_plddt')) if sf else None
                    rg_val    = self._safe_float(sf.get('rg')) if sf else None
                    comp_val  = self._safe_float(seq.get('composite_score'))

                    cursor.execute("""
                        INSERT OR REPLACE INTO sequences 
                        (sequence, generator, mic_value, mic_log, mic_unit, 
                         hemolysis_score, is_toxic, cpp_score, is_cpp, 
                         is_amp, amp_score, is_pareto_optimal, target, session_id,
                         struct_features, composite_score, helix_fraction, mean_plddt, rg)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        seq.get('sequence'),
                        seq.get('generator'),
                        mic_val,
                        seq.get('mic_log'),
                        seq.get('mic_unit', 'μM'),
                        hemo_val,
                        int(seq.get('is_toxic', False) or 0),
                        cpp_val,
                        int(seq.get('is_cpp', False) or 0),
                        int(seq.get('is_amp', False) or 0),
                        amp_val,
                        int(seq.get('is_pareto_optimal', False) or 0),
                        seq.get('target'),
                        session_id,
                        sf_json,
                        comp_val,
                        helix_val,
                        plddt_val,
                        rg_val
                    ))
                    saved_count += 1
                except Exception as e:
                    print(f"⚠️ Failed to save sequence {seq.get('sequence')}: {e}")
            
            # Update session statistics
            cursor.execute("""
                INSERT INTO sessions (session_id, total_sequences)
                VALUES (?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    total_sequences = total_sequences + ?,
                    last_activity = CURRENT_TIMESTAMP
            """, (session_id, saved_count, saved_count))
            
            conn.commit()
            return saved_count
    
    def load_sequences(self, 
                       session_id: Optional[str] = None,
                       generator: Optional[str] = None,
                       limit: int = 1000) -> pd.DataFrame:
        """
        Load sequences from database with optional filtering.
        
        Args:
            session_id: Filter by session ID
            generator: Filter by generator name
            limit: Maximum number of sequences to load
        
        Returns:
            DataFrame with sequence data and evaluation metrics
        
        Examples:
            >>> df = db.load_sequences(session_id="test_001", limit=100)
            >>> len(df)
            100
        """
        query = "SELECT * FROM sequences WHERE 1=1"
        params = []
        
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        
        if generator:
            query += " AND generator = ?"
            params.append(generator)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, params=params)
            
            # Convert boolean columns
            bool_cols = ['is_toxic', 'is_cpp', 'is_amp', 'is_pareto_optimal']
            for col in bool_cols:
                if col in df.columns:
                    df[col] = df[col].astype(bool)
            
            # [Fix] Ensure numeric columns are numbers
            float_cols = ['mic_value', 'hemolysis_score', 'cpp_score', 'amp_score']
            for col in float_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            return df
    
    def get_sequence_stats(self, session_id: Optional[str] = None) -> Dict:
        """Get sequence statistics grouped by generator.
        
        Args:
            session_id: Filter by session ID (optional)
        
        Returns:
            Dict with generator statistics (count, avg_mic)
        """
        query = "SELECT generator, COUNT(*) as count, AVG(mic_value) as avg_mic FROM sequences"
        params = []
        
        if session_id:
            query += " WHERE session_id = ?"
            params.append(session_id)
        
        query += " GROUP BY generator"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            return {
                'by_generator': [
                    {'generator': r[0], 'count': r[1], 'avg_mic': r[2]}
                    for r in results
                ]
            }
    
    def get_latest_sequence(self, sequence: str, session_id: Optional[str] = None) -> Optional[Dict]:
        """Get latest evaluation result for a sequence.
        
        Args:
            sequence: Amino acid sequence string
            session_id: Filter by session ID (optional)
        
        Returns:
            Dict with sequence data and evaluation metrics, or None if not found
        """
        if not sequence:
            return None
        query = "SELECT * FROM sequences WHERE sequence = ?"
        params = [sequence]
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        query += " ORDER BY created_at DESC LIMIT 1"
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            if not row:
                return None
            columns = [d[0] for d in cursor.description]
            return dict(zip(columns, row))

    # ==================== Tool Logs Management ====================
    
    def save_tool_log(self, log_entry: Dict, session_id: str = "default") -> bool:
        """Save single tool execution log.
        
        Args:
            log_entry: Log entry dict with keys:
                - timestamp: Execution timestamp
                - tool_name: Tool name
                - status: Execution status (success/error)
                - duration_ms: Execution duration in milliseconds
                - input_args: Input arguments dict
                - output_summary: Output summary string
                - error_message: Error message (if failed)
            session_id: Session identifier
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO tool_logs 
                    (session_id, timestamp, tool_name, status, duration_ms, 
                     input_args, output_summary, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    log_entry.get('timestamp'),
                    log_entry.get('tool_name'),
                    log_entry.get('status'),
                    log_entry.get('duration_ms'),
                    json.dumps(log_entry.get('input_args', {})),
                    log_entry.get('output_summary'),
                    log_entry.get('error_message')
                ))
                
                # Update session statistics
                cursor.execute("""
                    INSERT INTO sessions (session_id, total_tool_calls)
                    VALUES (?, 1)
                    ON CONFLICT(session_id) DO UPDATE SET
                        total_tool_calls = total_tool_calls + 1,
                        last_activity = CURRENT_TIMESTAMP
                """, (session_id,))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"⚠️ Failed to save tool log: {e}")
            return False
    
    def load_tool_logs(self, session_id: Optional[str] = None, tool_name: Optional[str] = None, limit: int = 500) -> List[Dict]:
        """Load tool logs from database with optional filtering.
        
        Args:
            session_id: Filter by session ID
            tool_name: Filter by tool name
            limit: Maximum number of logs to load
        
        Returns:
            List of log entry dicts
        """
        query = "SELECT * FROM tool_logs WHERE 1=1"
        params = []
        
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        
        if tool_name:
            query += " AND tool_name = ?"
            params.append(tool_name)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            results = cursor.fetchall()
            
            logs = []
            for row in results:
                log = dict(zip(columns, row))
                # Parse JSON fields
                if log.get('input_args'):
                    try:
                        log['input_args'] = json.loads(log['input_args'])
                    except:
                        pass
                logs.append(log)
            
            return logs
    
    # ==================== Session Management ====================
    
    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """Get session information.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Dict with session metadata (start_time, last_activity, counts)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT session_id, start_time, last_activity, 
                       total_sequences, total_tool_calls
                FROM sessions WHERE session_id = ?
            """, (session_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'session_id': row[0],
                    'start_time': row[1],
                    'last_activity': row[2],
                    'total_sequences': row[3],
                    'total_tool_calls': row[4]
                }
            return None
    
    def list_sessions(self, limit: int = 50) -> List[Dict]:
        """List all sessions ordered by last activity.
        
        Args:
            limit: Maximum number of sessions to return
        
        Returns:
            List of session dicts
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT session_id, start_time, last_activity, 
                       total_sequences, total_tool_calls
                FROM sessions
                ORDER BY last_activity DESC
                LIMIT ?
            """, (limit,))
            
            columns = [desc[0] for desc in cursor.description]
            results = cursor.fetchall()
            
            return [dict(zip(columns, row)) for row in results]
    
    # ==================== Ontology/Literature Knowledge Management (Original Full Logic) ====================

    def ensure_ontology_bootstrapped(self) -> Dict[str, int]:
        """Ensure ontology/doc tables are populated from integrated knowledge JSON."""
        stats = {"entities": 0, "relations": 0, "documents": 0, "chunks": 0}

        # [Fix] Use relative path to find knowledge base file
        base_dir = Path(__file__).resolve().parent.parent
        kb_file = base_dir / "knowledge_builder" / "integrated_knowledge_base" / "01_literature_knowledge" / "literature_knowledge.json"
        
        if not kb_file.exists():
            # Silently return if knowledge base file not found
            return stats

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # If ontology entities already exist, consider initialization complete
            cursor.execute("SELECT COUNT(*) FROM ontology_entity")
            row = cursor.fetchone()
            if row and row[0] > 0:
                return stats

            try:
                with kb_file.open("r", encoding="utf-8") as f:
                    records: List[Dict[str, Any]] = json.load(f)
            except Exception:
                return stats

            # Cache for entities and co-occurrence counts
            entity_ids: Dict[tuple, str] = {}
            mech_target_counts: Dict[tuple, int] = {}

            def ensure_entity(e_type: str, name: str, source: str = "literature") -> str:
                key = (e_type, name)
                if key in entity_ids:
                    return entity_ids[key]
                eid = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO ontology_entity (id, type, name, description, source, extra_json) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (eid, e_type, name, None, source, None),
                )
                entity_ids[key] = eid
                stats["entities"] += 1
                return eid

            for item in records:
                meta = item.get("metadata", {}) or {}
                core = item.get("knowledge_core", {}) or {}
                source = meta.get("source", "unknown")

                # 1) Document entity
                doc_id = str(uuid.uuid4())
                doc_title = meta.get("title") or source
                cursor.execute(
                    "INSERT INTO ontology_entity (id, type, name, description, source, extra_json) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (doc_id, "Document", doc_title, None, "literature", json.dumps(meta, ensure_ascii=False)),
                )
                stats["entities"] += 1

                cursor.execute(
                    "INSERT INTO document (id, source, title, year, metadata) VALUES (?, ?, ?, ?, ?)",
                    (doc_id, source, doc_title, meta.get("year"), json.dumps(meta, ensure_ascii=False)),
                )
                stats["documents"] += 1

                # Chunk
                text_parts: List[str] = []
                dps = core.get("design_principles", []) or []
                mechs = core.get("action_mechanisms", []) or []
                tgts = core.get("target_organisms", []) or []
                if dps: text_parts.append("Design principles: " + "; ".join(dps))
                if mechs: text_parts.append("Mechanisms: " + "; ".join(mechs))
                if tgts: text_parts.append("Targets: " + "; ".join(tgts))

                chunk_text = "\n".join(text_parts) if text_parts else doc_title
                chunk_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO document_chunk (id, document_id, section, text, embedding) VALUES (?, ?, ?, ?, NULL)",
                    (chunk_id, doc_id, None, chunk_text),
                )
                stats["chunks"] += 1

                # 2) Entities + Relations
                for dp in dps:
                    dp_id = ensure_entity("DesignPrinciple", dp, "literature")
                    rel_id = str(uuid.uuid4())
                    cursor.execute(
                        "INSERT INTO ontology_relation (id, subject_id, predicate, object_id, source, created_at) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                        (rel_id, doc_id, "has_design_principle", dp_id, "literature"),
                    )
                    stats["relations"] += 1

                for mech in mechs:
                    mech_id = ensure_entity("Mechanism", mech, "literature")
                    rel_id = str(uuid.uuid4())
                    cursor.execute(
                        "INSERT INTO ontology_relation (id, subject_id, predicate, object_id, source, created_at) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                        (rel_id, doc_id, "has_mechanism", mech_id, "literature"),
                    )
                    stats["relations"] += 1

                for tgt in tgts:
                    tgt_id = ensure_entity("Organism", tgt, "literature")
                    rel_id = str(uuid.uuid4())
                    cursor.execute(
                        "INSERT INTO ontology_relation (id, subject_id, predicate, object_id, source, created_at) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                        (rel_id, doc_id, "has_target", tgt_id, "literature"),
                    )
                    stats["relations"] += 1

                # 3) Aggregate co-occurrence
                for mech in mechs:
                    for tgt in tgts:
                        key = (mech, tgt)
                        mech_target_counts[key] = mech_target_counts.get(key, 0) + 1

            # 4) Write association relations
            for (mech_name, tgt_name), count in mech_target_counts.items():
                mech_id = entity_ids.get(("Mechanism", mech_name)) or ensure_entity("Mechanism", mech_name, "literature")
                tgt_id = entity_ids.get(("Organism", tgt_name)) or ensure_entity("Organism", tgt_name, "literature")
                rel_id = str(uuid.uuid4())
                extra = json.dumps({"cooccurrence_count": count}, ensure_ascii=False)
                cursor.execute(
                    "INSERT INTO ontology_relation (id, subject_id, predicate, object_id, extra_json, source, created_at) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                    (rel_id, mech_id, "associated_with", tgt_id, extra, "literature"),
                )
                stats["relations"] += 1

            conn.commit()
            return stats

    def get_ontology_overview(self) -> Dict[str, Any]:
        """Compute ontology overview (Original Logic)."""
        if self.use_postgres_ontology:
            return self._get_ontology_overview_pg()
        else:
            return self._get_ontology_overview_sqlite()
    
    def _get_ontology_overview_sqlite(self) -> Dict[str, Any]:
        """Query ontology overview from SQLite (Full Original)."""
        self.ensure_ontology_bootstrapped()

        overview: Dict[str, Any] = {
            "design_principles": [],
            "action_mechanisms": [],
            "target_organisms": [],
            "experimental_values_stats": {},
            "mechanism_target_matrix": [],
        }

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            def aggregate_concept(predicate: str, concept_type: str) -> List[Dict[str, Any]]:
                cursor.execute(
                    """
                    SELECT concept.name, doc.name
                    FROM ontology_relation r
                    JOIN ontology_entity concept ON r.object_id = concept.id
                    JOIN ontology_entity doc ON r.subject_id = doc.id
                    WHERE r.predicate = ? AND concept.type = ? AND doc.type = 'Document'
                    """,
                    (predicate, concept_type),
                )
                rows = cursor.fetchall()
                counter: Dict[str, Dict[str, Any]] = {}
                for name, doc_name in rows:
                    entry = counter.setdefault(name, {"count": 0, "sources": set()})
                    entry["count"] += 1
                    entry["sources"].add(doc_name)
                items: List[Dict[str, Any]] = []
                for name, info in counter.items():
                    items.append({
                        "name": name,
                        "count": info["count"],
                        "sources": sorted(list(info["sources"])),
                    })
                items.sort(key=lambda x: x["count"], reverse=True)
                return items

            # 1) Aggregate concepts
            overview["design_principles"] = aggregate_concept("has_design_principle", "DesignPrinciple")
            overview["action_mechanisms"] = aggregate_concept("has_mechanism", "Mechanism")
            overview["target_organisms"] = aggregate_concept("has_target", "Organism")

            # 2) MIC statistics
            cursor.execute("SELECT mic_value FROM sequences WHERE mic_value IS NOT NULL")
            mic_rows = cursor.fetchall()
            mic_values = [float(r[0]) for r in mic_rows if r[0] is not None]
            if mic_values:
                vals = sorted(mic_values)
                n = len(vals)
                overview["experimental_values_stats"] = {
                    "count": n,
                    "min_uM": min(vals),
                    "max_uM": max(vals),
                    "mean_uM": sum(vals) / n if n > 0 else None,
                }

            # 3) Mechanism × Target matrix
            cursor.execute(
                """
                SELECT mech.name, tgt.name, r.extra_json
                FROM ontology_relation r
                JOIN ontology_entity mech ON r.subject_id = mech.id
                JOIN ontology_entity tgt ON r.object_id = tgt.id
                WHERE r.predicate = 'associated_with'
                """
            )
            rows = cursor.fetchall()
            matrix: List[Dict[str, Any]] = []
            for mech_name, tgt_name, extra in rows:
                count_val = None
                if extra:
                    try:
                        data = json.loads(extra)
                        count_val = data.get("cooccurrence_count")
                    except: pass
                if count_val is not None:
                    matrix.append({
                        "mechanism": mech_name,
                        "target": tgt_name,
                        "count": int(count_val),
                    })
            matrix.sort(key=lambda x: x["count"], reverse=True)
            overview["mechanism_target_matrix"] = matrix

        return overview

    def _get_ontology_overview_pg(self) -> Dict[str, Any]:
        """Query ontology overview from PostgreSQL (Full Original)."""
        overview: Dict[str, Any] = {
            "design_principles": [],
            "action_mechanisms": [],
            "target_organisms": [],
            "experimental_values_stats": {},
            "mechanism_target_matrix": [],
        }
        
        try:
            conn = psycopg2.connect(self.pg_dsn)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Aggregate design principles
            cursor.execute("""
                SELECT concept.name, COUNT(DISTINCT doc.id) as count, array_agg(DISTINCT doc.name) as sources
                FROM ontology_relation r
                JOIN ontology_entity concept ON r.object_id = concept.id
                JOIN ontology_entity doc ON r.subject_id = doc.id
                WHERE r.predicate = 'has_design_principle' AND concept.type = 'DesignPrinciple' AND doc.type = 'Document'
                GROUP BY concept.name ORDER BY count DESC
            """)
            overview["design_principles"] = [dict(row) for row in cursor.fetchall()]
            
            # Aggregate mechanisms
            cursor.execute("""
                SELECT concept.name, COUNT(DISTINCT doc.id) as count, array_agg(DISTINCT doc.name) as sources
                FROM ontology_relation r
                JOIN ontology_entity concept ON r.object_id = concept.id
                JOIN ontology_entity doc ON r.subject_id = doc.id
                WHERE r.predicate = 'has_mechanism' AND concept.type = 'Mechanism' AND doc.type = 'Document'
                GROUP BY concept.name ORDER BY count DESC
            """)
            overview["action_mechanisms"] = [dict(row) for row in cursor.fetchall()]
            
            # Aggregate targets
            cursor.execute("""
                SELECT concept.name, COUNT(DISTINCT doc.id) as count, array_agg(DISTINCT doc.name) as sources
                FROM ontology_relation r
                JOIN ontology_entity concept ON r.object_id = concept.id
                JOIN ontology_entity doc ON r.subject_id = doc.id
                WHERE r.predicate = 'has_target' AND concept.type = 'Organism' AND doc.type = 'Document'
                GROUP BY concept.name ORDER BY count DESC
            """)
            overview["target_organisms"] = [dict(row) for row in cursor.fetchall()]
            
            # Mechanism × Target matrix
            cursor.execute("""
                SELECT mech.name as mechanism, tgt.name as target, (r.extra_json->>'cooccurrence_count')::int as count
                FROM ontology_relation r
                JOIN ontology_entity mech ON r.subject_id = mech.id
                JOIN ontology_entity tgt ON r.object_id = tgt.id
                WHERE r.predicate = 'associated_with' AND mech.type = 'Mechanism' AND tgt.type = 'Organism'
                ORDER BY count DESC
            """)
            overview["mechanism_target_matrix"] = [dict(row) for row in cursor.fetchall()]
            
            # MIC statistics (Fallback to SQLite)
            with sqlite3.connect(self.db_path) as sq_conn:
                sq_cur = sq_conn.cursor()
                sq_cur.execute("SELECT mic_value FROM sequences WHERE mic_value IS NOT NULL")
                mic_rows = sq_cur.fetchall()
                mic_values = [float(r[0]) for r in mic_rows if r[0] is not None]
                if mic_values:
                    n = len(mic_values)
                    overview["experimental_values_stats"] = {
                        "count": n, "min_uM": min(mic_values), "max_uM": max(mic_values), "mean_uM": sum(mic_values) / n
                    }
                    
            conn.close()
            return overview
        except Exception as e:
            logger.error(f"❌ Failed to query ontology from PostgreSQL: {e}")
            logger.warning("⚠️  Falling back to SQLite ontology backend")
            return self._get_ontology_overview_sqlite()

    def export_sequences_to_csv(self, output_path: str, session_id: Optional[str] = None):
        """Export sequences to CSV file."""
        df = self.load_sequences(session_id=session_id)
        df.to_csv(output_path, index=False)
        return len(df)
    
    def export_sequences_to_excel(self, output_path: str, session_id: Optional[str] = None):
        """Export sequences to Excel file."""
        df = self.load_sequences(session_id=session_id)
        column_order = [
            'sequence', 'generator', 'mic_value', 'hemolysis_score', 'cpp_score',
            'amp_score', 'is_amp', 'is_cpp', 'is_toxic', 'is_pareto_optimal',
            'mic_log', 'mic_unit', 'target', 'session_id', 'created_at'
        ]
        cols = [c for c in column_order if c in df.columns]
        df = df[cols]
        df.to_excel(output_path, index=False)
        return len(df)
    
    def export_sequences_to_fasta(self, output_path: str, session_id: Optional[str] = None):
        """Export sequences to FASTA format."""
        df = self.load_sequences(session_id=session_id)
        with open(output_path, 'w') as f:
            for idx, row in df.iterrows():
                mic = self._safe_float(row.get('mic_value'))
                mic_str = f"{mic:.2f}" if mic is not None else "N/A"
                header = f">{row['generator']}|MIC:{mic_str}|AMP:{row.get('amp_score', 0):.3f}"
                f.write(f"{header}\n{row['sequence']}\n")
        return len(df)

    def mark_sequences_verified(self, seq_ids: List[int], experimental_data: Dict = None):
        """Mark sequences as experimentally verified."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        data = experimental_data or {}
        for seq_id in seq_ids:
            cursor.execute("""
                UPDATE sequences 
                SET verified = 1, 
                    experimental_mic = ?, 
                    experimental_hemolysis = ?, 
                    experimental_notes = ?, 
                    verified_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                self._safe_float(data.get('mic')),
                self._safe_float(data.get('hemolysis')),
                data.get('notes'),
                seq_id
            ))
        conn.commit()
        conn.close()
        logger.info(f"✅ Marked {len(seq_ids)} sequences as verified")
        return {"success": True, "count": len(seq_ids)}
    
    def get_verified_sequences(self, limit: int = 100):
        """Get experimentally verified sequences."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM sequences 
            WHERE verified = 1 
            ORDER BY verified_at DESC 
            LIMIT ?
        """, (limit,))
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()
        return [dict(zip(columns, row)) for row in rows]
    
    def export_sequences_to_ontology(self, seq_ids: List[int]):
        """Export sequences to ontology graph (PostgreSQL)."""
        if not self.use_postgres_ontology:
            logger.warning("⚠️  PostgreSQL ontology backend not enabled, skipping export")
            return {"success": False, "error": "PostgreSQL not enabled"}
        
        conn_sqlite = sqlite3.connect(self.db_path)
        cursor_sqlite = conn_sqlite.cursor()
        placeholders = ','.join('?' * len(seq_ids))
        cursor_sqlite.execute(f"SELECT * FROM sequences WHERE id IN ({placeholders})", seq_ids)
        columns = [desc[0] for desc in cursor_sqlite.description]
        sequences = [dict(zip(columns, row)) for row in cursor_sqlite.fetchall()]
        conn_sqlite.close()
        
        if not sequences:
            return {"success": False, "error": "No sequences found"}
        
        import psycopg2
        from psycopg2.extras import Json
        
        conn_pg = psycopg2.connect(self.pg_dsn)
        cursor_pg = conn_pg.cursor()
        
        exported_count = 0
        for seq in sequences:
            try:
                entity_id = f"design_case_{seq['id']}"
                mic_val = self._safe_float(seq.get('mic_value'))
                
                cursor_pg.execute("""
                    INSERT INTO ontology_entity (id, type, name, description, source, extra_json)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        description = EXCLUDED.description,
                        extra_json = EXCLUDED.extra_json
                """, (
                    entity_id, 'DesignCase', seq['sequence'][:20] + '...',
                    f"Verified AMP sequence (MIC: {seq.get('experimental_mic') or mic_val} μM)",
                    'user_experiment',
                    Json({
                        'sequence': seq['sequence'],
                        'generator': seq['generator'],
                        'predicted_mic': mic_val,
                        'experimental_mic': self._safe_float(seq.get('experimental_mic')),
                        'verified_at': seq.get('verified_at')
                    })
                ))
                
                if seq.get('target'):
                    target_id = f"organism_{seq['target'].replace(' ', '_').lower()}"
                    cursor_pg.execute("INSERT INTO ontology_entity (id, type, name, source) VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING", 
                                      (target_id, 'Organism', seq['target'], 'user_input'))
                    
                    relation_id = f"rel_{entity_id}_target_{target_id}"
                    cursor_pg.execute("INSERT INTO ontology_relation (id, subject_id, predicate, object_id, source) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
                                      (relation_id, entity_id, 'has_target', target_id, 'user_experiment'))
                
                exported_count += 1
            except Exception as e:
                logger.error(f"❌ Failed to export sequence {seq['id']}: {e}")
                continue
        
        conn_pg.commit()
        conn_pg.close()
        logger.info(f"✅ Exported {exported_count}/{len(sequences)} sequences to PostgreSQL ontology")
        return {"success": True, "exported": exported_count, "total": len(sequences)}

    # ========== Auto-Debug Logging Functions ==========
    
    def log_tool_failure(self, tool_name: str, params: Dict, error_history: List[Dict], session_id: str = None):
        """Record tool failure log for Auto-Debug analysis."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tool_failure_logs (tool_name, params, error_history, session_id)
            VALUES (?, ?, ?, ?)
        """, (
            tool_name,
            json.dumps(params, ensure_ascii=False),
            json.dumps(error_history, ensure_ascii=False),
            session_id
        ))
        conn.commit()
        log_id = cursor.lastrowid
        conn.close()
        logger.info(f"📝 Logged tool failure: {tool_name} (ID: {log_id})")
        return log_id
    
    def get_recent_failures(self, limit: int = 50, auto_fixed_only: bool = False):
        """Get recent tool failure records."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        query = "SELECT * FROM tool_failure_logs"
        if auto_fixed_only:
            query += " WHERE auto_fixed = 0"
        query += " ORDER BY created_at DESC LIMIT ?"
        cursor.execute(query, (limit,))
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()
        return [dict(zip(columns, row)) for row in rows]