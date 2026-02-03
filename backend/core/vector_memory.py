"""
向量记忆管理模块 - 基于 ChromaDB 实现 RAG

功能：
- 存储和检索历史对话的向量表示
- 支持基于语义的上下文检索
"""

import os
import logging
import chromadb
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

class VectorMemory:
    def __init__(self, db_path: str = "data/vector_db"):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(self.db_path, exist_ok=True)
        
        try:
            self.client = chromadb.PersistentClient(path=self.db_path)
            self.collection = self.client.get_or_create_collection(
                name="chat_history",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"VectorMemory initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self.client = None
            self.collection = None

    def add_text(self, text: str, metadata: Dict[str, Any], id: str, embedding: Optional[List[float]] = None) -> None:
        if not self.collection:
            return
            
        try:
            if embedding:
                self.collection.add(
                    documents=[text],
                    metadatas=[metadata],
                    embeddings=[embedding],
                    ids=[id]
                )
            else:
                self.collection.add(
                    documents=[text],
                    metadatas=[metadata],
                    ids=[id]
                )
        except Exception as e:
            logger.error(f"Failed to add text to vector db: {e}")

    def search(self, query: Optional[str] = None, n_results: int = 5, filter_meta: Optional[Dict] = None, query_embedding: Optional[List[float]] = None) -> List[Dict[str, Any]]:
        if not self.collection:
            return []
            
        try:
            if query_embedding:
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where=filter_meta
                )
            else:
                results = self.collection.query(
                    query_texts=[query or ""],
                    n_results=n_results,
                    where=filter_meta
                )
            
            formatted = []
            if results['documents']:
                for i in range(len(results['documents'][0])):
                    formatted.append({
                        'text': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'distance': results['distances'][0][i] if results['distances'] else 0.0
                    })
            return formatted
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def delete(self, where: Dict[str, Any]) -> None:
        """删除记录"""
        if not self.collection:
            return
        try:
            self.collection.delete(where=where)
        except Exception as e:
            logger.error(f"Vector delete failed: {e}")
