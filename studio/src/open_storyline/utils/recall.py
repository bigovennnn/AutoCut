# Modified by the AutoCut project, 2026-10-12: lightweight operation and export correctness.
import os
import math
import re
from collections import Counter
from typing import Any, Dict, List


class LexicalIndex:
    """Small deterministic text index; never loads neural model weights."""

    def __init__(self, data: List[Dict[str, Any]], field: str) -> None:
        self.data = data
        self.vectors = [self._tokens(str(item.get(field, ""))) for item in data]

    @staticmethod
    def _tokens(text: str) -> Counter:
        text = text.lower()
        words = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", text)
        words.extend(text[i:i + 2] for i in range(len(text) - 1) if not text[i:i + 2].isspace())
        return Counter(words)

    def search(self, query: str, n: int) -> List[Dict[str, Any]]:
        vector = self._tokens(query)
        qnorm = math.sqrt(sum(v * v for v in vector.values()))
        def score(index: int) -> float:
            candidate = self.vectors[index]
            norm = math.sqrt(sum(v * v for v in candidate.values()))
            return sum(value * candidate.get(key, 0) for key, value in vector.items()) / (qnorm * norm) if qnorm and norm else 0.0
        indices = sorted(range(len(self.data)), key=lambda i: (-score(i), i))
        return [self.data[i] for i in indices[:max(0, n)]]

class StorylineRecall:
    @staticmethod
    def build_vectorstore(
        data: list[dict], 
        field: str = "description", 
        model_name: str = "./.storyline/models/all-MiniLM-L6-v2", 
        device: str = "cpu",
        backend: str = "embedding",
    ):
        """
        Build a FAISS vectorstore using a local HuggingFace embedding model.

        Args:
            data: list of dicts
            field: which text field to embed
            model_name: HuggingFace model identifier
            device: "cpu" or "cuda" if available

        Returns:
            FAISS vectorstore
        """
        if backend == "lexical":
            return LexicalIndex(data, field)
        if not any(item.get(field) for item in data):
            return None
        if backend != "embedding":
            raise ValueError(f"Unsupported retrieval backend: {backend}")
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            from langchain_core.documents import Document
            from langchain_community.vectorstores.faiss import FAISS
        except ImportError as exc:
            raise RuntimeError("Embedding retrieval requires the optional local-model dependencies; select lexical for the lightweight profile.") from exc
        if not os.path.exists(model_name):
            model_name = "sentence-transformers/all-MiniLM-L6-v2"

        # Create embeddings using HF model
        embeddings = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": device}
        )

        # Construct LangChain Documents
        docs = []
        for item in data:
            text = item.get(field, "")
            if text:
                docs.append(Document(page_content=text, metadata=item))

        if not docs:
            print(f"[RECALL - Build vectorstore] Cannot find field: {field}, return None.")
            return None
        # Build FAISS
        vectorstore = FAISS.from_documents(docs, embeddings)
        return vectorstore

    @staticmethod
    def query_top_n(vectorstore, query: str, n: int = 32):
        """
        Query the vectorstore and return top-N original dicts.

        Args:
            vectorstore: FAISS
            query: query string
            n: number of results

        Returns:
            list of original dict entries
        """
        if vectorstore is None:
            return []
        if isinstance(vectorstore, LexicalIndex):
            return vectorstore.search(query, n)
        results = vectorstore.similarity_search(query, k=n)
        return [doc.metadata for doc in results]
