"""SQLite vector backend using sqlite-vec extension."""

from pathlib import Path
from typing import List, Dict, Any, Optional
import sqlite3
import json

from .adapter import VectorBackendAdapter
from .types import VectorChunk, VectorQueryResult

class SQLiteVectorBackend(VectorBackendAdapter):
    """Vector backend using SQLite with vec extension."""
    
    def __init__(self, path: str, collection: str = "backlog"):
        self._path = Path(path)
        self._collection = collection
        self._conn: Optional[sqlite3.Connection] = None
        self._dims: Optional[int] = None
        
    def _ensure_connection(self):
        if self._conn is not None:
            return
            
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        
        # Try to load vec extension
        try:
            self._conn.enable_load_extension(True)
            # Try common extension names
            for ext_name in ["vec0", "vec", "sqlite-vec"]:
                try:
                    self._conn.load_extension(ext_name)
                    break
                except sqlite3.OperationalError:
                    continue
        except (sqlite3.OperationalError, AttributeError):
            # Extension loading not available or failed
            # We'll still create the DB but without vector search
            pass
    
    def prepare(self, schema: Dict[str, Any], dims: int, metric: str = "cosine") -> None:
        self._ensure_connection()
        self._dims = dims
        
        # Create main chunks table
        self._conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self._collection}_chunks (
                chunk_id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                metadata TEXT,
                vector BLOB
            )
        """)
        
        # Try to create virtual table for vector search
        try:
            self._conn.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS {self._collection}_vec 
                USING vec0(
                    chunk_id TEXT PRIMARY KEY,
                    embedding FLOAT[{dims}] 
                    distance_metric={metric}
                )
            """)
        except sqlite3.OperationalError:
            # vec extension not available, skip virtual table
            pass
            
        self._conn.commit()
    
    def upsert(self, chunk: VectorChunk) -> None:
        self._ensure_connection()
        
        # Serialize vector as JSON for storage
        vector_blob = json.dumps(chunk.vector) if chunk.vector else None
        metadata_json = json.dumps(chunk.metadata) if chunk.metadata else "{}"
        
        self._conn.execute(f"""
            INSERT OR REPLACE INTO {self._collection}_chunks 
            (chunk_id, text, metadata, vector)
            VALUES (?, ?, ?, ?)
        """, (chunk.chunk_id, chunk.text, metadata_json, vector_blob))
        
        # Try to update vector table
        if chunk.vector:
            try:
                # vec0 format expects vector as bytes
                vec_data = json.dumps(chunk.vector).encode()
                self._conn.execute(f"""
                    INSERT OR REPLACE INTO {self._collection}_vec 
                    (chunk_id, embedding) VALUES (?, ?)
                """, (chunk.chunk_id, vec_data))
            except sqlite3.OperationalError:
                pass
    
    def delete(self, chunk_id: str) -> None:
        self._ensure_connection()
        self._conn.execute(f"DELETE FROM {self._collection}_chunks WHERE chunk_id = ?", (chunk_id,))
        try:
            self._conn.execute(f"DELETE FROM {self._collection}_vec WHERE chunk_id = ?", (chunk_id,))
        except sqlite3.OperationalError:
            pass
    
    def query(
        self, vector: List[float], k: int = 10, filters: Dict[str, Any] | None = None
    ) -> List[VectorQueryResult]:
        self._ensure_connection()
        
        # Fetch all chunks with vectors
        cursor = self._conn.execute(f"""
            SELECT chunk_id, text, metadata, vector 
            FROM {self._collection}_chunks 
            WHERE vector IS NOT NULL
        """)
        
        results = []
        for row in cursor:
            chunk_id, text, metadata_json, vector_json = row
            
            # Deserialize vector
            try:
                stored_vector = json.loads(vector_json)
            except (json.JSONDecodeError, TypeError):
                continue
            
            # Calculate cosine similarity
            score = self._cosine_similarity(vector, stored_vector)
            
            # Parse metadata
            try:
                metadata = json.loads(metadata_json) if metadata_json else {}
            except json.JSONDecodeError:
                metadata = {}
            
            results.append(VectorQueryResult(
                chunk_id=chunk_id,
                score=score,
                metadata=metadata,
                text=text
            ))
        
        # Sort by score (descending) and return top k
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:k]
    
    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        mag1 = sum(a * a for a in vec1) ** 0.5
        mag2 = sum(b * b for b in vec2) ** 0.5
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
        
        return dot_product / (mag1 * mag2)
    
    def persist(self) -> None:
        if self._conn:
            self._conn.commit()
    
    def load(self) -> None:
        self._ensure_connection()
