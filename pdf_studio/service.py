"""
BrainyAi PDF Study Studio - Document Lifecycle & Academic Services
Provides durable Supabase Storage & PostgreSQL persistence, page-aware text indexing,
bounded hierarchical note synthesis, grounded document Q&A, strictly validated 4-option quizzes,
interactive flashcards, and robust progress tracking.
Zero AI API calls for text extraction or OCR.
"""

import os
import re
import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

import requests

from ai_routing.router import router
from ai_routing.tasks import TaskType, ResponseDepth
from ai_routing.prompts import prompt_registry, Platform
from pdf_studio.extractor import extract_pdf_pages, PageExtraction
from pdf_studio.chunker import chunk_document_pages, sample_pages_evenly

logger = logging.getLogger("pdf_service")

# ── IN-MEMORY CACHE & LOCAL FALLBACK FOR DEV / OFFLINE ENVIRONMENTS ──
_DOCUMENTS_STORE: Dict[str, Dict[str, Any]] = {}
_PAGES_STORE: Dict[str, List[Dict[str, Any]]] = {}
_NOTES_STORE: Dict[str, List[Dict[str, Any]]] = {}
_QUIZZES_STORE: Dict[str, List[Dict[str, Any]]] = {}
_ATTEMPTS_STORE: Dict[str, List[Dict[str, Any]]] = {}
_FLASHCARDS_STORE: Dict[str, List[Dict[str, Any]]] = {}
_PROGRESS_STORE: Dict[str, Dict[str, Any]] = {}

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "documents")
os.makedirs(DATA_DIR, exist_ok=True)


class PDFSecurityError(Exception):
    """Raised for unauthorized access or security violations."""


class PDFValidationError(Exception):
    """Raised for invalid, oversized, or malformed PDF documents."""


class PDFNotFoundError(PDFValidationError, KeyError):
    """Raised when a document, quiz, or note is not found."""


def validate_pdf_file(file_bytes: bytes, filename: str, max_size_mb: int = 25) -> Tuple[str, int]:
    """
    Validates PDF file signature, extension, and file size.
    """
    if not filename or not filename.lower().endswith(".pdf"):
        raise PDFValidationError("Invalid document format: Only .pdf files are supported.")

    if not file_bytes or not file_bytes.startswith(b"%PDF-"):
        raise PDFValidationError("Invalid file signature: The uploaded file is not a valid PDF document.")

    size = len(file_bytes)
    if size > max_size_mb * 1024 * 1024:
        raise PDFValidationError(f"File size exceeds limit: {size / (1024*1024):.1f}MB (Max allowed: {max_size_mb}MB).")

    # Sanitize filename
    clean_name = re.sub(r"[^\w\.\-\s]", "_", os.path.basename(filename)).strip()
    if not clean_name or clean_name == ".pdf":
        clean_name = "document.pdf"
    return clean_name, size


class PDFStudyService:
    def __init__(
        self,
        supabase_request_fn=None,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None
    ):
        self._sb_req = supabase_request_fn
        self._supabase_url = (supabase_url or os.getenv("SUPABASE_URL") or "").rstrip("/")
        self._supabase_key = supabase_key or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY") or ""

    def set_supabase_requester(self, sb_req_fn, url: Optional[str] = None, key: Optional[str] = None):
        """Allows dynamic injection of Supabase client/helpers."""
        self._sb_req = sb_req_fn
        if url:
            self._supabase_url = url.rstrip("/")
        if key:
            self._supabase_key = key

    def _is_supabase_available(self) -> bool:
        return bool(self._sb_req and self._supabase_url and self._supabase_key)

    def _sb_storage_headers(self, content_type: str = "application/pdf") -> dict:
        headers = {
            "apikey": self._supabase_key,
            "Content-Type": content_type,
            "x-upsert": "true"
        }
        if not self._supabase_key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self._supabase_key}"
        return headers

    def _upload_to_supabase_storage(self, user_id: int, doc_id: str, file_bytes: bytes) -> Optional[str]:
        """
        Uploads original PDF to private Supabase Storage bucket 'study-pdfs' under `<user_id>/<doc_id>/original.pdf`.
        """
        if not (self._supabase_url and self._supabase_key):
            return None

        storage_path = f"{user_id}/{doc_id}/original.pdf"
        url = f"{self._supabase_url}/storage/v1/object/study-pdfs/{storage_path}"
        headers = self._sb_storage_headers("application/pdf")

        try:
            resp = requests.post(url, headers=headers, data=file_bytes, timeout=15)
            if resp.status_code in (200, 201):
                logger.info("Uploaded original PDF to Supabase Storage: %s", storage_path)
                return storage_path
            else:
                logger.warning("Supabase Storage upload returned status %d: %s", resp.status_code, resp.text)
                return None
        except Exception as e:
            logger.warning("Failed to upload PDF to Supabase Storage: %s", e)
            return None

    def _delete_from_supabase_storage(self, storage_path: str):
        """Removes PDF object from Supabase Storage."""
        if not (self._supabase_url and self._supabase_key and storage_path):
            return

        url = f"{self._supabase_url}/storage/v1/object/study-pdfs/{storage_path}"
        headers = self._sb_storage_headers("application/json")
        try:
            requests.delete(url, headers=headers, timeout=8)
            logger.info("Deleted PDF from Supabase Storage: %s", storage_path)
        except Exception as e:
            logger.warning("Failed to delete PDF from Supabase Storage: %s", e)

    def _persist_file_locally(self, user_id: int, doc_id: str, file_bytes: bytes) -> str:
        """Stores physical PDF securely in a private user-isolated directory as local backup/cache."""
        user_folder = os.path.join(DATA_DIR, str(user_id))
        os.makedirs(user_folder, exist_ok=True)
        file_path = os.path.join(user_folder, f"{doc_id}.pdf")
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        return file_path

    # ── DOCUMENT INGESTION ──

    def upload_and_process_pdf(
        self,
        user_id: int,
        filename: str,
        file_bytes: bytes,
        max_pages: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Validates, persists, extracts text page-by-page locally, and indexes metadata.
        Zero AI calls are made during ingestion.
        """
        clean_name, size = validate_pdf_file(file_bytes, filename)
        doc_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        # 1. Local disk persistence
        local_path = self._persist_file_locally(user_id, doc_id, file_bytes)

        # 2. Supabase Storage persistence (private study-pdfs bucket)
        storage_path = self._upload_to_supabase_storage(user_id, doc_id, file_bytes) or local_path

        # 3. Local text extraction using PyMuPDF (zero AI calls)
        try:
            page_extractions = extract_pdf_pages(file_bytes, max_pages=max_pages, perform_ocr_fallback=True)
        except Exception as e:
            logger.error("Extraction error on %s: %s", clean_name, e)
            raise PDFValidationError(f"Failed to extract text from PDF: {e}")

        total_pages = len(page_extractions)
        if total_pages == 0:
            raise PDFValidationError("PDF document does not contain any readable pages.")

        # Determine overall OCR usage
        ocr_pages_count = sum(1 for p in page_extractions if p.extraction_method == "local_ocr")
        ocr_status = "local_ocr_used" if ocr_pages_count > 0 else "native_text"

        # Format processed pages
        processed_pages = []
        for p in page_extractions:
            processed_pages.append({
                "document_id": doc_id,
                "user_id": user_id,
                "page_number": p.page_number,
                "text_content": p.text,
                "token_count": p.token_count,
                "has_images": p.has_images,
                "headings": p.headings,
                "extraction_method": p.extraction_method,
                "extraction_status": p.extraction_status,
                "created_at": created_at
            })

        doc_record = {
            "id": doc_id,
            "user_id": user_id,
            "filename": clean_name,
            "file_size": size,
            "page_count": total_pages,
            "storage_path": storage_path,
            "processing_status": "ready",
            "error_message": None,
            "ocr_status": ocr_status,
            "created_at": created_at,
            "updated_at": created_at
        }

        # 4. Durable persistence in Supabase PostgreSQL (if available)
        if self._is_supabase_available():
            try:
                # Insert document
                self._sb_req("POST", "user_documents", json_body=doc_record)
                # Insert pages
                for page_row in processed_pages:
                    self._sb_req("POST", "document_pages", json_body=page_row)
                # Initialize progress
                prog_row = {
                    "user_id": user_id,
                    "document_id": doc_id,
                    "notes_generated": False,
                    "quizzes_taken": 0,
                    "best_quiz_score": 0,
                    "cards_reviewed": 0,
                    "last_studied_at": created_at
                }
                self._sb_req("POST", "document_study_progress", json_body=prog_row)
            except Exception as sbe:
                logger.warning("Supabase DB persistence error during upload (falling back to memory): %s", sbe)

        # In-memory store update (authoritative for dev / fast cache for production)
        _DOCUMENTS_STORE[doc_id] = doc_record
        _PAGES_STORE[doc_id] = processed_pages
        prog_key = f"{user_id}_{doc_id}"
        _PROGRESS_STORE[prog_key] = {
            "user_id": user_id,
            "document_id": doc_id,
            "notes_generated": False,
            "quizzes_taken": 0,
            "best_quiz_score": 0,
            "cards_reviewed": 0,
            "last_studied_at": created_at
        }

        logger.info("PDF ingested doc_id=%s user_id=%s pages=%d ocr_status=%s", doc_id, user_id, total_pages, ocr_status)
        return doc_record

    # ── DOCUMENT RETRIEVAL & DELETION ──

    def get_user_documents(self, user_id: int) -> List[Dict[str, Any]]:
        """Lists all documents belonging to the authenticated user."""
        if self._is_supabase_available():
            try:
                resp = self._sb_req("GET", "user_documents", params=f"?user_id=eq.{user_id}&order=created_at.desc")
                db_docs = resp.json() if hasattr(resp, "json") else []
                if isinstance(db_docs, list) and db_docs:
                    # Update local cache
                    for d in db_docs:
                        _DOCUMENTS_STORE[d["id"]] = d
                    return db_docs
            except Exception as e:
                logger.warning("Failed to fetch user documents from Supabase: %s", e)

        # In-memory fallback
        docs = [d for d in _DOCUMENTS_STORE.values() if d.get("user_id") == user_id]
        return sorted(docs, key=lambda x: x.get("created_at", ""), reverse=True)

    def get_document(self, doc_id: str, user_id: int) -> Dict[str, Any]:
        """Retrieves single document metadata and enforces user ownership."""
        doc = None
        if self._is_supabase_available():
            try:
                resp = self._sb_req("GET", "user_documents", params=f"?id=eq.{doc_id}&limit=1")
                rows = resp.json() if hasattr(resp, "json") else []
                if isinstance(rows, list) and rows:
                    doc = rows[0]
                    _DOCUMENTS_STORE[doc_id] = doc
            except Exception as e:
                logger.warning("Failed to fetch document %s from Supabase: %s", doc_id, e)

        if not doc:
            doc = _DOCUMENTS_STORE.get(doc_id)

        if not doc:
            raise PDFNotFoundError("Document not found.")

        if doc.get("user_id") != user_id:
            raise PDFSecurityError("Access denied: You do not own this document.")

        return doc

    def delete_document(self, doc_id: str, user_id: int) -> bool:
        """Securely deletes document, files from Supabase Storage and all derived records."""
        doc = self.get_document(doc_id, user_id)

        # 1. Delete from Supabase Storage
        storage_path = doc.get("storage_path")
        if storage_path and not os.path.isabs(storage_path):
            self._delete_from_supabase_storage(storage_path)

        # 2. Delete local physical file if exists
        local_path = os.path.join(DATA_DIR, str(user_id), f"{doc_id}.pdf")
        if os.path.exists(local_path):
            try:
                os.remove(local_path)
            except Exception as e:
                logger.warning("Could not delete local file %s: %s", local_path, e)

        # 3. Delete from Supabase PostgreSQL (Foreign Keys ON DELETE CASCADE will clean up pages, notes, quizzes, flashcards, progress)
        if self._is_supabase_available():
            try:
                self._sb_req("DELETE", "user_documents", params=f"?id=eq.{doc_id}&user_id=eq.{user_id}")
            except Exception as e:
                logger.warning("Failed to delete document from Supabase DB: %s", e)

        # 4. Clean up in-memory caches
        _DOCUMENTS_STORE.pop(doc_id, None)
        _PAGES_STORE.pop(doc_id, None)
        _NOTES_STORE.pop(doc_id, None)
        _QUIZZES_STORE.pop(doc_id, None)
        _FLASHCARDS_STORE.pop(doc_id, None)
        prog_key = f"{user_id}_{doc_id}"
        _PROGRESS_STORE.pop(prog_key, None)

        logger.info("Deleted document doc_id=%s user_id=%s", doc_id, user_id)
        return True

    def get_document_pages(self, doc_id: str, user_id: int) -> List[Dict[str, Any]]:
        """Retrieves all indexed pages for a document."""
        self.get_document(doc_id, user_id)

        if self._is_supabase_available():
            try:
                resp = self._sb_req("GET", "document_pages", params=f"?document_id=eq.{doc_id}&order=page_number.asc")
                rows = resp.json() if hasattr(resp, "json") else []
                if isinstance(rows, list) and rows:
                    _PAGES_STORE[doc_id] = rows
                    return rows
            except Exception as e:
                logger.warning("Failed to fetch document pages from Supabase: %s", e)

        return _PAGES_STORE.get(doc_id, [])

    # ── STRUCTURED NOTE GENERATION (MULTI-STAGE & BOUNDED CHUNKING) ──

    def generate_notes(self, doc_id: str, user_id: int, depth: str = "balanced") -> Dict[str, Any]:
        """
        Synthesizes structured revision notes.
        Uses bounded chunking for long documents without arbitrary truncation.
        Grounded strictly in source text with [Page X] citations.
        """
        doc = self.get_document(doc_id, user_id)
        pages = self.get_document_pages(doc_id, user_id)

        if not pages:
            raise ValueError("Document has no extractable pages to generate notes from.")

        # Check if text is present
        has_text = any(bool(p.get("text_content", "").strip()) for p in pages)
        if not has_text:
            raise ValueError("Document has no extractable text to generate notes from.")

        sys_prompt = prompt_registry.get_template("pdf_notes_prompt.txt")
        res_depth = ResponseDepth.from_str(depth) if hasattr(ResponseDepth, "from_str") else ResponseDepth.BALANCED

        # For shorter documents (<= 15 pages): process directly with all pages
        if len(pages) <= 15:
            full_text = "\n\n".join(
                f"--- [Page {p['page_number']}] ---\n{p.get('text_content', '').strip()}"
                for p in pages if p.get("text_content", "").strip()
            )
            prompt = f"Document Title: {doc['filename']}\n\nDocument Contents:\n{full_text}"
            resp = router.generate(
                prompt=prompt,
                task=TaskType.NOTE_GENERATION,
                depth=res_depth,
                system_prompt=sys_prompt
            )
            final_content = resp.text
        else:
            # Multi-stage chunking for long documents
            logger.info("Long document detected (%d pages); using bounded multi-stage summarization", len(pages))
            chunks = chunk_document_pages(pages, target_tokens_per_chunk=3500, overlap_pages=1)
            chunk_summaries = []

            for c in chunks:
                chunk_prompt = (
                    f"Document Title: {doc['filename']}\n"
                    f"Section: Pages {c.start_page} to {c.end_page}\n\n"
                    f"Extract key concepts, definitions, formulas, and workflows with [Page X] citations:\n"
                    f"{c.text}"
                )
                chunk_resp = router.generate(
                    prompt=chunk_prompt,
                    task=TaskType.NOTE_GENERATION,
                    depth=ResponseDepth.FAST,
                    system_prompt="Extract concise structured study notes with exact [Page X] citations."
                )
                chunk_summaries.append(
                    f"### Section: Pages {c.start_page}-{c.end_page}\n{chunk_resp.text.strip()}"
                )

            # Stage 2: Master synthesis into unified structured guide
            combined_chunks = "\n\n".join(chunk_summaries)
            consolidation_prompt = (
                f"Document Title: {doc['filename']} (Total Pages: {len(pages)})\n\n"
                f"Synthesize the following section summaries into a comprehensive Master Study Guide "
                f"following all required Markdown sections and preserving [Page X] citations:\n\n"
                f"{combined_chunks}"
            )
            master_resp = router.generate(
                prompt=consolidation_prompt,
                task=TaskType.NOTE_GENERATION,
                depth=res_depth,
                system_prompt=sys_prompt
            )
            final_content = master_resp.text

        # Extract cited pages
        cited_pages = sorted(list(set(int(m) for m in re.findall(r"\[Page\s+(\d+)\]", final_content, re.IGNORECASE))))

        note_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        depth_label = depth.upper() if isinstance(depth, str) else "BALANCED"

        note_record = {
            "id": note_id,
            "document_id": doc_id,
            "user_id": user_id,
            "title": f"Study Notes: {doc['filename']}",
            "depth": depth_label,
            "content": final_content,
            "citations": cited_pages,
            "created_at": created_at
        }

        # Persist to Supabase if available
        if self._is_supabase_available():
            try:
                self._sb_req("POST", "document_notes", json_body=note_record)
                # Update progress in DB
                self._sb_req(
                    "PATCH",
                    "document_study_progress",
                    params=f"?user_id=eq.{user_id}&document_id=eq.{doc_id}",
                    json_body={"notes_generated": True, "last_studied_at": created_at}
                )
            except Exception as e:
                logger.warning("Failed to persist notes to Supabase: %s", e)

        # In-memory store
        _NOTES_STORE.setdefault(doc_id, []).append(note_record)
        prog_key = f"{user_id}_{doc_id}"
        if prog_key in _PROGRESS_STORE:
            _PROGRESS_STORE[prog_key]["notes_generated"] = True
            _PROGRESS_STORE[prog_key]["last_studied_at"] = created_at

        return note_record

    def get_notes(self, doc_id: str, user_id: int) -> List[Dict[str, Any]]:
        """Retrieves all generated notes for a document."""
        self.get_document(doc_id, user_id)

        if self._is_supabase_available():
            try:
                resp = self._sb_req("GET", "document_notes", params=f"?document_id=eq.{doc_id}&user_id=eq.{user_id}&order=created_at.desc")
                rows = resp.json() if hasattr(resp, "json") else []
                if isinstance(rows, list) and rows:
                    _NOTES_STORE[doc_id] = rows
                    return rows
            except Exception as e:
                logger.warning("Failed to fetch notes from Supabase: %s", e)

        notes = _NOTES_STORE.get(doc_id, [])
        return sorted(notes, key=lambda x: x.get("created_at", ""), reverse=True)

    # ── GROUNDED DOCUMENT Q&A ──

    def ask_document(self, doc_id: str, user_id: int, question: str, depth: Any = "balanced") -> Dict[str, Any]:
        """Source-grounded Document Q&A with exact page citation."""
        doc = self.get_document(doc_id, user_id)
        pages = self.get_document_pages(doc_id, user_id)

        q_clean = question.strip()
        if not q_clean:
            raise ValueError("Question cannot be empty.")

        # Keyword / token matching retrieval across pages
        q_tokens = set(re.findall(r"\w+", q_clean.lower()))
        scored_pages = []
        for p in pages:
            p_text = p.get("text_content", "")
            p_tokens = set(re.findall(r"\w+", p_text.lower()))
            overlap = len(q_tokens.intersection(p_tokens))
            scored_pages.append((overlap, p))

        scored_pages.sort(key=lambda x: x[0], reverse=True)
        top_pages = [p for _, p in scored_pages[:6]]
        top_pages.sort(key=lambda x: x["page_number"])

        excerpts = []
        matched_page_nums = []
        for p in top_pages:
            matched_page_nums.append(p["page_number"])
            excerpts.append(f"[PAGE {p['page_number']}]\n{p.get('text_content', '')[:1200]}")

        context_block = "\n\n".join(excerpts)
        sys_prompt = prompt_registry.get_template("pdf_qa_prompt.txt")

        user_prompt = f"Document: {doc['filename']}\n\nDocument Context:\n{context_block}\n\nQuestion: {q_clean}"

        res_depth = ResponseDepth.from_str(str(depth)) if hasattr(ResponseDepth, "from_str") else ResponseDepth.BALANCED
        resp = router.generate(
            prompt=user_prompt,
            task=TaskType.PDF_QUESTION_ANSWERING,
            depth=res_depth,
            system_prompt=sys_prompt
        )

        return {
            "answer": resp.text,
            "document_id": doc_id,
            "page_references": matched_page_nums,
            "citations": matched_page_nums,
            "model": resp.model,
            "provider": resp.provider
        }

    # ── STRICT 4-OPTION MCQ QUIZ GENERATION ──

    def generate_quiz(self, doc_id: str, user_id: int, num_questions: int = 5, depth: Any = "balanced") -> Dict[str, Any]:
        """
        Generates interactive multiple-choice quiz with strictly 4 distinct options per question.
        Evenly samples across long documents.
        """
        doc = self.get_document(doc_id, user_id)
        pages = self.get_document_pages(doc_id, user_id)

        # Sample pages evenly across the entire document
        sampled_pages = sample_pages_evenly(pages, max_pages=25)
        sample_text = "\n\n".join(
            f"[Page {p['page_number']}] {p.get('text_content','')[:900]}"
            for p in sampled_pages if p.get("text_content", "").strip()
        )

        if not sample_text:
            raise ValueError("Document contains no readable text to generate quiz questions.")

        sys_prompt = prompt_registry.get_template("pdf_quiz_prompt.txt")

        prompt = (
            f"Document: {doc['filename']}\n"
            f"Generate a {num_questions}-question multiple choice quiz from the following document text.\n"
            f"Every question MUST have exactly 4 distinct options, exactly 1 correct option index (0 to 3), "
            f"a helpful explanation, and the specific source page reference:\n\n{sample_text}"
        )

        quiz_data = router.generate_structured(
            prompt=prompt,
            system_prompt=sys_prompt,
            task=TaskType.QUIZ_GENERATION,
            max_tokens=3500
        )

        raw_questions = quiz_data.get("questions", [])
        validated_questions = []

        for q in raw_questions:
            q_text = str(q.get("question") or "").strip()
            opts = q.get("options") or []
            if not isinstance(opts, list) or len(opts) < 4:
                continue

            # Ensure exactly 4 options
            clean_opts = [str(o).strip() for o in opts[:4]]
            if len(set(clean_opts)) != 4 or any(len(o) == 0 for o in clean_opts):
                continue

            correct_idx = q.get("correct_index", 0)
            if not isinstance(correct_idx, int) or correct_idx < 0 or correct_idx > 3:
                correct_idx = 0

            expl = str(q.get("explanation") or "").strip() or "Correct option based on document text."
            page_ref = str(q.get("page_ref") or "Page 1").strip()

            validated_questions.append({
                "question": q_text,
                "options": clean_opts,
                "correct_index": correct_idx,
                "explanation": expl,
                "page_ref": page_ref
            })

        if not validated_questions:
            raise RuntimeError("Model failed to produce validated 4-option quiz questions. Please retry.")

        quiz_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        quiz_record = {
            "id": quiz_id,
            "document_id": doc_id,
            "user_id": user_id,
            "title": str(quiz_data.get("title") or f"Quiz: {doc['filename']}")[:100],
            "questions": validated_questions,
            "created_at": created_at
        }

        # Persist to Supabase if available
        if self._is_supabase_available():
            try:
                self._sb_req("POST", "document_quizzes", json_body=quiz_record)
            except Exception as e:
                logger.warning("Failed to persist quiz to Supabase: %s", e)

        _QUIZZES_STORE.setdefault(doc_id, []).append(quiz_record)
        return quiz_record

    def get_quizzes(self, doc_id: str, user_id: int) -> List[Dict[str, Any]]:
        """Retrieves all generated quizzes for the document."""
        self.get_document(doc_id, user_id)

        if self._is_supabase_available():
            try:
                resp = self._sb_req("GET", "document_quizzes", params=f"?document_id=eq.{doc_id}&user_id=eq.{user_id}&order=created_at.desc")
                rows = resp.json() if hasattr(resp, "json") else []
                if isinstance(rows, list) and rows:
                    _QUIZZES_STORE[doc_id] = rows
                    return rows
            except Exception as e:
                logger.warning("Failed to fetch quizzes from Supabase: %s", e)

        quizzes = _QUIZZES_STORE.get(doc_id, [])
        return sorted(quizzes, key=lambda x: x.get("created_at", ""), reverse=True)

    def submit_quiz_attempt(
        self,
        quiz_id: str,
        user_id: int,
        user_answers: Optional[Dict[str, int] | List[int]] = None,
        selected_indices: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Evaluates user answers, computes score, and updates study progress."""
        if selected_indices is not None and user_answers is None:
            user_answers = {str(i): idx for i, idx in enumerate(selected_indices)}
        elif isinstance(user_answers, list):
            user_answers = {str(i): idx for i, idx in enumerate(user_answers)}
        elif user_answers is None:
            user_answers = {}

        # Find quiz in Supabase or memory
        target_quiz = None
        if self._is_supabase_available():
            try:
                resp = self._sb_req("GET", "document_quizzes", params=f"?id=eq.{quiz_id}&limit=1")
                rows = resp.json() if hasattr(resp, "json") else []
                if isinstance(rows, list) and rows:
                    target_quiz = rows[0]
            except Exception as e:
                logger.warning("Failed to fetch quiz %s from Supabase: %s", quiz_id, e)

        if not target_quiz:
            for q_list in _QUIZZES_STORE.values():
                for q in q_list:
                    if q["id"] == quiz_id:
                        target_quiz = q
                        break
                if target_quiz:
                    break

        if not target_quiz:
            raise PDFNotFoundError("Quiz not found.")

        doc_id = target_quiz["document_id"]
        self.get_document(doc_id, user_id)

        questions = target_quiz["questions"]
        total = len(questions)
        correct_count = 0
        details = []

        for idx, q in enumerate(questions):
            ans = user_answers.get(str(idx))
            is_correct = (ans == q["correct_index"])
            if is_correct:
                correct_count += 1
            details.append({
                "question_index": idx,
                "selected_option": ans,
                "correct_option": q["correct_index"],
                "is_correct": is_correct,
                "explanation": q["explanation"],
                "page_ref": q["page_ref"]
            })

        attempt_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        pct = round((correct_count / total * 100) if total > 0 else 0.0, 2)
        attempt_record = {
            "id": attempt_id,
            "quiz_id": quiz_id,
            "user_id": user_id,
            "score": correct_count,
            "total": total,
            "percentage": pct,
            "details": details,
            "feedback": details,
            "created_at": created_at
        }

        # Persist attempt to Supabase
        if self._is_supabase_available():
            try:
                self._sb_req("POST", "document_quiz_attempts", json_body=attempt_record)
            except Exception as e:
                logger.warning("Failed to persist quiz attempt to Supabase: %s", e)

        _ATTEMPTS_STORE.setdefault(quiz_id, []).append(attempt_record)

        # Update study progress
        prog_key = f"{user_id}_{doc_id}"
        if prog_key in _PROGRESS_STORE:
            p = _PROGRESS_STORE[prog_key]
            p["quizzes_taken"] += 1
            p["best_quiz_score"] = max(p.get("best_quiz_score", 0), correct_count)
            p["last_studied_at"] = created_at

        if self._is_supabase_available():
            try:
                cur_prog = self.get_study_progress(doc_id, user_id)
                new_quizzes = cur_prog.get("quizzes_taken", 0) + 1
                new_best = max(cur_prog.get("best_quiz_score", 0), correct_count)
                self._sb_req(
                    "PATCH",
                    "document_study_progress",
                    params=f"?user_id=eq.{user_id}&document_id=eq.{doc_id}",
                    json_body={
                        "quizzes_taken": new_quizzes,
                        "best_quiz_score": new_best,
                        "last_studied_at": created_at
                    }
                )
            except Exception as e:
                logger.warning("Failed to update progress in Supabase: %s", e)

        return attempt_record

    # ── FLASHCARDS GENERATION ──

    def generate_flashcards(self, doc_id: str, user_id: int, count: int = 8, depth: str = "balanced") -> Dict[str, Any]:
        """Generates study flashcards evenly sampled from document key concepts."""
        doc = self.get_document(doc_id, user_id)
        pages = self.get_document_pages(doc_id, user_id)

        # Sample pages evenly across document
        sampled_pages = sample_pages_evenly(pages, max_pages=20)
        sample_text = "\n\n".join(
            f"[Page {p['page_number']}] {p.get('text_content','')[:800]}"
            for p in sampled_pages if p.get("text_content", "").strip()
        )

        if not sample_text:
            raise ValueError("Document contains no readable text to generate flashcards.")

        sys_prompt = prompt_registry.get_template("pdf_flashcards_prompt.txt")

        prompt = (
            f"Document: {doc['filename']}\n"
            f"Create {count} distinct study flashcards from the text below.\n"
            f"Each card must contain front (term/concept/question), back (concise answer/definition), "
            f"page_ref (e.g. Page 1), and difficulty (Easy, Medium, or Hard):\n\n{sample_text}"
        )

        card_data = router.generate_structured(
            prompt=prompt,
            system_prompt=sys_prompt,
            task=TaskType.FLASHCARD_GENERATION,
            max_tokens=3000
        )

        raw_cards = card_data.get("cards", [])
        valid_cards = []
        for c in raw_cards:
            f_text = str(c.get("front") or "").strip()
            b_text = str(c.get("back") or "").strip()
            if f_text and b_text:
                valid_cards.append({
                    "front": f_text,
                    "back": b_text,
                    "page_ref": str(c.get("page_ref") or "Page 1"),
                    "difficulty": str(c.get("difficulty") or "Medium")
                })

        flash_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        flash_record = {
            "id": flash_id,
            "document_id": doc_id,
            "user_id": user_id,
            "cards": valid_cards,
            "created_at": created_at
        }

        # Persist to Supabase
        if self._is_supabase_available():
            try:
                self._sb_req("POST", "document_flashcards", json_body=flash_record)
            except Exception as e:
                logger.warning("Failed to persist flashcards to Supabase: %s", e)

        _FLASHCARDS_STORE.setdefault(doc_id, []).append(flash_record)

        # Update progress
        prog_key = f"{user_id}_{doc_id}"
        if prog_key in _PROGRESS_STORE:
            _PROGRESS_STORE[prog_key]["cards_reviewed"] += len(valid_cards)
            _PROGRESS_STORE[prog_key]["last_studied_at"] = created_at

        return flash_record

    def get_flashcards(self, doc_id: str, user_id: int) -> List[Dict[str, Any]]:
        """Retrieves all flashcard decks generated for the document."""
        self.get_document(doc_id, user_id)

        if self._is_supabase_available():
            try:
                resp = self._sb_req("GET", "document_flashcards", params=f"?document_id=eq.{doc_id}&user_id=eq.{user_id}&order=created_at.desc")
                rows = resp.json() if hasattr(resp, "json") else []
                if isinstance(rows, list) and rows:
                    _FLASHCARDS_STORE[doc_id] = rows
                    return rows
            except Exception as e:
                logger.warning("Failed to fetch flashcards from Supabase: %s", e)

        cards = _FLASHCARDS_STORE.get(doc_id, [])
        return sorted(cards, key=lambda x: x.get("created_at", ""), reverse=True)

    # ── PROGRESS TRACKING ──

    def get_study_progress(self, doc_id: str, user_id: int) -> Dict[str, Any]:
        """Retrieves user study progress for the document."""
        self.get_document(doc_id, user_id)

        if self._is_supabase_available():
            try:
                resp = self._sb_req("GET", "document_study_progress", params=f"?user_id=eq.{user_id}&document_id=eq.{doc_id}&limit=1")
                rows = resp.json() if hasattr(resp, "json") else []
                if isinstance(rows, list) and rows:
                    return rows[0]
            except Exception as e:
                logger.warning("Failed to fetch progress from Supabase: %s", e)

        prog_key = f"{user_id}_{doc_id}"
        return _PROGRESS_STORE.get(prog_key, {
            "user_id": user_id,
            "document_id": doc_id,
            "notes_generated": False,
            "quizzes_taken": 0,
            "best_quiz_score": 0,
            "cards_reviewed": 0,
            "last_studied_at": datetime.now(timezone.utc).isoformat()
        })


# Global singleton service
pdf_service = PDFStudyService()
