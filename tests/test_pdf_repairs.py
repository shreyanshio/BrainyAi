"""
tests/test_pdf_repairs.py
=========================
Regression test suite for PDF Study Studio repairs, 10 MB upload ceiling,
5-day document retention lifecycle, Notes Assistant routing, SSE question streaming,
deterministic greeting latency fast-path, and 3 MB image attachment validation.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from pdf_studio.service import PDFStudyService, PDFValidationError
from pdf_studio.extractor import PageExtraction
from pdf_studio.notes_engine import generate_local_notes
from ai_routing.policy import PDF_STUDY_TASKS, get_routing_candidates
from ai_routing.tasks import TaskType, TaskComplexity, ResponseDepth


class TestPdfStudioRepairs(unittest.TestCase):

    def setUp(self):
        self.service = PDFStudyService()

    def test_pdf_10mb_limit_enforced(self):
        """Strict 10 MB size limit must reject larger files with PDFValidationError."""
        oversized = b"%PDF-1.4" + b"0" * (10 * 1024 * 1024 + 10)
        with self.assertRaises(PDFValidationError) as ctx:
            self.service.upload_and_process_pdf(user_id=1, filename="large.pdf", file_bytes=oversized)
        self.assertTrue("10MB" in str(ctx.exception) or "10 MB" in str(ctx.exception))

    def test_pdf_5_day_expiration_calculated(self):
        """Document creation must set expires_at exactly 5 days into the future."""
        mock_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        with patch('pdf_studio.service.extract_pdf_pages') as mock_ext:
            mock_ext.return_value = [
                PageExtraction(
                    page_number=1,
                    text="Brainy study content",
                    token_count=10,
                    has_images=False,
                    headings=[],
                    is_scanned=False,
                    extraction_method="direct_text",
                    extraction_status="success",
                    image_bytes=None,
                    error_message=None
                )
            ]
            doc = self.service.upload_and_process_pdf(user_id=42, filename="notes.pdf", file_bytes=mock_pdf)
            self.assertIn("expires_at", doc)
            expires_at = datetime.fromisoformat(doc["expires_at"])
            uploaded_at = datetime.fromisoformat(doc["uploaded_at"])
            diff = expires_at - uploaded_at
            self.assertEqual(diff.days, 5)

    def test_notes_formatting_no_broken_symbols(self):
        """Notes engine output must not contain raw unformatted markdown or emojis."""
        sample_pages = [
            {"page_number": 1, "text": "Linear Algebra covers vector spaces and linear transformations."},
            {"page_number": 2, "text": "Eigenvalues solve the equation Av = lambda v for non-zero vectors."}
        ]
        content = generate_local_notes(
            doc_title="Linear Algebra",
            pages=sample_pages,
            depth="standard"
        )
        self.assertNotIn("📚", content)
        self.assertNotIn("⏱️", content)
        self.assertNotIn("Local Deterministic Core", content)
        self.assertIn("Linear Algebra", content)

    def test_gemini_allowed_in_pdf_study_tasks(self):
        """PDF Study tasks must include Gemini in their routing policy and not disallow Gemini."""
        for task in PDF_STUDY_TASKS:
            candidates = get_routing_candidates(task, TaskComplexity.STANDARD, ResponseDepth.BALANCED)
            self.assertTrue(len(candidates) > 0, f"Task {task} has no candidates")
            if task == TaskType.PDF_QUESTION_ANSWERING:
                self.assertEqual(candidates[0][0], "gemini")

    def test_important_questions_category_support(self):
        """generate_important_questions and stream_important_questions must accept category."""
        with patch.object(self.service, 'get_document') as mock_get_doc, \
             patch.object(self.service, 'get_document_pages') as mock_pages, \
             patch('ai_routing.router.router.generate_structured') as mock_ai:
            mock_get_doc.return_value = {"id": "doc_1", "user_id": 1, "status": "ready", "title": "Test Doc"}
            mock_pages.return_value = [{"page_number": 1, "text_content": "Photosynthesis turns light energy into chemical energy."}]
            mock_ai.return_value = {"questions": [{"id": "q1", "question": "What is photosynthesis?", "category": "DEFINITION", "priority": "HIGH", "expected_answer": "Conversion of light to chemical energy", "page_ref": "Page 1"}]}

            items = list(self.service.stream_important_questions(
                doc_id="doc_1", user_id=1, count=5, category="DEFINITION"
            ))
            self.assertTrue(len(items) > 0)
            events = [it.get("event") for it in items]
            self.assertIn("question", events)
            self.assertTrue("complete" in events or "done" in events)

    def test_cleanup_expired_documents_user_scoping(self):
        """Verifies cleanup_expired_documents accepts user_id without TypeError and scopes cleanup correctly."""
        from pdf_studio.service import _DOCUMENTS_STORE
        now = datetime.now(timezone.utc)
        past = (now - timedelta(days=6)).isoformat()
        future = (now + timedelta(days=2)).isoformat()

        _DOCUMENTS_STORE["expired_user_10"] = {
            "id": "expired_user_10",
            "user_id": 10,
            "filename": "old10.pdf",
            "status": "ready",
            "expires_at": past
        }
        _DOCUMENTS_STORE["expired_user_20"] = {
            "id": "expired_user_20",
            "user_id": 20,
            "filename": "old20.pdf",
            "status": "ready",
            "expires_at": past
        }
        _DOCUMENTS_STORE["active_user_10"] = {
            "id": "active_user_10",
            "user_id": 10,
            "filename": "active10.pdf",
            "status": "ready",
            "expires_at": future
        }

        # 1. Scope cleanup to user 10
        res = self.service.cleanup_expired_documents(user_id=10)
        self.assertIn("expired_user_10", res["document_ids"])
        self.assertNotIn("expired_user_20", res["document_ids"])
        self.assertEqual(_DOCUMENTS_STORE["expired_user_10"]["status"], "expired")
        self.assertEqual(_DOCUMENTS_STORE["expired_user_20"]["status"], "ready")
        self.assertEqual(_DOCUMENTS_STORE["active_user_10"]["status"], "ready")

        # 2. Global cleanup with no user_id cleans remaining expired
        res2 = self.service.cleanup_expired_documents()
        self.assertIn("expired_user_20", res2["document_ids"])
        self.assertEqual(_DOCUMENTS_STORE["expired_user_20"]["status"], "expired")

    def test_important_questions_category_normalization(self):
        """Verifies category normalization handles aliases and case-insensitivity cleanly."""
        with patch.object(self.service, 'get_document') as mock_get_doc, \
             patch.object(self.service, 'get_document_pages') as mock_pages, \
             patch('ai_routing.router.router.generate_structured') as mock_ai:
            mock_get_doc.return_value = {"id": "doc_101", "user_id": 1, "status": "ready", "title": "Physics"}
            mock_pages.return_value = [{"page_number": 1, "text_content": "Newton's second law is F = ma."}]
            mock_ai.return_value = {
                "questions": [
                    {
                        "question": "State Newton's second law.",
                        "category": "definitions and terminology",
                        "priority": "HIGH",
                        "answer_outline": ["F = ma", "Rate of change of momentum"],
                        "page_ref": "Page 1"
                    }
                ]
            }

            res = self.service.generate_important_questions(
                doc_id="doc_101",
                user_id=1,
                count=5,
                category="DEFINITION"
            )
            self.assertEqual(res["questions"][0]["category"], "Definition")

    def test_pdf_routes_value_error_handling(self):
        """Verifies that ValueError raised by service produces HTTP 400 instead of generic 500."""
        from app import app
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["user_id"] = 101

            with patch("pdf_studio.service.pdf_service.generate_notes", side_effect=ValueError("Document has no readable text to generate notes from.")):
                resp = client.post("/api/pdf/documents/test-doc/notes", json={"depth": "STANDARD"})
                self.assertEqual(resp.status_code, 400)
                self.assertIn("Document has no readable text", resp.get_json()["error"])

    def test_fast_deterministic_greeting(self):
        """Fast greeting check must catch pure greetings and return immediately."""
        from app import _check_fast_greeting
        self.assertIsNotNone(_check_fast_greeting("Hi", "Alice"))
        self.assertIsNotNone(_check_fast_greeting("hello!", "Bob"))
        self.assertIsNotNone(_check_fast_greeting("Good morning", "Charlie"))
        self.assertIsNotNone(_check_fast_greeting("hey", "User"))
        self.assertIsNone(_check_fast_greeting("What is the derivative of sin(x)?", "Alice"))
        self.assertIsNone(_check_fast_greeting("Explain photosynthesis", "Alice"))
        self.assertIsNone(_check_fast_greeting("hello, how do I derive quantum mechanics?", "Alice"))

    def test_image_attachment_validation(self):
        """Images exceeding 3 MB must be rejected with 413."""
        from app import app, _prepare_chat_request
        oversized_b64 = "A" * (4 * 1024 * 1024 + 100)
        data = {
            "message": "Analyze this diagram",
            "image": f"data:image/png;base64,{oversized_b64}"
        }
        with app.test_request_context():
            prep, err, status = _prepare_chat_request(data, user_id=999, first_name="Test", username="test", ip="127.0.0.1")
            self.assertEqual(status, 413)
            self.assertIn("3 MB", err.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
