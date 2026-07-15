"""Document Manager Service for handling file storage, metadata, and upload sessions.
"""

import os
import uuid
import time
import json
from typing import Dict, Any, List, Optional
from loguru import logger
from backend.app.core.config import settings


class DocumentManager:
    """Manages document uploads, listings, deletions, and metadata sessions."""

    def __init__(self) -> None:
        self.upload_dir = os.path.join(settings.DATA_DIR, "uploads")
        self.metadata_path = os.path.join(settings.DATA_DIR, "documents_metadata.json")
        os.makedirs(self.upload_dir, exist_ok=True)
        self._ensure_metadata_file()

    def _ensure_metadata_file(self) -> None:
        """Creates an empty metadata JSON file if not exists."""
        if not os.path.exists(self.metadata_path):
            try:
                with open(self.metadata_path, "w", encoding="utf-8") as f:
                    json.dump({}, f)
            except Exception as e:
                logger.error(f"Failed to initialize document metadata file: {e}")

    def _read_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Reads and returns the documents metadata database.
        
        Returns:
            Dict mapping doc_id -> metadata dict.
        """
        try:
            if not os.path.exists(self.metadata_path):
                return {}
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read document metadata: {e}")
            return {}

    def _write_metadata(self, data: Dict[str, Dict[str, Any]]) -> None:
        """Writes documents metadata back to the JSON file.
        
        Args:
            data: Metadata dictionary.
        """
        try:
            with open(self.metadata_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write document metadata: {e}")

    def upload_document(self, filename: str, file_content: bytes) -> Dict[str, Any]:
        """Saves a document content to disk and indexes its metadata.
        
        Args:
            filename: Original name of the uploaded file.
            file_content: Raw bytes of the file.
            
        Returns:
            Document metadata dictionary.
        """
        doc_id = str(uuid.uuid4())
        _, ext = os.path.splitext(filename)
        safe_filename = f"{doc_id}{ext}"
        filepath = os.path.join(self.upload_dir, safe_filename)

        logger.info(f"Saving uploaded document: {filename} as {safe_filename}")

        try:
            with open(filepath, "wb") as f:
                f.write(file_content)
        except Exception as e:
            logger.error(f"Failed to save file to disk: {e}")
            raise IOError(f"Failed to save file {filename}: {str(e)}")

        metadata = {
            "id": doc_id,
            "filename": filename,
            "file_path": filepath,
            "file_type": ext.lower(),
            "upload_time": time.time(),
            "file_size": len(file_content),
            "status": "uploaded",
        }

        db = self._read_metadata()
        db[doc_id] = metadata
        self._write_metadata(db)

        return metadata

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves metadata of a document.
        
        Args:
            doc_id: Unique document ID.
            
        Returns:
            Metadata dict or None if not found.
        """
        db = self._read_metadata()
        return db.get(doc_id)

    def list_documents(self) -> List[Dict[str, Any]]:
        """Returns all registered documents metadata.
        
        Returns:
            List of document metadata dicts.
        """
        db = self._read_metadata()
        return list(db.values())

    def update_status(self, doc_id: str, status: str, error_message: Optional[str] = None) -> None:
        """Updates processing status of a document.
        
        Args:
            doc_id: Document ID.
            status: New status ('processing', 'processed', 'error').
            error_message: Optional error message.
        """
        db = self._read_metadata()
        if doc_id in db:
            db[doc_id]["status"] = status
            if error_message:
                db[doc_id]["error"] = error_message
            self._write_metadata(db)

    def delete_document(self, doc_id: str) -> bool:
        """Deletes a document physical file and removes it from metadata.
        
        Args:
            doc_id: Document ID.
            
        Returns:
            True if deletion was successful, False otherwise.
        """
        db = self._read_metadata()
        if doc_id not in db:
            logger.warning(f"Document ID {doc_id} not found for deletion.")
            return False

        doc = db[doc_id]
        filepath = doc.get("file_path")

        # Delete physical file
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
                logger.info(f"Removed physical file: {filepath}")
            except Exception as e:
                logger.error(f"Failed to delete physical file {filepath}: {e}")

        # Remove from index
        del db[doc_id]
        self._write_metadata(db)
        logger.info(f"Removed document {doc_id} from metadata database.")
        return True

    def rename_document(self, doc_id: str, new_name: str) -> bool:
        """Renames a document title in metadata.
        
        Args:
            doc_id: Document ID.
            new_name: New filename.
            
        Returns:
            True if successful.
        """
        db = self._read_metadata()
        if doc_id not in db:
            return False
        
        db[doc_id]["filename"] = new_name
        self._write_metadata(db)
        logger.info(f"Renamed document {doc_id} to {new_name}")
        return True


document_manager = DocumentManager()
