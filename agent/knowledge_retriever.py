# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Knowledge-base retrieval service.
Provides vector-based knowledge retrieval for the Qwen Agent.

This module assumes the knowledge base was built by
`knowledge_builder/build_integrated_knowledge.py`, using
Sentence-Transformers `all-mpnet-base-v2` (768-d) plus a persistent
ChromaDB vector store. The primary collection is `literature_knowledge`,
with auxiliary sub-collections such as MIC / CPP / Hemolysis.

Supported knowledge types:
1. Literature knowledge (mechanism of action, design strategies, clinical trials)
2. CPP (cell-penetrating peptide) data
3. MIC antibacterial-activity data
4. Hemolysis data
5. AMP sequence-database index
6. Motif patterns
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
    """Knowledge-base retriever."""
    
    def __init__(
        self, 
        knowledge_base_dir: str = "/data/amp-generator-platform/knowledge_builder/integrated_knowledge_base",
        model_name: str = "/root/.cache/huggingface/hub/models--sentence-transformers--all-mpnet-base-v2/sentence-transformersall-mpnet-base-v2"
    ):
        """
        Initialize the knowledge-base retriever.
        
        Args:
            knowledge_base_dir: Root directory of the knowledge base.
            model_name: Path to the sentence-embedding model.
        """
        self.kb_dir = Path(knowledge_base_dir)
        self.model_name = model_name
        
        # Initialize the embedding model (offline mode)
        logger.info(f"🔧 Loading embedding model: all-mpnet-base-v2 (768-d)")
        import os
        os.environ["HF_HUB_OFFLINE"] = "1"  # Force offline
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
                
        try:
            # Load from local path
            self.embedding_model = SentenceTransformer(
                model_name,
                device="cuda" if __import__("torch").cuda.is_available() else "cpu"
            )
            logger.info(f"   ✅ Model loaded successfully (device: {self.embedding_model.device})")
        except Exception as e:
            logger.error(f"   ❌ Model load failed: {e}")
            raise RuntimeError(f"Failed to load embedding model: {e}")
        
        # Initialize ChromaDB
        self.chroma_path = self.kb_dir / "vector_store"
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🔧 Initializing ChromaDB: {self.chroma_path}")
        self.client = chromadb.PersistentClient(
            path=str(self.chroma_path),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Mapping of knowledge-base collections
        self.collections = {}
        self._init_collections()
    
    def _init_collections(self):
        """Initialize all knowledge-base collections."""
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
                logger.info(f"   ✅ Collection: {name} (docs: {self.collections[name].count()})")
            except Exception as e:
                logger.warning(f"   ⚠️ Collection {name} initialization failed: {e}")
    
    def index_literature_knowledge(self):
        """Index literature knowledge (directly vectorize the raw text)."""
        logger.info("📚 Indexing literature knowledge base...")
            
        # Prefer loading from JSON
        import json
        json_file = self.kb_dir / "01_literature_knowledge" / "literature_knowledge.json"
        if json_file.exists():
            logger.info(f"   📖 Loading literature knowledge from JSON: {json_file}")
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            collection = self.collections["literature_knowledge"]
                
            all_documents = []
            all_metadatas = []
            all_ids = []
                
            entries = data.get("entries", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                
            logger.info(f"   Found {len(entries)} literature records")
                        
            for i, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    continue
                            
                # Extract text from the complex JSON structure
                metadata = entry.get('metadata', {})
                knowledge_core = entry.get('knowledge_core', {})
                evidence_bank = entry.get('evidence_bank', {})
                            
                source_name = metadata.get('source', f'entry_{i}')
                            
                # Extract sequence context
                for seq_item in evidence_bank.get('extracted_sequences', []):
                    seq = seq_item.get('sequence', '')
                    context = seq_item.get('context_snippet', '')
                    if len(context) > 20:
                        all_documents.append(context[:1000])
                        all_metadatas.append({'type': 'literature_seq_context', 'source': source_name})
                        all_ids.append(f"lit_{i}_seq_{seq}")
                            
                # Extract mechanism descriptions
                for mech_item in evidence_bank.get('mechanism_details', []):
                    desc = mech_item.get('description_snippet', '')
                    mech = mech_item.get('mechanism', '')
                    if len(desc) > 50:
                        all_documents.append(desc[:1000])
                        all_metadatas.append({'type': 'literature_mechanism', 'source': source_name, 'mechanism': mech})
                        all_ids.append(f"lit_{i}_mech_{mech}")
                            
                # Extract design principles (convert to text)
                for principle in knowledge_core.get('design_principles', []):
                    text = f"Design principle: {principle}"
                    all_documents.append(text)
                    all_metadatas.append({'type': 'literature_principle', 'source': source_name})
                    all_ids.append(f"lit_{i}_prin_{principle}")
                
            if all_documents:
                logger.info(f"   🔄 Starting vectorization of {len(all_documents)} literature entries...")
                batch_size = 500
                    
                for i in range(0, len(all_documents), batch_size):
                    batch_docs = all_documents[i:i+batch_size]
                    batch_meta = all_metadatas[i:i+batch_size]
                    batch_ids = all_ids[i:i+batch_size]
                        
                    embeddings = self.embedding_model.encode(batch_docs, show_progress_bar=True).tolist()
                    collection.add(documents=batch_docs, embeddings=embeddings, metadatas=batch_meta, ids=batch_ids)
                    logger.info(f"      ✅ Batch {i//batch_size + 1}: {len(batch_docs)} entries")
                
            logger.info(f"✅ Literature-knowledge indexing complete. Total: {collection.count()} entries")
            return
            
        # Fall back to the raw-TXT processing path
        lit_dir = self.kb_dir.parent / "raw_literature"
        if not lit_dir.exists():
            logger.warning(f"⚠️ Raw literature directory not found: {lit_dir}")
            return
            
        collection = self.collections["literature_knowledge"]
        
        # Process raw TXT literature files directly
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
                
                # Split into paragraphs (preserve enough context)
                paragraphs = []
                current_para = []
                
                for line in content.split('\n'):
                    line = line.strip()
                    if not line:  # A blank line marks the end of a paragraph
                        if current_para:
                            para_text = ' '.join(current_para)
                            if len(para_text) > 50:  # Filter out very short paragraphs
                                paragraphs.append(para_text)
                            current_para = []
                    else:
                        current_para.append(line)
                
                # The final paragraph
                if current_para:
                    para_text = ' '.join(current_para)
                    if len(para_text) > 50:
                        paragraphs.append(para_text)
                
                # Vectorize each paragraph
                for i, para in enumerate(paragraphs):
                    # Cap length (keep the first 1000 characters)
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
                logger.info(f"      ✅ Batch {i//batch_size + 1}: {len(batch_docs)} entries (total: {total_added})")
        
        logger.info(f"✅ Literature-knowledge indexing complete. Total: {collection.count()} entries")
    
    def index_mic_data(self):
        """Index MIC data."""
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
        
        # Handle the actual data structure: data_by_activity
        total_count = 0
        for activity_level in ["high_activity", "medium_activity", "low_activity"]:
            for entry in data.get("data_by_activity", {}).get(activity_level, []):
                sequence = entry['sequence']
                mic_value = entry['mic_value']
                length = entry.get('length', len(sequence))
                
                # Build searchable text
                doc = f"AMP sequence: {sequence} | MIC value: {mic_value:.4f} | length: {length} | activity level: {activity_level.replace('_', ' ')}"
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
            logger.info(f"✅ MIC data indexing complete. Total: {len(documents)} entries")
            logger.info(f"   - High activity: {data['mic_distribution']['high_activity']} entries")
            logger.info(f"   - Medium activity: {data['mic_distribution']['medium_activity']} entries")
            logger.info(f"   - Low activity: {data['mic_distribution']['low_activity']} entries")
    
    def index_cpp_data(self):
        """Index CPP data."""
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
        
        # Handle the actual data structure: datasets
        total_count = 0
        for dataset_name, dataset_info in data.get("datasets", {}).items():
            for entry in dataset_info.get("sequences", []):
                sequence = entry['sequence']
                label = entry['label']  # 1=CPP, 0=Non-CPP
                label_text = 'CPP' if label == 1 else 'Non-CPP'
                
                # Build searchable text
                doc = f"CPP sequence: {sequence} | category: {label_text} | dataset: {dataset_name} | length: {len(sequence)}"
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
            # Batch processing (ChromaDB limit)
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
                logger.info(f"   ✅ Batch {i//batch_size + 1}: {len(batch_docs)} entries")
            
            logger.info(f"✅ CPP data indexing complete. Total: {len(documents)} entries")
            logger.info(f"   - CPP positive: {data['statistics']['cpp_positive']} entries")
            logger.info(f"   - CPP negative: {data['statistics']['cpp_negative']} entries")
    
    def index_hemolysis_data(self):
        """Index hemolysis data."""
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
        
        # Handle all_sequences
        for i, entry in enumerate(data.get("all_sequences", [])):
            sequence = entry['sequence']
            hc50 = entry['hc50']
            is_hemolytic = entry['is_hemolytic']
            hemo_text = 'hemolytic_positive' if is_hemolytic else 'hemolytic_negative'
            
            # Build searchable text
            doc = f"sequence: {sequence} | HC50: {hc50} μg/mL | category: {hemo_text} | length: {len(sequence)}"
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
                logger.info(f"   ✅ Batch {i//batch_size + 1}: {len(batch_docs)} entries")
            
            logger.info(f"✅ Hemolysis data indexing complete. Total: {len(documents)} entries")
            logger.info(f"   - Hemolytic positive: {data['statistics']['hemolytic_positive']} entries")
            logger.info(f"   - Hemolytic negative: {data['statistics']['hemolytic_negative']} entries")
    
    def search(
        self, 
        query: str, 
        knowledge_type: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search the knowledge base.
        
        Args:
            query: Query string.
            knowledge_type: Knowledge type (literature/cpp/mic/hemolysis/motif).
            top_k: Return top-k results.
        
        Returns:
            List of search results.
        """
        # Determine which collections to search
        if knowledge_type:
            # Try two possible naming formats
            collection_name = f"{knowledge_type}_data"
            alt_collection_name = f"{knowledge_type}_knowledge"
            
            collection = self.collections.get(collection_name) or self.collections.get(alt_collection_name)
            
            if collection is None:
                logger.warning(f"⚠️ Knowledge type not found: {knowledge_type} (tried: {collection_name}, {alt_collection_name})")
                collections_to_search = []
            else:
                collections_to_search = [collection]
        else:
            # Search all collections
            collections_to_search = list(self.collections.values())
        
        if not collections_to_search:
            logger.warning(f"⚠️ Knowledge type not found: {knowledge_type}")
            return []
        
        # Generate query embedding
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
                logger.error(f"❌ Failed to search collection {collection.name}: {e}")
        
        # Sort by distance
        all_results.sort(key=lambda x: x.get('distance', float('inf')))
        
        return all_results[:top_k]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get knowledge-base statistics."""
        stats = {
            "total_documents": 0,
            "collections": {}
        }
        
        for name, collection in self.collections.items():
            count = collection.count()
            stats["collections"][name] = count
            stats["total_documents"] += count
        
        return stats


def build_vector_store():
    """Build the vector store (run for initial creation or updates)."""
    logger.info("🚀 Starting to build the vector knowledge base...")
    
    retriever = KnowledgeRetriever()
    
    # Index each knowledge type
    retriever.index_literature_knowledge()
    retriever.index_mic_data()
    retriever.index_cpp_data()
    retriever.index_hemolysis_data()
    
    # Show statistics
    stats = retriever.get_statistics()
    logger.info("\n" + "="*60)
    logger.info("📊 Knowledge-base statistics:")
    logger.info(f"   Total documents: {stats['total_documents']}")
    for coll_name, count in stats['collections'].items():
        logger.info(f"   - {coll_name}: {count}")
    logger.info("="*60)
    
    logger.info("✅ Vector knowledge base built successfully!")


if __name__ == "__main__":
    # Build the vector store
    build_vector_store()
    
    # Test retrieval
    print("\n" + "="*60)
    print("🧪 Testing knowledge retrieval")
    print("="*60)
    
    retriever = KnowledgeRetriever()
    
    # Test queries
    test_queries = [
        ("What is the mechanism of action of antimicrobial peptides?", "literature"),
        ("Which sequences have an MIC value less than 1?", "mic"),
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
