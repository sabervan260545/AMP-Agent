# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Knowledge Retrieval Service for AMP Agent
===========================================

Vector-based knowledge retrieval system providing semantic search capabilities
for AMP design and evaluation.

Architecture:
- **Embedding Model**: Sentence-Transformers all-mpnet-base-v2 (768-dim)
- **Vector Store**: ChromaDB with persistent storage
- **Collections**: Literature, MIC, CPP, Hemolysis, Motif patterns

Knowledge Types:
1. Literature Knowledge (mechanisms, design strategies, clinical trials)
2. CPP Permeability Data (cell-penetrating peptides)
3. MIC Antibacterial Activity Data
4. Hemolysis Toxicity Data
5. AMP Sequence Database Index
6. Motif Patterns

Integration:
- Built by `knowledge_builder/build_integrated_knowledge.py`
- Core collection: `literature_knowledge`
- Auxiliary collections: MIC, CPP, Hemolysis subsets

Author: AMP Platform Team
Version: Production 1.0
License: MIT
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

try:
    from sentence_transformers import SentenceTransformer
    import chromadb
    from chromadb.config import Settings
except ImportError as e:
    print(f"⚠️ Missing dependency: {e}")
    print("Please run: pip install sentence-transformers chromadb")


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KnowledgeRetriever:
    """
    Vector-based knowledge retrieval system with ChromaDB backend.
    
    Provides semantic search across multiple knowledge collections using
    Sentence-Transformers embeddings.
    
    Attributes:
        kb_dir: Knowledge base root directory path
        model_name: Embedding model path (all-mpnet-base-v2)
        embedding_model: SentenceTransformer instance
        chroma_path: ChromaDB persistent storage path
        client: ChromaDB client instance
        collections: Dict of collection name to ChromaDB collection
    
    Examples:
        >>> retriever = KnowledgeRetriever()
        >>> results = retriever.search("antimicrobial mechanisms", top_k=5)
        >>> len(results)
        5
    
    Notes:
        - Runs in offline mode (no HuggingFace Hub access)
        - Uses GPU if available, falls back to CPU
        - Persistent storage across restarts
    """
    
    def __init__(
        self, 
        knowledge_base_dir: str = "/data/amp-generator-platform/knowledge_builder/integrated_knowledge_base",
        model_name: str = "/home/ubuntu/.cache/huggingface/hub/models--sentence-transformers--all-mpnet-base-v2/sentence-transformersall-mpnet-base-v2"
    ):
        """
        Initialize knowledge retriever with embedding model and vector store.
        
        Args:
            knowledge_base_dir: Knowledge base root directory
            model_name: Sentence embedding model path (local)
        
        Raises:
            RuntimeError: If embedding model fails to load
        
        Notes:
            - Forces offline mode (HF_HUB_OFFLINE=1)
            - Auto-detects CUDA availability
            - Creates ChromaDB directory if not exists
        """
        self.kb_dir = Path(knowledge_base_dir)
        self.model_name = model_name
        
        # Initialize embedding model (offline mode)
        logger.info(f"🔧 Loading embedding model: all-mpnet-base-v2 (768-dim)")
        import os
        os.environ["HF_HUB_OFFLINE"] = "1"  # Force offline mode
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
                
        try:
            # Load from local path
            self.embedding_model = SentenceTransformer(
                model_name,
                device="cuda" if __import__("torch").cuda.is_available() else "cpu"
            )
            logger.info(f"   ✅ Model loaded successfully (device: {self.embedding_model.device})")
        except Exception as e:
            logger.error(f"   ❌ Model loading failed: {e}")
            raise RuntimeError(f"Failed to load embedding model: {e}")
        
        # Initialize ChromaDB
        self.chroma_path = self.kb_dir / "vector_store"
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🔧 Initializing ChromaDB: {self.chroma_path}")
        self.client = chromadb.PersistentClient(
            path=str(self.chroma_path),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Knowledge base collection mapping
        self.collections = {}
        self._init_collections()
    
    def _init_collections(self) -> None:
        """
        Initialize all knowledge base collections.
        
        Creates or retrieves ChromaDB collections for each knowledge type.
        Uses cosine distance for similarity measurement.
        
        Collections:
            - literature_knowledge: Literature and research papers
            - cpp_data: Cell-penetrating peptide data
            - mic_data: Minimum inhibitory concentration data
            - hemolysis_data: Hemolysis toxicity data
            - motif_patterns: Sequence motif patterns
        
        Notes:
            - Logs document count for each collection
            - Warns but continues if a collection fails to initialize
        """
        collection_names = [
            "literature_knowledge",  # Literature knowledge
            "cpp_data",              # CPP data
            "mic_data",              # MIC data
            "hemolysis_data",        # Hemolysis data
            "motif_patterns"         # Motif patterns
        ]
        
        for name in collection_names:
            try:
                self.collections[name] = self.client.get_or_create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info(f"   ✅ Collection: {name} (documents: {self.collections[name].count()})")
            except Exception as e:
                logger.warning(f"   ⚠️ Collection {name} initialization failed: {e}")
    
    def index_literature_knowledge(self) -> None:
        """
        Index literature knowledge from raw text files.
        
        Processes raw .txt literature files, splits into paragraphs,
        and creates vector embeddings for semantic search.
        
        Process:
            1. Scan raw_literature directory for .txt files
            2. Split each file into paragraphs (min 50 chars)
            3. Truncate paragraphs to 1000 chars
            4. Batch vectorize (500 docs per batch)
            5. Store in literature_knowledge collection
        
        Notes:
            - Skips example.txt
            - Filters paragraphs shorter than 50 characters
            - Uses show_progress_bar for batch encoding
        """
        logger.info("📚 Indexing literature knowledge base...")
        
        lit_dir = self.kb_dir.parent / "raw_literature"
        if not lit_dir.exists():
            logger.warning(f"⚠️ Raw literature directory not found: {lit_dir}")
            return
        
        collection = self.collections["literature_knowledge"]
        
        # Process raw txt literature files
        txt_files = list(lit_dir.glob("*.txt"))
        txt_files = [f for f in txt_files if f.name not in ["example.txt"]]
        
        logger.info(f"   Found {len(txt_files)} literature files")
        
        all_documents = []
        all_metadatas = []
        all_ids = []
        
        for txt_file in txt_files:
            try:
                logger.info(f"   📖 Processing: {txt_file.name}")
                
                with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Split by paragraphs (preserve sufficient context)
                paragraphs = []
                current_para = []
                
                for line in content.split('\n'):
                    line = line.strip()
                    if not line:  # Empty line indicates paragraph end
                        if current_para:
                            para_text = ' '.join(current_para)
                            if len(para_text) > 50:  # Filter too-short paragraphs
                                paragraphs.append(para_text)
                            current_para = []
                    else:
                        current_para.append(line)
                
                # Last paragraph
                if current_para:
                    para_text = ' '.join(current_para)
                    if len(para_text) > 50:
                        paragraphs.append(para_text)
                
                # Vectorize each paragraph
                for i, para in enumerate(paragraphs):
                    # Limit length (keep first 1000 chars)
                    doc_text = para[:1000] if len(para) > 1000 else para
                    
                    all_documents.append(doc_text)
                    all_metadatas.append({
                        "type": "literature_paragraph",
                        "source": txt_file.stem,
                        "paragraph_id": i
                    })
                    all_ids.append(f"{txt_file.stem}_para_{i}")
                
                logger.info(f"      ✅ Extracted {len(paragraphs)} paragraphs")
                
            except Exception as e:
                logger.error(f"      ❌ Processing failed: {e}")
                continue
        
        # Batch vectorization
        if all_documents:
            logger.info(f"   🔄 Starting vectorization of {len(all_documents)} paragraphs...")
            batch_size = 500
            total_added = 0
            
            for i in range(0, len(all_documents), batch_size):
                batch_docs = all_documents[i:i+batch_size]
                batch_meta = all_metadatas[i:i+batch_size]
                batch_ids = all_ids[i:i+batch_size]
                
                embeddings = self.embedding_model.encode(batch_docs, show_progress_bar=True).tolist()
                collection.add(
                    documents=batch_docs,
                    embeddings=embeddings,
                    metadatas=batch_meta,
                    ids=batch_ids
                )
                total_added += len(batch_docs)
                logger.info(f"      ✅ Batch {i//batch_size + 1}: {len(batch_docs)} docs (total: {total_added})")
        
        logger.info(f"✅ Literature knowledge indexing complete, total: {collection.count()} docs")
    
    def index_mic_data(self) -> None:
        """
        Index MIC (Minimum Inhibitory Concentration) data.
        
        Processes MIC knowledge JSON file and creates searchable records
        with activity-level classification.
        
        Data Structure:
            - high_activity: MIC < threshold_1
            - medium_activity: threshold_1 <= MIC < threshold_2
            - low_activity: MIC >= threshold_2
        
        Notes:
            - Creates searchable text format with sequence, MIC value, length
            - Stores in mic_data collection
        """
        logger.info("🎯 Indexing MIC knowledge base...")
        
        mic_dir = self.kb_dir / "03_mic_data"
        mic_file = mic_dir / "mic_knowledge.json"
        
        if not mic_file.exists():
            logger.warning(f"⚠️ MIC data file not found: {mic_file}")
            return
        
        collection = self.collections["mic_data"]
        
        with open(mic_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        documents = []
        metadatas = []
        ids = []
        
        # Process actual data structure: data_by_activity
        total_count = 0
        for activity_level in ["high_activity", "medium_activity", "low_activity"]:
            for entry in data.get("data_by_activity", {}).get(activity_level, []):
                sequence = entry['sequence']
                mic_value = entry['mic_value']
                length = entry.get('length', len(sequence))
                
                # Create searchable text
                doc = f"AMP Sequence: {sequence} | MIC Value: {mic_value:.4f} | Length: {length} | Activity Level: {activity_level.replace('_', ' ')}"
                documents.append(doc)
                metadatas.append({
                    "type": "mic_record",
                    "sequence": sequence,
                    "mic_value": mic_value,
                    "length": length,
                    "activity_level": activity_level
                })
                ids.append(f"mic_{total_count}")
                total_count += 1
        
        if documents:
            logger.info(f"   🔄 Starting vectorization of {len(documents)} MIC records...")
            embeddings = self.embedding_model.encode(documents, show_progress_bar=True).tolist()
            collection.add(
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"✅ MIC data indexing complete, total: {len(documents)} docs")
            logger.info(f"   - High activity: {data['mic_distribution']['high_activity']} docs")
            logger.info(f"   - Medium activity: {data['mic_distribution']['medium_activity']} docs")
            logger.info(f"   - Low activity: {data['mic_distribution']['low_activity']} docs")
    
    def index_cpp_data(self) -> None:
        """
        Index CPP (Cell-Penetrating Peptide) data.
        
        Processes CPP knowledge JSON file with binary classification
        (CPP vs Non-CPP) from multiple datasets.
        
        Notes:
            - Label 1 = CPP, Label 0 = Non-CPP
            - Batch processing with 500 docs per batch
            - Stores in cpp_data collection
        """
        logger.info("🧬 Indexing CPP knowledge base...")
        
        cpp_dir = self.kb_dir / "02_cpp_data"
        cpp_file = cpp_dir / "cpp_knowledge.json"
        
        if not cpp_file.exists():
            logger.warning(f"⚠️ CPP data file not found: {cpp_file}")
            return
        
        collection = self.collections["cpp_data"]
        
        with open(cpp_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        documents = []
        metadatas = []
        ids = []
        
        # Process actual data structure: datasets
        total_count = 0
        for dataset_name, dataset_info in data.get("datasets", {}).items():
            for entry in dataset_info.get("sequences", []):
                sequence = entry['sequence']
                label = entry['label']  # 1=CPP, 0=Non-CPP
                label_text = 'CPP' if label == 1 else 'Non-CPP'
                
                # Create searchable text
                doc = f"CPP Sequence: {sequence} | Category: {label_text} | Dataset: {dataset_name} | Length: {len(sequence)}"
                documents.append(doc)
                metadatas.append({
                    "type": "cpp_record",
                    "sequence": sequence,
                    "label": label,
                    "label_text": label_text,
                    "dataset": dataset_name,
                    "length": len(sequence)
                })
                ids.append(f"cpp_{total_count}")
                total_count += 1
        
        if documents:
            logger.info(f"   🔄 Starting vectorization of {len(documents)} CPP records...")
            # Batch processing (ChromaDB limitation)
            batch_size = 500
            for i in range(0, len(documents), batch_size):
                batch_docs = documents[i:i+batch_size]
                batch_meta = metadatas[i:i+batch_size]
                batch_ids = ids[i:i+batch_size]
                
                embeddings = self.embedding_model.encode(batch_docs, show_progress_bar=True).tolist()
                collection.add(
                    documents=batch_docs,
                    embeddings=embeddings,
                    metadatas=batch_meta,
                    ids=batch_ids
                )
                logger.info(f"   ✅ Batch {i//batch_size + 1}: {len(batch_docs)} docs")
            
            logger.info(f"✅ CPP data indexing complete, total: {len(documents)} docs")
            logger.info(f"   - CPP positive: {data['statistics']['cpp_positive']} docs")
            logger.info(f"   - CPP negative: {data['statistics']['cpp_negative']} docs")
    
    def index_hemolysis_data(self) -> None:
        """
        Index hemolysis toxicity data.
        
        Processes hemolysis knowledge JSON file with HC50 values
        and binary classification (hemolytic vs non-hemolytic).
        
        Notes:
            - HC50 in μg/mL (concentration causing 50% hemolysis)
            - Binary label: hemolytic vs non-hemolytic
            - Batch processing with 500 docs per batch
        """
        logger.info("🩸 Indexing hemolysis knowledge base...")
        
        hemo_dir = self.kb_dir / "05_hemolysis_data"
        hemo_file = hemo_dir / "hemolysis_knowledge.json"
        
        if not hemo_file.exists():
            logger.warning(f"⚠️ Hemolysis data file not found: {hemo_file}")
            return
        
        collection = self.collections["hemolysis_data"]
        
        with open(hemo_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        documents = []
        metadatas = []
        ids = []
        
        # Process all_sequences
        for i, entry in enumerate(data.get("all_sequences", [])):
            sequence = entry['sequence']
            hc50 = entry['hc50']
            is_hemolytic = entry['is_hemolytic']
            hemo_text = 'Hemolytic Positive' if is_hemolytic else 'Hemolytic Negative'
            
            # Create searchable text
            doc = f"Sequence: {sequence} | HC50: {hc50} μg/mL | Category: {hemo_text} | Length: {len(sequence)}"
            documents.append(doc)
            metadatas.append({
                "type": "hemolysis_record",
                "sequence": sequence,
                "hc50": hc50,
                "is_hemolytic": is_hemolytic,
                "hemolytic_text": hemo_text,
                "length": len(sequence)
            })
            ids.append(f"hemo_{i}")
        
        if documents:
            logger.info(f"   🔄 Starting vectorization of {len(documents)} hemolysis records...")
            batch_size = 500
            for i in range(0, len(documents), batch_size):
                batch_docs = documents[i:i+batch_size]
                batch_meta = metadatas[i:i+batch_size]
                batch_ids = ids[i:i+batch_size]
                
                embeddings = self.embedding_model.encode(batch_docs, show_progress_bar=True).tolist()
                collection.add(
                    documents=batch_docs,
                    embeddings=embeddings,
                    metadatas=batch_meta,
                    ids=batch_ids
                )
                logger.info(f"   ✅ Batch {i//batch_size + 1}: {len(batch_docs)} docs")
            
            logger.info(f"✅ Hemolysis data indexing complete, total: {len(documents)} docs")
            logger.info(f"   - Hemolytic positive: {data['statistics']['hemolytic_positive']} docs")
            logger.info(f"   - Hemolytic negative: {data['statistics']['hemolytic_negative']} docs")
    
    def search(
        self, 
        query: str, 
        knowledge_type: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve knowledge from vector store with semantic search.
        
        Args:
            query: Query string
            knowledge_type: Knowledge type filter (literature/cpp/mic/hemolysis/motif)
            top_k: Number of top results to return
        
        Returns:
            List of retrieval result dicts with keys:
                - id: Document ID
                - document: Document text
                - metadata: Document metadata
                - distance: Cosine distance
                - collection: Collection name
        
        Examples:
            >>> retriever = KnowledgeRetriever()
            >>> results = retriever.search("antibacterial mechanisms", top_k=5)
            >>> len(results)
            5
        
        Notes:
            - Uses cosine distance (lower is more similar)
            - Returns sorted by distance (ascending)
            - Searches all collections if knowledge_type not specified
        """
        # Determine collections to search
        if knowledge_type:
            collections_to_search = [self.collections.get(f"{knowledge_type}_data") or 
                                    self.collections.get(f"{knowledge_type}_knowledge")]
            collections_to_search = [c for c in collections_to_search if c is not None]
        else:
            # Search all collections
            collections_to_search = list(self.collections.values())
        
        if not collections_to_search:
            logger.warning(f"⚠️ Knowledge type not found: {knowledge_type}")
            return []
        
        # Generate query vector
        query_embedding = self.embedding_model.encode([query])[0].tolist()
        
        all_results = []
        
        for collection in collections_to_search:
            try:
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=top_k
                )
                
                # Format results
                for i in range(len(results['ids'][0])):
                    all_results.append({
                        "id": results['ids'][0][i],
                        "document": results['documents'][0][i],
                        "metadata": results['metadatas'][0][i],
                        "distance": results['distances'][0][i] if 'distances' in results else None,
                        "collection": collection.name
                    })
            except Exception as e:
                logger.error(f"❌ Collection {collection.name} search failed: {e}")
        
        # Sort by distance
        all_results.sort(key=lambda x: x.get('distance', float('inf')))
        
        return all_results[:top_k]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get knowledge base statistics.
        
        Returns:
            Dict with keys:
                - total_documents: Total document count across all collections
                - collections: Dict of collection name to document count
        
        Examples:
            >>> retriever = KnowledgeRetriever()
            >>> stats = retriever.get_statistics()
            >>> stats['total_documents']
            10000
        """
        stats = {
            "total_documents": 0,
            "collections": {}
        }
        
        for name, collection in self.collections.items():
            count = collection.count()
            stats["collections"][name] = count
            stats["total_documents"] += count
        
        return stats


def build_vector_store() -> None:
    """
    Build vector store (run on first setup or update).
    
    Indexes all knowledge types:
        - Literature knowledge
        - MIC data
        - CPP data
        - Hemolysis data
    
    Notes:
        - Creates ChromaDB persistent storage
        - Logs statistics after completion
    """
    logger.info("🚀 Starting vector knowledge base construction...")
    
    retriever = KnowledgeRetriever()
    
    # Index all knowledge types
    retriever.index_literature_knowledge()
    retriever.index_mic_data()
    retriever.index_cpp_data()
    retriever.index_hemolysis_data()
    
    # Display statistics
    stats = retriever.get_statistics()
    logger.info("\n" + "="*60)
    logger.info("📊 Knowledge Base Statistics:")
    logger.info(f"   Total documents: {stats['total_documents']}")
    for coll_name, count in stats['collections'].items():
        logger.info(f"   - {coll_name}: {count}")
    logger.info("="*60)
    
    logger.info("✅ Vector knowledge base construction complete!")


if __name__ == "__main__":
    # Build vector store
    build_vector_store()
    
    # Test retrieval
    print("\n" + "="*60)
    print("🧪 Test Knowledge Retrieval")
    print("="*60)
    
    retriever = KnowledgeRetriever()
    
    # Test queries
    test_queries = [
        ("What is the mechanism of action of antimicrobial peptides?", "literature"),
        ("Which sequences have MIC values less than 1?", "mic"),
        ("What is the difference between CPP and non-CPP?", "cpp"),
    ]
    
    for query, ktype in test_queries:
        print(f"\n🔍 Query: {query}")
        print(f"   Type: {ktype}")
        results = retriever.search(query, knowledge_type=ktype, top_k=3)
        
        for i, result in enumerate(results, 1):
            print(f"\n   [{i}] {result['document'][:100]}...")
            print(f"       Similarity: {1 - result['distance']:.4f}")
            print(f"       Source: {result['collection']}")
