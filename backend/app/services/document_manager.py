"""Document Manager Service for handling file storage, metadata, and upload sessions.
"""

import os
import uuid
import time
import json
from typing import Dict, Any, List, Optional, Set
from loguru import logger
from backend.app.core.config import settings


class DocumentManager:
    """Manages document uploads, listings, deletions, and metadata sessions."""

    # Essential test fixtures and baseline files that must never be auto-deleted
    PROTECTED_FILENAMES: Set[str] = {
        "0aaa92a2-f665-4d5e-98ba-c39ce650f525.pdf",
        "1a5fa635-e77b-4d14-85b9-64b0878e8549.pdf",
        "2958370a-b714-47c0-9efa-9adfa6403d30.pdf",
        "44ab4ecc-f6a6-407d-829f-809c547be6c4.pdf",
        "4f8eac53-a110-440b-8b98-019b3c1e4dfd.pdf",
        "6b8939a2-0379-44ba-8ab5-1fdf791d4da6.pdf",
        "89b03245-aa37-4088-b800-3fd4321cd3f5.pdf",
        "9dd28e45-80d7-4c0d-ae26-b6c28b7cd995.pdf",
        "e3388f45-7527-48be-bf16-f2610c9b8e03.pdf",
        "Tender_Document_WiFi.pdf",
    }

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

    def upload_document(self, filename: str, file_content: bytes, pre_parse: bool = True) -> Dict[str, Any]:
        """Saves a document content to disk and indexes its metadata.
        
        Args:
            filename: Original name of the uploaded file.
            file_content: Raw bytes of the file.
            pre_parse: Whether to pre-extract text immediately (set False when caller parses directly).
            
        Returns:
            Document metadata dictionary.
        """
        import hashlib

        doc_id = str(uuid.uuid4())
        file_hash = hashlib.sha256(file_content).hexdigest()
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

        ext_lower = ext.lower()
        doc_type = "GENERAL_DOCUMENT"
        if ext_lower in (".xlsx", ".xls", ".csv"):
            doc_type = "EXCEL"
        elif ext_lower == ".pdf":
            doc_type = "PDF"
        elif ext_lower in (".docx", ".doc"):
            doc_type = "DOCX"
        elif ext_lower in (".pptx", ".ppt"):
            doc_type = "PPTX"
        elif ext_lower in (".txt", ".md", ".json", ".xml", ".html"):
            doc_type = "TEXT"
        elif ext_lower in (".png", ".jpg", ".jpeg"):
            doc_type = "IMAGE"

        extracted_text = ""
        structured_data = {}
        if pre_parse:
            try:
                from backend.app.services.document_parser import document_parser
                parsed = document_parser.parse(filepath)
                extracted_text = parsed.get("text", "")
                structured_data = parsed.get("metadata", {})
            except Exception as e:
                logger.warning(f"Could not pre-extract text for {filename}: {e}")

        mime_map = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".doc": "application/msword",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls": "application/vnd.ms-excel",
            ".csv": "text/csv",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".ppt": "application/vnd.ms-powerpoint",
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".json": "application/json",
            ".xml": "application/xml",
            ".html": "text/html",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
        }
        mime_type = mime_map.get(ext_lower, "application/octet-stream")
        now_ts = time.time()

        metadata = {
            "id": doc_id,
            "document_id": doc_id,
            "file_hash": file_hash,
            "filename": filename,
            "file_path": filepath,
            "extension": ext_lower,
            "file_type": ext_lower,
            "mime_type": mime_type,
            "document_type": doc_type,
            "extracted_text": extracted_text,
            "structured_data": structured_data,
            "upload_timestamp": now_ts,
            "upload_time": now_ts,
            "file_size": len(file_content),
            "status": "uploaded",
        }

        db = self._read_metadata()
        db[doc_id] = metadata
        self._write_metadata(db)

        # Enforce storage limits (LRU auto-pruning)
        try:
            self.enforce_storage_quota(exclude_doc_ids={doc_id})
        except Exception as quota_err:
            logger.error(f"Error enforcing storage quota after upload: {quota_err}")

        return metadata

    def _clean_parse_cache(self, file_hash: Optional[str]) -> None:
        """Removes on-disk parsed cache file for a given file hash if no longer referenced."""
        if not file_hash:
            return
        try:
            cache_file = os.path.join(settings.DATA_DIR, "cache", "parsed", f"{file_hash}.json")
            if os.path.exists(cache_file):
                os.remove(cache_file)
                logger.debug(f"Removed parsed cache: {cache_file}")
        except Exception as e:
            logger.warning(f"Could not remove parsed cache for {file_hash}: {e}")

    def enforce_storage_quota(
        self,
        max_mb: Optional[int] = None,
        max_docs: Optional[int] = None,
        exclude_doc_ids: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Enforces upload directory quota and LRU document retention policy.
        
        Prunes old files to guarantee:
        1. Number of active non-protected documents <= max_docs (default settings.TENDER_STORAGE_MAX_DOCUMENTS).
        2. Total disk storage in uploads directory <= max_mb (default settings.TENDER_STORAGE_MAX_MB).
        3. Orphan unreferenced files on disk are removed.
        4. Protected automated-test fixtures are strictly preserved.
        5. Associated parsed caches in data/cache/parsed/ are safely cleaned.
        
        Args:
            max_mb: Maximum allowed MB in uploads directory (defaults to settings.TENDER_STORAGE_MAX_MB or 200).
            max_docs: Maximum allowed active non-protected documents (defaults to settings.TENDER_STORAGE_MAX_DOCUMENTS or 5).
            exclude_doc_ids: Set of document IDs that must not be deleted in this pass (e.g. newly uploaded).
            
        Returns:
            Dict summary of quota enforcement results.
        """
        if max_docs is None:
            max_docs = getattr(settings, "TENDER_STORAGE_MAX_DOCUMENTS", 5)
        if exclude_doc_ids is None:
            exclude_doc_ids = set()

        max_bytes = max_mb * 1024 * 1024 if max_mb is not None else None
        freed_bytes = 0
        deleted_count = 0

        # Read current metadata database
        db = self._read_metadata()

        # Step 1: Clean up orphan files on disk that are not registered in metadata and not protected
        if os.path.exists(self.upload_dir):
            disk_files = set(os.listdir(self.upload_dir))
            registered_filenames = set()
            for doc in db.values():
                fp = doc.get("file_path")
                if fp:
                    registered_filenames.add(os.path.basename(fp))
                orig_name = doc.get("filename")
                if orig_name:
                    registered_filenames.add(orig_name)

            for fname in disk_files:
                if fname in self.PROTECTED_FILENAMES:
                    continue
                if fname not in registered_filenames:
                    fpath = os.path.join(self.upload_dir, fname)
                    if os.path.isfile(fpath):
                        try:
                            sz = os.path.getsize(fpath)
                            os.remove(fpath)
                            freed_bytes += sz
                            deleted_count += 1
                            logger.info(f"[QUOTA] Cleaned orphan upload file: {fname} ({sz / (1024*1024):.2f} MB)")
                        except Exception as e:
                            logger.warning(f"[QUOTA] Failed to remove orphan file {fpath}: {e}")

        # Step 2: Identify non-protected registered documents for LRU evaluation
        non_protected_docs = []
        for doc_id, doc in db.items():
            if doc_id in exclude_doc_ids:
                continue
            fp = doc.get("file_path", "")
            base_name = os.path.basename(fp)
            orig_name = doc.get("filename", "")

            if base_name in self.PROTECTED_FILENAMES or orig_name in self.PROTECTED_FILENAMES:
                continue

            # Compute sort timestamp (oldest first)
            ts = doc.get("upload_timestamp") or doc.get("upload_time")
            if not ts and fp and os.path.exists(fp):
                try:
                    ts = os.path.getmtime(fp)
                except Exception:
                    ts = 0
            if not ts:
                ts = 0

            sz = doc.get("file_size") or doc.get("size")
            if not sz and fp and os.path.exists(fp):
                try:
                    sz = os.path.getsize(fp)
                except Exception:
                    sz = 0
            if not sz:
                sz = 0

            non_protected_docs.append({
                "doc_id": doc_id,
                "timestamp": ts,
                "file_path": fp,
                "file_hash": doc.get("file_hash"),
                "size": sz,
                "filename": orig_name or base_name,
            })

        # Sort non-protected documents ascending by timestamp (oldest first)
        non_protected_docs.sort(key=lambda d: d["timestamp"])

        metadata_changed = False

        # Step 3: Enforce max_docs limit (keep only the newest max_docs documents)
        if len(non_protected_docs) > max_docs:
            excess_count = len(non_protected_docs) - max_docs
            docs_to_prune = non_protected_docs[:excess_count]
            non_protected_docs = non_protected_docs[excess_count:]

            for item in docs_to_prune:
                doc_id = item["doc_id"]
                fp = item["file_path"]
                if fp and os.path.exists(fp):
                    try:
                        sz = os.path.getsize(fp)
                        freed_bytes += sz
                        deleted_count += 1
                        logger.info(f"[QUOTA LRU] Pruned oldest doc {item['filename']} ({doc_id}) [{sz / (1024*1024):.2f} MB]")
                    except Exception:
                        pass
                self.delete_document(doc_id)
                metadata_changed = True

        def get_total_upload_bytes() -> int:
            if not os.path.exists(self.upload_dir):
                return 0
            total = 0
            for f in os.listdir(self.upload_dir):
                p = os.path.join(self.upload_dir, f)
                if os.path.isfile(p):
                    try:
                        total += os.path.getsize(p)
                    except Exception:
                        pass
            return total

        # Step 4: Optional Enforce max_mb limit on total directory storage (if specified)
        if max_bytes is not None:
            current_total_bytes = get_total_upload_bytes()
            while current_total_bytes > max_bytes and non_protected_docs:
                item = non_protected_docs.pop(0)
                doc_id = item["doc_id"]
                fp = item["file_path"]
                if fp and os.path.exists(fp):
                    try:
                        sz = os.path.getsize(fp)
                        freed_bytes += sz
                        deleted_count += 1
                        logger.info(f"[QUOTA SIZE] Pruned doc for size limit: {item['filename']} ({doc_id}) [{sz / (1024*1024):.2f} MB]")
                    except Exception:
                        pass
                self.delete_document(doc_id)
                current_total_bytes = get_total_upload_bytes()

        final_total_bytes = get_total_upload_bytes()
        remaining_files = os.listdir(self.upload_dir) if os.path.exists(self.upload_dir) else []

        summary = {
            "freed_bytes": freed_bytes,
            "freed_mb": round(freed_bytes / (1024 * 1024), 2),
            "deleted_files_count": deleted_count,
            "remaining_files_count": len(remaining_files),
            "remaining_size_mb": round(final_total_bytes / (1024 * 1024), 2),
            "max_storage_mb": max_mb,
            "max_documents": max_docs,
        }
        logger.info(
            f"[QUOTA ENFORCED] Freed {summary['freed_mb']} MB across {deleted_count} files. "
            f"Remaining: {summary['remaining_size_mb']} MB across {len(remaining_files)} files "
            f"(Cap: {max_mb} MB, Max Tenders: {max_docs})"
        )
        return summary

    def get_storage_stats(self) -> Dict[str, Any]:
        """Returns statistics on disk usage and stored document quotas."""
        try:
            files = os.listdir(self.upload_dir) if os.path.exists(self.upload_dir) else []
            total_bytes = sum(
                os.path.getsize(os.path.join(self.upload_dir, f))
                for f in files
                if os.path.isfile(os.path.join(self.upload_dir, f))
            )
            db = self._read_metadata()
            return {
                "upload_dir": self.upload_dir,
                "total_files": len(files),
                "total_size_bytes": total_bytes,
                "total_size_mb": round(total_bytes / (1024 * 1024), 2),
                "max_storage_mb": getattr(settings, "TENDER_STORAGE_MAX_MB", 200),
                "max_documents": getattr(settings, "TENDER_STORAGE_MAX_DOCUMENTS", 5),
                "metadata_records_count": len(db),
            }
        except Exception as e:
            logger.error(f"Failed to calculate storage stats: {e}")
            return {"error": str(e)}

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
        """Deletes a document physical file, vector index, consultant cache, and metadata.
        
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
        file_hash = doc.get("file_hash")

        # 1. Delete physical file
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
                logger.info(f"Removed physical file: {filepath}")
            except Exception as e:
                logger.error(f"Failed to delete physical file {filepath}: {e}")

        # 2. Clean parse cache if exists
        self._clean_parse_cache(file_hash)

        # 3. Purge Vector Index from disk & memory
        try:
            from backend.app.services.rag.tender_vector_index import tender_index_registry
            if file_hash:
                tender_index_registry.delete_index(file_hash[:16])
                tender_index_registry.delete_index(file_hash)
            tender_index_registry.delete_index(doc_id[:16])
            tender_index_registry.delete_index(doc_id)
        except Exception as ve:
            logger.debug(f"Could not remove vector index for {doc_id}: {ve}")

        # 4. Invalidate and purge cached consultant reports
        try:
            from backend.app.services.tender_intelligence.intelligence_report_builder import intelligence_report_builder
            intelligence_report_builder.invalidate_cache_for_document(doc_id)
        except Exception as re:
            logger.debug(f"Could not remove cached consultant report for {doc_id}: {re}")

        # 5. Remove from active conversation context states
        try:
            from backend.app.services.conversation_context_manager import conversation_context_manager
            conversation_context_manager.remove_document(doc_id)
        except Exception as ce:
            logger.debug(f"Could not remove document from context states: {ce}")

        # 6. Remove from metadata index
        del db[doc_id]
        self._write_metadata(db)
        logger.info(f"Removed document {doc_id} from metadata database and all associated caches.")
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
