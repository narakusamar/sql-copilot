"""
Agent Memory: 使用 embedding 语义相似度检索历史成功 SQL
"""
import sqlite3
import numpy as np
from datetime import datetime
from pathlib import Path
from sentence_transformers import SentenceTransformer

from core.config import Config

EMBEDDING_MODEL = "shibing624/text2vec-base-chinese"


def _sanitize(text: str) -> str:
    return text.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="replace")


class Memory:
    _model: SentenceTransformer | None = None

    def __init__(self):
        self.db_path = str(Path(__file__).parent.parent / "memory.db")
        self._init_table()
        self._load_model()

    @classmethod
    def _load_model(cls):
        if cls._model is None:
            import os
            if Config.HF_ENDPOINT:
                os.environ.setdefault("HF_ENDPOINT", Config.HF_ENDPOINT)
            cls._model = SentenceTransformer(EMBEDDING_MODEL)

    @property
    def model(self) -> SentenceTransformer:
        return self._model

    def _init_table(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT,
                sql TEXT,
                success INTEGER DEFAULT 1,
                created_at TEXT
            )
        """)
        try:
            conn.execute("ALTER TABLE memory_log ADD COLUMN embedding BLOB")
        except sqlite3.OperationalError:
            pass
        conn.commit()
        conn.close()

    def _encode(self, text: str) -> np.ndarray:
        return self.model.encode(_sanitize(text), normalize_embeddings=True)

    def save(self, question: str, sql: str, success: bool = True):
        emb = self._encode(question).tobytes()
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO memory_log (question, sql, success, created_at, embedding) "
            "VALUES (?, ?, ?, ?, ?)",
            (_sanitize(question), _sanitize(sql), int(success),
             datetime.now().isoformat(), emb),
        )
        conn.commit()
        conn.close()

    def recall_similar(self, question: str, limit: int = 3) -> list[tuple]:
        """语义相似度检索历史 SQL"""
        conn = sqlite3.connect(self.db_path)

        if not question.strip():
            rows = conn.execute(
                "SELECT question, sql FROM memory_log WHERE success=1 "
                "ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            conn.close()
            return rows

        query_vec = self._encode(question)

        rows = conn.execute(
            "SELECT id, question, sql, embedding FROM memory_log "
            "WHERE success=1 AND embedding IS NOT NULL"
        ).fetchall()
        conn.close()

        if not rows:
            return []

        scored = []
        dim = query_vec.shape[0]
        for rid, q, s, emb_blob in rows:
            emb = np.frombuffer(emb_blob, dtype=np.float32)
            if emb.shape[0] != dim:
                continue  # 跳过旧模型不兼容的向量
            sim = float(np.dot(query_vec, emb))
            scored.append((sim, q, s))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [(q, s) for _, q, s in scored[:limit]]
