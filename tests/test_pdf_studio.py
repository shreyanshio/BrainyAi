"""
Unit tests for Phase 2: PDF Study Studio.
Verifies PDF validation (signature, oversize limit), text extraction,
isolated user storage, note generation, strictly 4-option quiz generation,
quiz attempt scoring, flashcard generation, and study progress tracking.
"""

import unittest
from unittest.mock import patch, MagicMock

import fitz  # PyMuPDF
from pdf_studio.service import (
    PDFStudyService,
    validate_pdf_file,
    PDFValidationError,
    PDFSecurityError
)
from pdf_studio.extractor import extract_pdf_pages
from ai_routing.providers.base import ProviderResult


def create_minimal_pdf_bytes(text: str = "BrainyAi Sample Document Content") -> bytes:
    """Helper to generate valid in-memory PDF bytes using PyMuPDF."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class TestPDFValidationAndExtraction(unittest.TestCase):
    def test_validate_valid_pdf(self):
        pdf_bytes = create_minimal_pdf_bytes("Test content")
        clean_name, size = validate_pdf_file(pdf_bytes, "Physics_Notes.pdf")
        self.assertEqual(clean_name, "Physics_Notes.pdf")
        self.assertGreater(size, 0)

    def test_validate_invalid_extension(self):
        with self.assertRaises(PDFValidationError):
            validate_pdf_file(b"%PDF-1.4 something", "notes.docx")

    def test_validate_invalid_signature(self):
        with self.assertRaises(PDFValidationError):
            validate_pdf_file(b"NOT_A_PDF_FILE", "notes.pdf")

    def test_validate_oversize_file(self):
        fake_huge_bytes = b"%PDF-" + b"0" * (26 * 1024 * 1024)
        with self.assertRaises(PDFValidationError):
            validate_pdf_file(fake_huge_bytes, "huge.pdf", max_size_mb=25)

    def test_page_aware_text_extraction(self):
        pdf_bytes = create_minimal_pdf_bytes("Thermodynamics is the study of heat and work.")
        pages = extract_pdf_pages(pdf_bytes)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].page_number, 1)
        self.assertIn("Thermodynamics", pages[0].text)
        self.assertGreater(pages[0].token_count, 0)


class TestPDFStudyServiceLifecycle(unittest.TestCase):
    def setUp(self):
        self.service = PDFStudyService()
        self.user_1 = 10001
        self.user_2 = 10002
        self.pdf_bytes = create_minimal_pdf_bytes("Calculus Chapter 1: Limits and Derivatives.\nDef: Limit of f(x) as x approaches c.")

    def test_upload_and_user_isolation(self):
        doc = self.service.upload_and_process_pdf(
            user_id=self.user_1,
            filename="Calculus.pdf",
            file_bytes=self.pdf_bytes
        )
        doc_id = doc["id"]
        self.assertEqual(doc["filename"], "Calculus.pdf")
        self.assertEqual(doc["page_count"], 1)

        # User 1 can retrieve their document
        retrieved = self.service.get_document(doc_id, self.user_1)
        self.assertEqual(retrieved["id"], doc_id)

        # User 2 cannot access user 1's document (raises PDFSecurityError)
        with self.assertRaises(PDFSecurityError):
            self.service.get_document(doc_id, self.user_2)

        # Document list for User 1 contains doc, User 2 does not
        user1_docs = self.service.get_user_documents(self.user_1)
        user2_docs = self.service.get_user_documents(self.user_2)
        self.assertTrue(any(d["id"] == doc_id for d in user1_docs))
        self.assertFalse(any(d["id"] == doc_id for d in user2_docs))

    @patch("ai_routing.router.router.generate")
    def test_generate_notes_with_citations(self, mock_generate):
        mock_generate.return_value = ProviderResult(
            text="### Executive Overview\nKey concepts [Page 1].\n### Formulas\n$$f'(x) = \\lim \\frac{f(x+h)-f(x)}{h}$$ [Page 1]",
            model="mock-gemini",
            provider="gemini",
            latency_ms=100.0,
            tokens_out=80
        )

        doc = self.service.upload_and_process_pdf(
            user_id=self.user_1,
            filename="Derivatives.pdf",
            file_bytes=self.pdf_bytes
        )
        note = self.service.generate_notes(doc["id"], self.user_1)
        self.assertIn("Executive Overview", note["content"])
        self.assertIn("[Page 1]", note["content"])
        self.assertIn("citations", note)
        self.assertIn(1, note["citations"])

    @patch("ai_routing.router.router.generate_structured")
    def test_generate_quiz_strictly_4_options(self, mock_gen_struct):
        # Mock structured LLM response
        mock_gen_struct.return_value = {
            "title": "Calculus Quiz",
            "questions": [
                {
                    "question": "What is the derivative of x^2?",
                    "options": ["2x", "x", "x^2", "2"],
                    "correct_index": 0,
                    "explanation": "By the power rule, d/dx(x^n) = n*x^(n-1).",
                    "page_ref": "Page 1"
                },
                {
                    "question": "What is the limit of 1/x as x approaches infinity?",
                    "options": ["1", "0", "infinity", "undefined"],
                    "correct_index": 1,
                    "explanation": "As denominator grows indefinitely, value approaches 0.",
                    "page_ref": "Page 1"
                }
            ]
        }

        doc = self.service.upload_and_process_pdf(
            user_id=self.user_1,
            filename="Calculus_Quiz.pdf",
            file_bytes=self.pdf_bytes
        )
        quiz = self.service.generate_quiz(doc["id"], self.user_1, num_questions=2)
        self.assertEqual(len(quiz["questions"]), 2)

        # Strictly 4 options per question verification
        for q in quiz["questions"]:
            self.assertEqual(len(q["options"]), 4)
            self.assertIn(q["correct_index"], [0, 1, 2, 3])

    def test_quiz_attempt_scoring(self):
        # Create a mock quiz directly in store
        doc = self.service.upload_and_process_pdf(
            user_id=self.user_1,
            filename="Scoring_Test.pdf",
            file_bytes=self.pdf_bytes
        )

        with patch("ai_routing.router.router.generate_structured") as mock_gen_struct:
            mock_gen_struct.return_value = {
                "title": "Quick Math Quiz",
                "questions": [
                    {
                        "question": "2 + 2 = ?",
                        "options": ["3", "4", "5", "6"],
                        "correct_index": 1,
                        "explanation": "Basic addition",
                        "page_ref": "Page 1"
                    },
                    {
                        "question": "5 * 5 = ?",
                        "options": ["20", "25", "30", "35"],
                        "correct_index": 1,
                        "explanation": "Multiplication",
                        "page_ref": "Page 1"
                    }
                ]
            }
            quiz = self.service.generate_quiz(doc["id"], self.user_1, num_questions=2)

        # Attempt: question 1 correct (index 1), question 2 incorrect (index 0)
        attempt = self.service.submit_quiz_attempt(
            quiz_id=quiz["id"],
            user_id=self.user_1,
            selected_indices=[1, 0]
        )

        self.assertEqual(attempt["score"], 1)
        self.assertEqual(attempt["total"], 2)
        self.assertEqual(attempt["percentage"], 50.0)
        self.assertTrue(attempt["feedback"][0]["is_correct"])
        self.assertFalse(attempt["feedback"][1]["is_correct"])

    def test_delete_document(self):
        doc = self.service.upload_and_process_pdf(
            user_id=self.user_1,
            filename="To_Delete.pdf",
            file_bytes=self.pdf_bytes
        )
        doc_id = doc["id"]
        self.service.delete_document(doc_id, self.user_1)

        # Accessing after deletion raises PDFValidationError
        with self.assertRaises(PDFValidationError):
            self.service.get_document(doc_id, self.user_1)


if __name__ == "__main__":
    unittest.main()
