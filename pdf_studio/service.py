"""
BrainyAi PDF Study Studio - Document Lifecycle & Academic Services
Provides private document storage, page-aware text indexing, note synthesis,
grounded document Q&A, strictly validated 4-option quizzes, flashcards, and progress tracking.
"""

import os
import re
import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from ai_routing.router import router
from ai_routing.tasks import TaskType, ResponseDepth
from pdf_studio.extractor import extract_pdf_pages, PageExtraction
from pdf_studio.gemini_doc import ocr_scanned_page

logger = logging.getLogger("pdf_service")

# ── IN-MEMORY / LOCAL STORAGE FOR SEAMLESS TESTING & DEV ──
_DOCUMENTS_STORE: Dict[str, Dict[str, Any]] = {}
_PAGES_STORE: Dict[str, List[Dict[str, Any]]] = {}  # doc_id -> list of pages
_NOTES_STORE: Dict[str, List[Dict[str, Any]]] = {}  # doc_id -> list of notes
_QUIZZES_STORE: Dict[str, List[Dict[str, Any]]] = {}  # doc_id -> list of quizzes
_ATTEMPTS_STORE: Dict[str, List[Dict[str, Any]]] = {}  # quiz_id -> list of attempts
_FLASHCARDS_STORE: Dict[str, List[Dict[str, Any]]] = {}  # doc_id -> list of flashcards
_PROGRESS_STORE: Dict[str, Dict[str, Any]] = {}  # f"{user_id}_{doc_id}" -> progress

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "documents")
os.makedirs(DATA_DIR, exist_ok=True)

class PDFSecurityError(Exception):
    """Raised for unauthorized access or security violations."""

class PDFValidationError(Exception):
    """Raised for invalid, oversized, or malformed PDF documents."""

class PDFNotFoundError(PDFValidationError, KeyError):
    """Raised when a document or quiz is not found."""

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
    return clean_name, size

class PDFStudyService:
    def __init__(self, supabase_request_fn=None):
        self._sb_req = supabase_request_fn

    def _persist_file_bytes(self, user_id: int, doc_id: str, file_bytes: bytes) -> str:
        """Stores physical PDF securely in a private user-isolated directory."""
        user_folder = os.path.join(DATA_DIR, str(user_id))
        os.makedirs(user_folder, exist_ok=True)
        file_path = os.path.join(user_folder, f"{doc_id}.pdf")
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        return file_path

    def upload_and_process_pdf(
        self,
        user_id: int,
        filename: str,
        file_bytes: bytes,
        max_pages: int = 100
    ) -> Dict[str, Any]:
        """
        Validates, saves, extracts page text, and creates document record.
        """
        clean_name, size = validate_pdf_file(file_bytes, filename)
        doc_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        # Save to disk
        local_path = self._persist_file_bytes(user_id, doc_id, file_bytes)

        # Extract pages with PyMuPDF
        try:
            page_extractions = extract_pdf_pages(file_bytes, max_pages=max_pages)
        except Exception as e:
            logger.error("Extraction error on %s: %s", clean_name, e)
            raise PDFValidationError(f"Failed to extract text from PDF: {e}")

        total_pages = len(page_extractions)
        if total_pages == 0:
            raise PDFValidationError("PDF document does not contain any readable pages.")

        # Process scanned pages if needed
        processed_pages = []
        for p in page_extractions:
            text_content = p.text
            if p.is_scanned and p.image_bytes:
                ocr_text = ocr_scanned_page(p.image_bytes, p.page_number)
                if ocr_text:
                    text_content = ocr_text

            processed_pages.append({
                "document_id": doc_id,
                "page_number": p.page_number,
                "text_content": text_content,
                "token_count": p.token_count,
                "has_images": p.has_images,
                "headings": p.headings
            })

        doc_record = {
            "id": doc_id,
            "user_id": user_id,
            "filename": clean_name,
            "file_size": size,
            "page_count": total_pages,
            "storage_path": local_path,
            "processing_status": "ready",
            "error_message": None,
            "created_at": created_at,
            "updated_at": created_at
        }

        # Store in Supabase / In-Memory
        _DOCUMENTS_STORE[doc_id] = doc_record
        _PAGES_STORE[doc_id] = processed_pages

        # Initialize progress record
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

        logger.info("PDF uploaded doc_id=%s user_id=%s pages=%d size_bytes=%d", doc_id, user_id, total_pages, size)
        return doc_record

    def get_user_documents(self, user_id: int) -> List[Dict[str, Any]]:
        docs = [d for d in _DOCUMENTS_STORE.values() if d.get("user_id") == user_id]
        return sorted(docs, key=lambda x: x.get("created_at", ""), reverse=True)

    def get_document(self, doc_id: str, user_id: int) -> Dict[str, Any]:
        doc = _DOCUMENTS_STORE.get(doc_id)
        if not doc:
            raise PDFNotFoundError("Document not found.")
        if doc.get("user_id") != user_id:
            raise PDFSecurityError("Access denied: You do not own this document.")
        return doc

    def delete_document(self, doc_id: str, user_id: int) -> bool:
        doc = self.get_document(doc_id, user_id)
        # Remove physical file
        path = doc.get("storage_path")
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                logger.warning("Could not delete file %s: %s", path, e)

        _DOCUMENTS_STORE.pop(doc_id, None)
        _PAGES_STORE.pop(doc_id, None)
        _NOTES_STORE.pop(doc_id, None)
        _QUIZZES_STORE.pop(doc_id, None)
        _FLASHCARDS_STORE.pop(doc_id, None)
        prog_key = f"{user_id}_{doc_id}"
        _PROGRESS_STORE.pop(prog_key, None)
        return True

    def get_document_pages(self, doc_id: str, user_id: int) -> List[Dict[str, Any]]:
        self.get_document(doc_id, user_id)
        return _PAGES_STORE.get(doc_id, [])

    def generate_notes(self, doc_id: str, user_id: int, depth: str = "balanced") -> Dict[str, Any]:
        """
        Synthesizes structured, source-grounded study notes with page citations.
        """
        doc = self.get_document(doc_id, user_id)
        pages = self.get_document_pages(doc_id, user_id)

        # Compile page text excerpts with page provenance
        page_excerpts = []
        for p in pages[:40]:  # Up to 40 pages for notes synthesis
            txt = p.get("text_content", "").strip()
            if txt:
                page_excerpts.append(f"--- PAGE {p['page_number']} ---\n{txt}")

        combined_text = "\n\n".join(page_excerpts)
        if not combined_text:
            raise ValueError("Document has no extractable text to generate notes from.")

        sys_prompt = (
            "You are BrainyAi Study Studio. Generate comprehensive, highly structured academic revision notes "
            "strictly grounded in the provided document. Cite exact page numbers (e.g. [Page 2], [Pages 4-5]) for important facts.\n"
            "Format your notes using the following exact markdown sections:\n"
            "## 📌 Executive Overview\n"
            "## 📖 Chapter & Topic Breakdown\n"
            "## 💡 Key Definitions & Core Terminology\n"
            "## 🧮 Important Formulas & Mathematical Rules (use LaTeX $...$ or $$...$$)\n"
            "## ⚖️ Critical Comparisons & Contrasts\n"
            "## 🎯 High-Yield Revision Takeaways\n\n"
            "Ground all claims in the text. If a section has no relevant content in the document, state 'None in this document'."
        )

        prompt = f"Document Title: {doc['filename']}\n\nDocument Contents:\n{combined_text[:35000]}"

        res_depth = ResponseDepth.from_str(depth)
        resp = router.generate(
            prompt=prompt,
            task=TaskType.NOTE_GENERATION,
            depth=res_depth,
            system_prompt=sys_prompt
        )

        note_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        cited_pages = sorted(list(set(int(m) for m in re.findall(r"\[Page\s+(\d+)\]", resp.text, re.IGNORECASE))))
        note_record = {
            "id": note_id,
            "document_id": doc_id,
            "user_id": user_id,
            "depth": depth,
            "content": resp.text,
            "citations": cited_pages,
            "created_at": created_at
        }

        _NOTES_STORE.setdefault(doc_id, []).append(note_record)

        # Update progress
        prog_key = f"{user_id}_{doc_id}"
        if prog_key in _PROGRESS_STORE:
            _PROGRESS_STORE[prog_key]["notes_generated"] = True
            _PROGRESS_STORE[prog_key]["last_studied_at"] = created_at

        return note_record

    def get_notes(self, doc_id: str, user_id: int) -> List[Dict[str, Any]]:
        self.get_document(doc_id, user_id)
        notes = _NOTES_STORE.get(doc_id, [])
        return sorted(notes, key=lambda x: x.get("created_at", ""), reverse=True)

    def ask_document(self, doc_id: str, user_id: int, question: str) -> Dict[str, Any]:
        """
        Source-grounded Document Q&A with exact page citation.
        """
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
        top_pages = [p for _, p in scored_pages[:5]]
        top_pages.sort(key=lambda x: x["page_number"])

        excerpts = []
        matched_page_nums = []
        for p in top_pages:
            matched_page_nums.append(p["page_number"])
            excerpts.append(f"[PAGE {p['page_number']}]\n{p.get('text_content', '')[:1200]}")

        context_block = "\n\n".join(excerpts)
        sys_prompt = (
            "You are BrainyAi Document Assistant. Answer the student's question based strictly on the provided document excerpts. "
            "Always include citations to the source page (e.g., [Page 3]). "
            "If the document excerpts do not contain the answer, explicitly state: "
            "'This document does not contain information to answer this question.'"
        )

        user_prompt = f"Document: {doc['filename']}\n\nDocument Context:\n{context_block}\n\nQuestion: {q_clean}"

        resp = router.generate(
            prompt=user_prompt,
            task=TaskType.PDF_QUESTION_ANSWERING,
            depth=ResponseDepth.BALANCED,
            system_prompt=sys_prompt
        )

        return {
            "answer": resp.text,
            "document_id": doc_id,
            "page_references": matched_page_nums,
            "model": resp.model,
            "provider": resp.provider
        }

    def generate_quiz(self, doc_id: str, user_id: int, num_questions: int = 5) -> Dict[str, Any]:
        """
        Generates interactive multiple-choice quiz with strictly 4 distinct options per question.
        """
        doc = self.get_document(doc_id, user_id)
        pages = self.get_document_pages(doc_id, user_id)

        sample_text = "\n\n".join(f"[Page {p['page_number']}] {p.get('text_content','')[:800]}" for p in pages[:25])

        sys_prompt = (
            "You are BrainyAi Quiz Engine. Generate an academic multiple-choice quiz based on the document.\n"
            "CRITICAL CONSTRAINTS:\n"
            "1. Every question MUST have exactly FOUR distinct, non-empty options in the options array.\n"
            "2. 'correct_index' MUST be an integer between 0 and 3.\n"
            "3. Provide a clear educational explanation and source page_ref.\n"
            "4. Output MUST be strictly valid JSON in the following schema:\n"
            "{\n"
            '  "title": "Quiz Title",\n'
            '  "questions": [\n'
            '    {\n'
            '      "question": "Clear question text?",\n'
            '      "options": ["Option A", "Option B", "Option C", "Option D"],\n'
            '      "correct_index": 0,\n'
            '      "explanation": "Why Option A is correct.",\n'
            '      "page_ref": "Page 2"\n'
            '    }\n'
            '  ]\n'
            "}"
        )

        prompt = f"Document: {doc['filename']}\nGenerate a {num_questions}-question quiz from:\n{sample_text[:20000]}"

        quiz_data = router.generate_structured(
            prompt=prompt,
            system_prompt=sys_prompt,
            task=TaskType.QUIZ_GENERATION,
            max_tokens=3000
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

        _QUIZZES_STORE.setdefault(doc_id, []).append(quiz_record)
        return quiz_record

    def get_quizzes(self, doc_id: str, user_id: int) -> List[Dict[str, Any]]:
        self.get_document(doc_id, user_id)
        quizzes = _QUIZZES_STORE.get(doc_id, [])
        return sorted(quizzes, key=lambda x: x.get("created_at", ""), reverse=True)

    def submit_quiz_attempt(
        self,
        quiz_id: str,
        user_id: int,
        user_answers: Optional[Dict[str, int] | List[int]] = None,
        selected_indices: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates user answers, computes score, and updates study progress.
        """
        if selected_indices is not None and user_answers is None:
            user_answers = {str(i): idx for i, idx in enumerate(selected_indices)}
        elif isinstance(user_answers, list):
            user_answers = {str(i): idx for i, idx in enumerate(user_answers)}
        elif user_answers is None:
            user_answers = {}

        # Find quiz
        target_quiz = None
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

        _ATTEMPTS_STORE.setdefault(quiz_id, []).append(attempt_record)

        # Update progress
        prog_key = f"{user_id}_{doc_id}"
        if prog_key in _PROGRESS_STORE:
            p = _PROGRESS_STORE[prog_key]
            p["quizzes_taken"] += 1
            p["best_quiz_score"] = max(p.get("best_quiz_score", 0), correct_count)
            p["last_studied_at"] = created_at

        return attempt_record

    def generate_flashcards(self, doc_id: str, user_id: int, count: int = 8) -> Dict[str, Any]:
        """
        Generates study flashcards from document key concepts.
        """
        doc = self.get_document(doc_id, user_id)
        pages = self.get_document_pages(doc_id, user_id)

        sample_text = "\n\n".join(f"[Page {p['page_number']}] {p.get('text_content','')[:800]}" for p in pages[:20])

        sys_prompt = (
            "You are BrainyAi Flashcard Studio. Extract the key academic concepts, formulas, and definitions from the text.\n"
            "Output MUST be strictly valid JSON in this schema:\n"
            "{\n"
            '  "cards": [\n'
            '    {\n'
            '      "front": "Concept or Question?",\n'
            '      "back": "Concise answer or explanation.",\n'
            '      "page_ref": "Page 1",\n'
            '      "difficulty": "Easy"|"Medium"|"Hard"\n'
            '    }\n'
            '  ]\n'
            "}"
        )

        prompt = f"Document: {doc['filename']}\nCreate {count} flashcards from:\n{sample_text[:18000]}"

        card_data = router.generate_structured(
            prompt=prompt,
            system_prompt=sys_prompt,
            task=TaskType.FLASHCARD_GENERATION,
            max_tokens=2500
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

        _FLASHCARDS_STORE.setdefault(doc_id, []).append(flash_record)

        # Update progress
        prog_key = f"{user_id}_{doc_id}"
        if prog_key in _PROGRESS_STORE:
            _PROGRESS_STORE[prog_key]["cards_reviewed"] += len(valid_cards)
            _PROGRESS_STORE[prog_key]["last_studied_at"] = created_at

        return flash_record

    def get_flashcards(self, doc_id: str, user_id: int) -> List[Dict[str, Any]]:
        self.get_document(doc_id, user_id)
        cards = _FLASHCARDS_STORE.get(doc_id, [])
        return sorted(cards, key=lambda x: x.get("created_at", ""), reverse=True)

    def get_study_progress(self, doc_id: str, user_id: int) -> Dict[str, Any]:
        self.get_document(doc_id, user_id)
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
