"""
Brainy Centralized User File Management Service
================================================
Handles secure validation, Google Drive storage, Supabase metadata persistence,
and authorized retrieval for multimodal image intelligence and attachments.
"""

import os
import io
import re
import uuid
import json
import hashlib
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List

from PIL import Image
from pdf_studio.google_drive import (
    drive_storage,
    cipher,
    GoogleDriveError,
    GoogleDriveCompliancePause,
    GoogleDriveAuthError,
)

logger = logging.getLogger("file_service")

# Storage directory for local fallback vault in offline/dev environments
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "files_vault")
os.makedirs(DATA_DIR, exist_ok=True)

# In-memory file metadata store for fast lookups and dev mode
_FILES_STORE: Dict[str, Dict[str, Any]] = {}
_FILES_LOCK = threading.Lock()

MAX_IMAGE_SIZE_BYTES = 3 * 1024 * 1024  # 3 MB strict limit


class FileSecurityError(Exception):
    """Raised for unauthorized access, IDOR attempts, or security violations."""


class FileValidationError(Exception):
    """Raised for invalid MIME type, oversized file, or corrupted image data."""


class InvalidImageError(FileValidationError):
    """Raised specifically when an image has invalid format, corrupted bytes, or spoofed header."""


class FileTooLargeError(FileValidationError):
    """Raised specifically when a file exceeds size limits."""


class FileNotFoundError(FileValidationError, KeyError):
    """Raised when a requested file record does not exist or has been deleted."""


def validate_image_file(file_bytes: bytes, filename: str, max_size_bytes: int = MAX_IMAGE_SIZE_BYTES) -> Dict[str, Any]:
    """
    Validates image file size, magic bytes signature, MIME type, and internal integrity.
    Rejects malformed, unsupported, or oversized files.
    Returns metadata dict: {clean_name, mime_type, size, width, height, checksum}.
    """
    if not file_bytes:
        raise FileValidationError("Uploaded file is empty.")

    size = len(file_bytes)
    if size > max_size_bytes:
        raise FileTooLargeError(
            f"Image size exceeds the 3 MB limit ({size / (1024 * 1024):.2f} MB). Please upload an image under 3 MB."
        )

    # Magic bytes signature validation
    detected_mime = None
    if file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        detected_mime = "image/png"
    elif file_bytes.startswith(b"\xff\xd8\xff"):
        detected_mime = "image/jpeg"
    elif file_bytes.startswith(b"RIFF") and len(file_bytes) >= 12 and file_bytes[8:12] == b"WEBP":
        detected_mime = "image/webp"

    if not detected_mime:
        raise InvalidImageError(
            "Unsupported or invalid image file signature. Only PNG, JPEG, and WebP formats are supported."
        )

    # Image readability & dimension verification via Pillow
    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            img.verify()
            width, height = img.size
    except Exception as e:
        logger.warning("Image verification failed: %s", e)
        raise InvalidImageError("Corrupted or malformed image file. Could not be decoded.")

    if width <= 0 or height <= 0:
        raise InvalidImageError("Invalid image dimensions.")

    # Sanitize filename
    raw_name = os.path.basename(filename or "image")
    clean_name = re.sub(r"[^\w\.\-\s]", "_", raw_name).strip()
    ext = os.path.splitext(clean_name)[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        default_ext = ".png" if detected_mime == "image/png" else (".webp" if detected_mime == "image/webp" else ".jpg")
        clean_name = f"{clean_name}{default_ext}"

    checksum = hashlib.sha256(file_bytes).hexdigest()

    return {
        "clean_filename": clean_name,
        "mime_type": detected_mime,
        "file_size": size,
        "image_width": width,
        "image_height": height,
        "checksum": checksum,
    }


class FileService:
    """
    Production-grade user file management service with Google Drive central storage
    and Supabase metadata persistence.
    """

    def __init__(self, supabase_request_fn=None):
        self._sb_req = supabase_request_fn

    def set_supabase_requester(self, sb_req_fn):
        self._sb_req = sb_req_fn

    def _get_local_vault_path(self, user_id: Any, file_id: str) -> str:
        user_dir = os.path.join(DATA_DIR, str(user_id))
        os.makedirs(user_dir, exist_ok=True)
        return os.path.join(user_dir, f"{file_id}.bin")

    def _save_local_vault(self, user_id: Any, file_id: str, file_bytes: bytes):
        """Encrypted local disk vault fallback for offline dev or sandbox mode."""
        vault_path = self._get_local_vault_path(user_id, file_id)
        # Encrypt with dedicated AES-256-GCM cipher
        enc_payload = cipher.encrypt(file_bytes.hex())
        with open(vault_path, "w", encoding="utf-8") as f:
            f.write(enc_payload)

    def _read_local_vault(self, user_id: Any, file_id: str) -> bytes:
        vault_path = self._get_local_vault_path(user_id, file_id)
        if not os.path.exists(vault_path):
            raise FileNotFoundError("File data is not found in local vault.")
        with open(vault_path, "r", encoding="utf-8") as f:
            enc_payload = f.read()
        hex_data = cipher.decrypt(enc_payload)
        return bytes.fromhex(hex_data)

    def _delete_local_vault(self, user_id: Any, file_id: str):
        vault_path = self._get_local_vault_path(user_id, file_id)
        if os.path.exists(vault_path):
            try:
                os.remove(vault_path)
            except Exception as e:
                logger.warning("Could not delete local vault file %s: %s", vault_path, e)

    def upload_image(
        self,
        user_id: Any,
        filename: str,
        file_bytes: bytes,
        source_chat_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Uploads and processes an image file:
        1. Validates magic bytes, size, and dimensions.
        2. Uploads privately to Google Drive under Brainy/Users/{user}/Images/{year}/{month}/.
        3. Persists metadata record in Supabase user_files.
        4. Returns safe attachment reference.
        """
        if not user_id:
            raise FileSecurityError("Authentication required for image upload.")

        meta = validate_image_file(file_bytes, filename)
        file_id = str(uuid.uuid4())
        clean_filename = meta["clean_filename"]
        storage_filename = f"{file_id}_{clean_filename}"
        mime_type = meta["mime_type"]
        file_size = meta["file_size"]
        checksum = meta["checksum"]
        width = meta["image_width"]
        height = meta["image_height"]

        now_iso = datetime.now(timezone.utc).isoformat()
        drive_file_id = None
        drive_folder_id = None
        upload_status = "ready"

        # Attempt Google Drive centralized upload
        try:
            drive_res = drive_storage.upload_file(
                user_id=user_id,
                filename=clean_filename,
                file_bytes=file_bytes,
                mime_type=mime_type,
                file_id=file_id,
                file_type="image",
            )
            drive_file_id = drive_res.get("drive_file_id")
            drive_folder_id = drive_res.get("drive_folder_id")
            logger.info("Image uploaded to Google Drive file_id=%s drive_id=%s", file_id, drive_file_id)
        except GoogleDriveCompliancePause as ce:
            logger.info("Google Drive compliance pause active; saving to encrypted local vault: %s", ce)
            self._save_local_vault(user_id, file_id, file_bytes)
        except GoogleDriveAuthError as ae:
            logger.info("Google Drive unconfigured or not connected; saving to local vault: %s", ae)
            self._save_local_vault(user_id, file_id, file_bytes)
        except Exception as e:
            logger.warning("Google Drive upload error; saving to local vault fallback: %s", e)
            self._save_local_vault(user_id, file_id, file_bytes)

        file_record = {
            "id": file_id,
            "user_id": int(user_id) if str(user_id).isdigit() else str(user_id),
            "original_filename": clean_filename,
            "storage_filename": storage_filename,
            "mime_type": mime_type,
            "file_size": file_size,
            "file_type": "image",
            "drive_file_id": drive_file_id,
            "drive_folder_id": drive_folder_id,
            "checksum": checksum,
            "image_width": width,
            "image_height": height,
            "upload_status": upload_status,
            "source_chat_id": source_chat_id,
            "created_at": now_iso,
            "updated_at": now_iso,
            "deleted_at": None,
        }

        # 1. Store in memory
        with _FILES_LOCK:
            _FILES_STORE[file_id] = file_record

        # 2. Persist in Supabase user_files
        if self._sb_req:
            try:
                self._sb_req("POST", "user_files", json_body=file_record)
            except Exception as se:
                logger.warning("Failed to persist file metadata to Supabase user_files: %s", se)

        return {
            "id": file_id,
            "file_id": file_id,
            "original_filename": clean_filename,
            "mime_type": mime_type,
            "file_size": file_size,
            "image_width": width,
            "image_height": height,
            "checksum": checksum,
            "drive_file_id": drive_file_id,
            "preview_url": f"/api/files/{file_id}/preview",
        }

    def get_file_record(self, file_id: str, user_id: Any) -> Dict[str, Any]:
        """Retrieves and verifies ownership of a file metadata record."""
        record = None

        # 1. Check in-memory store
        with _FILES_LOCK:
            record = _FILES_STORE.get(file_id)

        # 2. Check Supabase user_files if not in memory
        if not record and self._sb_req:
            try:
                resp = self._sb_req(
                    "GET",
                    "user_files",
                    params=f"?id=eq.{file_id}&deleted_at=is.null&limit=1"
                )
                rows = resp.json() if hasattr(resp, "json") else []
                if isinstance(rows, list) and rows:
                    record = rows[0]
                    with _FILES_LOCK:
                        _FILES_STORE[file_id] = record
            except Exception as e:
                logger.debug("Failed querying Supabase user_files: %s", e)

        if not record:
            raise FileNotFoundError(f"File '{file_id}' not found.")

        # IDOR and ownership check
        if str(record.get("user_id")) != str(user_id):
            logger.warning("IDOR attempt: user %s attempted accessing file %s owned by %s",
                           user_id, file_id, record.get("user_id"))
            raise FileSecurityError("Access denied: You do not have permission to access this file.")

        return record

    def get_file_bytes(self, file_id: str, user_id: Any) -> Tuple[Dict[str, Any], bytes]:
        """
        Securely retrieves original file bytes for an authenticated owner.
        Retrieves from Google Drive if drive_file_id exists, or from local encrypted vault.
        Verifies checksum integrity.
        """
        record = self.get_file_record(file_id, user_id)
        drive_file_id = record.get("drive_file_id")

        file_bytes = None
        if drive_file_id:
            try:
                file_bytes = drive_storage.get_file_bytes(user_id, file_id, drive_file_id)
            except Exception as e:
                logger.warning("Failed retrieving file from Google Drive, checking vault: %s", e)

        if file_bytes is None:
            # Fall back to local encrypted vault
            file_bytes = self._read_local_vault(user_id, file_id)

        # Integrity verification
        expected_checksum = record.get("checksum")
        if expected_checksum:
            actual_checksum = hashlib.sha256(file_bytes).hexdigest()
            if actual_checksum != expected_checksum:
                raise FileValidationError("File integrity check failed (checksum mismatch).")

        return record, file_bytes

    def delete_user_file(self, file_id: str, user_id: Any) -> bool:
        """
        Securely deletes a file:
        1. Verifies ownership.
        2. Deletes from Google Drive.
        3. Soft-deletes or removes from Supabase user_files.
        4. Removes from local storage and memory.
        """
        record = self.get_file_record(file_id, user_id)
        drive_file_id = record.get("drive_file_id")

        if drive_file_id:
            try:
                drive_storage.delete_file(user_id, file_id, drive_file_id)
            except Exception as e:
                logger.warning("Failed deleting file from Google Drive: %s", e)

        # Delete from local disk vault
        self._delete_local_vault(user_id, file_id)

        # Mark deleted in memory
        with _FILES_LOCK:
            if file_id in _FILES_STORE:
                _FILES_STORE[file_id]["deleted_at"] = datetime.now(timezone.utc).isoformat()
                _FILES_STORE[file_id]["upload_status"] = "deleted"

        # Update in Supabase
        if self._sb_req:
            try:
                now_iso = datetime.now(timezone.utc).isoformat()
                self._sb_req(
                    "PATCH",
                    "user_files",
                    params=f"?id=eq.{file_id}&user_id=eq.{user_id}",
                    json_body={"deleted_at": now_iso, "upload_status": "deleted"}
                )
            except Exception as se:
                logger.warning("Failed to update user_files deletion in Supabase: %s", se)

        return True


# Global singleton instance
file_service = FileService()


def save_file(file_bytes: bytes, filename: str, mime_type: str = "image/png", user_id: Any = None) -> Dict[str, Any]:
    return file_service.upload_image(user_id=user_id, filename=filename, file_bytes=file_bytes)


def get_file(file_id: str, user_id: Any) -> Tuple[Dict[str, Any], bytes]:
    return file_service.get_file_bytes(file_id=file_id, user_id=user_id)


def delete_file(file_id: str, user_id: Any) -> bool:
    return file_service.delete_user_file(file_id=file_id, user_id=user_id)
