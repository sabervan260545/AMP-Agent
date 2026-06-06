# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Graph RAG Query Interface for AMP Ontology

Provides semantic + structural queries over PostgreSQL + pgvector ontology backend.
Can be integrated into Agent tools for advanced knowledge retrieval.
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class GraphRAGQuery:
    """
    Graph RAG query interface: Combining graph structure + semantic retrieval.
    
    Provides hybrid knowledge retrieval from PostgreSQL + pgvector ontology backend,
    combining structural graph queries with vector similarity search.
    
    Capabilities:
    - Mechanism discovery for specific target organisms
    - Design principle recommendations for mechanisms
    - Ontology triplet path traversal
    - Semantic vector search over document chunks
    
    Attributes:
        pg_dsn: PostgreSQL connection string (from ONTOLOGY_PG_DSN env var)
    
    Examples:
        >>> query = GraphRAGQuery()
        >>> results = query.query_mechanism_by_target("E.coli", limit=5)
        >>> len(results)
        5
    
    Notes:
        - Requires PostgreSQL with pgvector extension
        - Uses ILIKE for fuzzy entity matching
        - Results ordered by literature frequency (doc_count)
    """
    
    def __init__(self, pg_dsn: str = None):
        self.pg_dsn = pg_dsn or os.getenv("ONTOLOGY_PG_DSN")
        if not self.pg_dsn:
            raise ValueError("ONTOLOGY_PG_DSN not set")
    
    def query_mechanism_by_target(self, target: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Query mechanisms for specific target organism (sorted by literature frequency).
        
        Retrieves antimicrobial mechanisms associated with a target organism
        by aggregating across literature documents in the ontology.
        
        Args:
            target: Target organism name (supports fuzzy matching)
            limit: Maximum number of mechanisms to return
        
        Returns:
            List of dicts with keys:
                - mechanism (str): Mechanism name
                - doc_count (int): Number of supporting documents
                - evidence_docs (list): List of document titles
        
        Examples:
            >>> query.query_mechanism_by_target("E.coli")
            [{'mechanism': 'membrane_disruption', 'doc_count': 5, 'evidence_docs': [...]}, ...]
        
        Notes:
            - Uses ILIKE for case-insensitive fuzzy matching
            - Results ordered by doc_count DESC
        """
        conn = psycopg2.connect(self.pg_dsn)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            WITH target_docs AS (
                SELECT DISTINCT r.subject_id as doc_id
                FROM ontology_relation r
                JOIN ontology_entity tgt ON r.object_id = tgt.id
                WHERE r.predicate = 'has_target' 
                  AND tgt.type = 'Organism'
                  AND tgt.name ILIKE %s
            )
            SELECT 
                mech.name as mechanism,
                COUNT(DISTINCT r.subject_id) as doc_count,
                array_agg(DISTINCT doc.name) as evidence_docs
            FROM ontology_relation r
            JOIN ontology_entity mech ON r.object_id = mech.id
            JOIN ontology_entity doc ON r.subject_id = doc.id
            WHERE r.predicate = 'has_mechanism'
              AND mech.type = 'Mechanism'
              AND r.subject_id IN (SELECT doc_id FROM target_docs)
            GROUP BY mech.name
            ORDER BY doc_count DESC
            LIMIT %s
        """, (f"%{target}%", limit))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def query_design_principles_for_mechanism(self, mechanism: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Query design principles co-occurring with specific mechanism.
        
        Retrieves design principles that frequently co-occur with a given
        mechanism in literature, useful for rational AMP design guidance.
        
        Args:
            mechanism: Mechanism name (supports fuzzy matching)
            limit: Maximum number of principles to return
        
        Returns:
            List of dicts with keys:
                - principle (str): Design principle name
                - doc_count (int): Number of supporting documents
                - evidence_docs (list): List of document titles
        
        Examples:
            >>> query.query_design_principles_for_mechanism("membrane_disruption")
            [{'principle': 'cationic_enhancement', 'doc_count': 4, ...}, ...]
        
        Notes:
            - Results ordered by co-occurrence frequency
            - Helps identify which design principles are effective for specific mechanisms
        """
        conn = psycopg2.connect(self.pg_dsn)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            WITH mech_docs AS (
                SELECT DISTINCT r.subject_id as doc_id
                FROM ontology_relation r
                JOIN ontology_entity mech ON r.object_id = mech.id
                WHERE r.predicate = 'has_mechanism' 
                  AND mech.type = 'Mechanism'
                  AND mech.name ILIKE %s
            )
            SELECT 
                dp.name as principle,
                COUNT(DISTINCT r.subject_id) as doc_count,
                array_agg(DISTINCT doc.name) as evidence_docs
            FROM ontology_relation r
            JOIN ontology_entity dp ON r.object_id = dp.id
            JOIN ontology_entity doc ON r.subject_id = doc.id
            WHERE r.predicate = 'has_design_principle'
              AND dp.type = 'DesignPrinciple'
              AND r.subject_id IN (SELECT doc_id FROM mech_docs)
            GROUP BY dp.name
            ORDER BY doc_count DESC
            LIMIT %s
        """, (f"%{mechanism}%", limit))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def query_triplet_path(self, 
                          start_entity: str, 
                          start_type: str,
                          relation: str,
                          target_type: str,
                          limit: int = 20) -> List[Dict[str, Any]]:
        """
        Query ontology triplet paths (subject-predicate-object).
        
        Generic graph traversal for exploring entity relationships
        in the AMP ontology knowledge graph.
        
        Args:
            start_entity: Starting entity name (supports fuzzy matching)
            start_type: Entity type (e.g., 'Organism', 'Mechanism')
            relation: Predicate/relationship type (e.g., 'has_target')
            target_type: Target entity type
            limit: Maximum number of triplets to return
        
        Returns:
            List of dicts with keys:
                - subject (str): Subject entity name
                - predicate (str): Relationship type
                - object (str): Object entity name
                - extra_json (dict): Additional metadata (optional)
        
        Examples:
            >>> query.query_triplet_path("E.coli", "Organism", "has_target", "Document")
            [{'subject': 'E.coli', 'predicate': 'has_target', 'object': 'Paper_123'}, ...]
        
        Notes:
            - Flexible for custom graph queries
            - Can be chained for multi-hop reasoning
        """
        conn = psycopg2.connect(self.pg_dsn)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT 
                subj.name as subject,
                r.predicate,
                obj.name as object,
                r.extra_json
            FROM ontology_relation r
            JOIN ontology_entity subj ON r.subject_id = subj.id
            JOIN ontology_entity obj ON r.object_id = obj.id
            WHERE subj.type = %s
              AND obj.type = %s
              AND r.predicate = %s
              AND subj.name ILIKE %s
            LIMIT %s
        """, (start_type, target_type, relation, f"%{start_entity}%", limit))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def semantic_search_chunks(self, 
                               query_embedding: List[float],
                               top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Vector-based semantic search over document chunks (requires embedding populated).
        
        Performs cosine similarity search using pgvector extension to find
        semantically relevant document chunks.
        
        Args:
            query_embedding: Query vector (768-dim for all-mpnet-base-v2)
            top_k: Number of top results to return
        
        Returns:
            List of dicts with keys:
                - text (str): Document chunk text
                - title (str): Source document title
                - source (str): Document source identifier
                - year (int): Publication year
                - similarity (float): Cosine similarity score (0-1)
        
        Examples:
            >>> from sentence_transformers import SentenceTransformer
            >>> model = SentenceTransformer('all-mpnet-base-v2')
            >>> query_emb = model.encode("antimicrobial peptides membrane disruption").tolist()
            >>> results = query.semantic_search_chunks(query_emb, top_k=5)
            >>> results[0]['similarity']
            0.92
        
        Notes:
            - Requires document_chunk.embedding to be pre-populated
            - Uses pgvector <=> operator for cosine distance
            - Results ordered by similarity DESC
        """
        conn = psycopg2.connect(self.pg_dsn)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # pgvector cosine distance
        cursor.execute("""
            SELECT 
                chunk.text,
                doc.title,
                doc.source,
                doc.year,
                1 - (chunk.embedding <=> %s::vector) as similarity
            FROM document_chunk chunk
            JOIN document doc ON chunk.document_id = doc.id
            WHERE chunk.embedding IS NOT NULL
            ORDER BY chunk.embedding <=> %s::vector
            LIMIT %s
        """, (query_embedding, query_embedding, top_k))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results


# Convenience functions: For direct Agent tool invocation
def query_mechanisms_for_target(target: str, limit: int = 5) -> Dict[str, Any]:
    """
    Query mechanisms for specific target (convenience function for Agent tools).
    
    Wrapper function with error handling for Agent tool integration.
    
    Args:
        target: Target organism name
        limit: Maximum number of mechanisms to return
    
    Returns:
        Dict with keys:
            - success (bool): Query success status
            - target (str): Target organism
            - mechanisms (list): List of mechanism dicts
            - error (str): Error message (if failed)
    
    Examples:
        >>> result = query_mechanisms_for_target("E.coli", limit=5)
        >>> result['success']
        True
        >>> len(result['mechanisms'])
        5
    """
    try:
        q = GraphRAGQuery()
        results = q.query_mechanism_by_target(target, limit)
        return {
            "success": True,
            "target": target,
            "mechanisms": results,
        }
    except Exception as e:
        logger.error(f"Failed to query mechanisms for target {target}: {e}")
        return {"success": False, "error": str(e)}


def query_principles_for_mechanism(mechanism: str, limit: int = 5) -> Dict[str, Any]:
    """
    Query design principles co-occurring with mechanism (convenience function for Agent tools).
    
    Wrapper function with error handling for Agent tool integration.
    
    Args:
        mechanism: Mechanism name
        limit: Maximum number of principles to return
    
    Returns:
        Dict with keys:
            - success (bool): Query success status
            - mechanism (str): Mechanism name
            - design_principles (list): List of principle dicts
            - error (str): Error message (if failed)
    
    Examples:
        >>> result = query_principles_for_mechanism("membrane_disruption", limit=5)
        >>> result['success']
        True
        >>> len(result['design_principles'])
        5
    """
    try:
        q = GraphRAGQuery()
        results = q.query_design_principles_for_mechanism(mechanism, limit)
        return {
            "success": True,
            "mechanism": mechanism,
            "design_principles": results,
        }
    except Exception as e:
        logger.error(f"Failed to query principles for mechanism {mechanism}: {e}")
        return {"success": False, "error": str(e)}
