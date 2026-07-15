"""Storage Abstraction Service for persisting chunks and embeddings.
"""

import os
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from loguru import logger
from backend.app.core.config import settings


class StorageInterface(ABC):
    """Abstract interface defining document storage operations."""

    @abstractmethod
    def save_chunks(self, doc_id: str, chunks: List[Dict[str, Any]]) -> None:
        """Saves document chunks (including embeddings) to storage."""
        pass

    @abstractmethod
    def get_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """Retrieves chunks for a specific document."""
        pass

    @abstractmethod
    def delete_chunks(self, doc_id: str) -> None:
        """Deletes chunks for a specific document."""
        pass

    @abstractmethod
    def get_all_chunks(self) -> List[Dict[str, Any]]:
        """Retrieves all chunks across all documents."""
        pass


class JSONStorage(StorageInterface):
    """Concrete storage implementation using a local JSON database file."""

    def __init__(self) -> None:
        self.store_path = os.path.join(settings.DATA_DIR, "document_store.json")
        self._ensure_store_exists()

    def _ensure_store_exists(self) -> None:
        """Creates the store file if it does not exist."""
        if not os.path.exists(self.store_path):
            try:
                with open(self.store_path, "w", encoding="utf-8") as f:
                    json.dump({}, f)
                logger.info(f"Initialized empty JSON document store at {self.store_path}")
            except Exception as e:
                logger.error(f"Failed to create document store file: {e}")

    def _read_store(self) -> Dict[str, List[Dict[str, Any]]]:
        """Reads document store data.
        
        Returns:
            Dict mapping doc_id -> list of chunks.
        """
        try:
            if not os.path.exists(self.store_path):
                return {}
            with open(self.store_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read from document store: {e}")
            return {}

    def _write_store(self, data: Dict[str, List[Dict[str, Any]]]) -> None:
        """Writes data back to the document store file.
        
        Args:
            data: Document store mapping.
        """
        try:
            with open(self.store_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write to document store: {e}")

    def save_chunks(self, doc_id: str, chunks: List[Dict[str, Any]]) -> None:
        """Saves chunks for a document.
        
        Args:
            doc_id: Document identifier.
            chunks: List of chunk dicts (including embeddings list).
        """
        logger.info(f"Saving {len(chunks)} chunks for document {doc_id} to JSON store.")
        data = self._read_store()
        data[doc_id] = chunks
        self._write_store(data)

    def get_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """Retrieves chunks of a document.
        
        Args:
            doc_id: Document ID.
            
        Returns:
            List of chunk dicts.
        """
        data = self._read_store()
        return data.get(doc_id, [])

    def delete_chunks(self, doc_id: str) -> None:
        """Deletes chunks of a document.
        
        Args:
            doc_id: Document ID.
        """
        logger.info(f"Deleting chunks for document {doc_id} from JSON store.")
        data = self._read_store()
        if doc_id in data:
            del data[doc_id]
            self._write_store(data)

    def get_all_chunks(self) -> List[Dict[str, Any]]:
        """Retrieves all chunks across all documents.
        
        Returns:
            Flat list of chunk dicts.
        """
        data = self._read_store()
        all_chunks = []
        for chunks_list in data.values():
            all_chunks.extend(chunks_list)
        return all_chunks


# Initialize concrete JSON storage instance
storage_service = JSONStorage()
