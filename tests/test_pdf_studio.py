"""
Comprehensive Unit & Integration Test Suite for BrainyAi PDF Study Studio.
Verifies local PyMuPDF extraction, local OCR fallback (zero AI calls),
durable Supabase Storage & PostgreSQL persistence, multi-stage chunking for long PDFs,
structured note generation with LaTeX formulas and page citations, strictly 4-option MCQs,
flashcard decks, study progress metrics, and strict user-ownership security.
"""

import os
import unittest
from unittest.mock import patch, MagicMock

import fitz  # PyMuPDF
from pdf_studio.service import (
    PDFStudyService,
    validate_pdf_file,
    PDFValidationError,
    PDFSecurityError,
    PDFNotFoundError
)
from pdf_studio.extractor import extract_pdf_pages, PageExtraction
from pdf_studio.ocr import is_ocr_available, ocr_page_image
from pdf_studio.chunker import chunk_document_pages, sample_pages_evenly
from ai_routing.providers.base import ProviderResult


def create_test_pdf_bytes(pages_text: list[str]) -> bytes:
    """Helper to generate a multi-page PDF using PyMuPDF."""
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class TestPDFValidationAndLocalExtraction(unittest.TestCase):
    def test_validate_valid_pdf(self):
        pdf_bytes = create_test_pdf_bytes(["Test physics content"])
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

    def test_single_page_text_extraction(self):
        pdf_bytes = create_test_pdf_bytes(["Thermodynamics is the study of heat and work."])
        pages = extract_pdf_pages(pdf_bytes)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].page_number, 1)
        self.assertIn("Thermodynamics", pages[0].text)
        self.assertEqual(pages[0].extraction_method, "native_text")
        self.assertEqual(pages[0].extraction_status, "success")
        self.assertGreater(pages[0].token_count, 0)

    def test_multi_page_distinct_content_extraction(self):
        pages_content = [
            "Chapter 1: Classical Mechanics.\nNewtonian laws of motion.",
            "Chapter 2: Fluid Dynamics.\nBernoulli's equation and Navier-Stokes.",
            "Chapter 3: Quantum Mechanics.\nWave function collapse and Schrodinger equation."
        ]
        pdf_bytes = create_test_pdf_bytes(pages_content)
        pages = extract_pdf_pages(pdf_bytes)
        self.assertEqual(len(pages), 3)
        for i, page in enumerate(pages):
            self.assertEqual(page.page_number, i + 1)
            self.assertIn(f"Chapter {i + 1}", page.text)
            self.assertEqual(page.extraction_method, "native_text")
            self.assertEqual(page.extraction_status, "success")

    def test_formulas_headings_lists_extraction(self):
        text = (
            "Mathematics & Electromagnetism\n\n"
            "Governing Maxwell Equations:\n"
            "1. Gauss's Law: $\\nabla \\cdot E = \\frac{\\rho}{\\epsilon_0}$\n"
            "2. Faraday's Law: $\\nabla \\times E = -\\frac{\\partial B}{\\partial t}$\n"
            "• Electric field E in V/m\n"
            "• Magnetic field B in Tesla"
        )
        pdf_bytes = create_test_pdf_bytes([text])
        pages = extract_pdf_pages(pdf_bytes)
        self.assertEqual(len(pages), 1)
        self.assertIn("Gauss's Law", pages[0].text)
        self.assertIn("Faraday's Law", pages[0].text)
        self.assertIn("\\nabla", pages[0].text)

    def test_empty_or_whitespace_page_handling(self):
        pdf_bytes = create_test_pdf_bytes(["   \n\t  "])
        pages = extract_pdf_pages(pdf_bytes)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].page_number, 1)
        self.assertEqual(pages[0].text, "")
        self.assertEqual(pages[0].extraction_status, "empty")

    def test_encrypted_pdf_rejection(self):
        # Create encrypted PDF using fitz
        doc = fitz.open()
        p = doc.new_page()
        p.insert_text((50, 72), "Secret content")
        # Save with user and owner passwords
        encrypted_bytes = doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="pass123", owner_pw="admin123")
        doc.close()

        with self.assertRaises(PDFValidationError):
            service = PDFStudyService()
            service.upload_and_process_pdf(user_id=101, filename="secret.pdf", file_bytes=encrypted_bytes)

    @patch("pdf_studio.ocr.is_ocr_available", return_value=False)
    def test_scanned_page_detection_without_ai_calls(self, mock_ocr_avail):
        # Create a PDF with an image to simulate scanned document
        doc = fitz.open()
        page = doc.new_page()
        # Insert a small drawn shape so page has visual elements but zero selectable text
        page.draw_rect(fitz.Rect(50, 50, 200, 200), color=(0, 0, 1), fill=(0.9, 0.9, 1))
        # Draw image
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100), 0)
        pix.clear_with(255)
        page.insert_image(fitz.Rect(50, 50, 150, 150), pixmap=pix)
        scanned_bytes = doc.tobytes()
        doc.close()

        pages = extract_pdf_pages(scanned_bytes)
        self.assertEqual(len(pages), 1)
        self.assertTrue(pages[0].is_scanned)
        # Should record local_ocr and ocr_unavailable status without any external AI calls
        self.assertEqual(pages[0].extraction_method, "local_ocr")
        self.assertEqual(pages[0].extraction_status, "ocr_unavailable")


class TestDocumentChunkingAndSampling(unittest.TestCase):
    def test_chunking_preserves_page_provenance(self):
        pages = [
            {"page_number": 1, "text_content": "Page one physics text.", "token_count": 50, "headings": ["Intro"]},
            {"page_number": 2, "text_content": "Page two equations.", "token_count": 60, "headings": ["Formulas"]},
            {"page_number": 3, "text_content": "Page three results.", "token_count": 70, "headings": ["Summary"]},
        ]
        chunks = chunk_document_pages(pages, target_tokens_per_chunk=100, overlap_pages=1)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0].start_page, 1)
        self.assertIn("[Page 1]", chunks[0].text)

    def test_uniform_sampling_across_entire_document(self):
        # 100 pages document
        pages = [{"page_number": i, "text_content": f"Text on page {i}"} for i in range(1, 101)]
        sampled = sample_pages_evenly(pages, max_pages=10)
        self.assertEqual(len(sampled), 10)
        # Ensure beginning, middle, and end are sampled
        sampled_numbers = [p["page_number"] for p in sampled]
        self.assertEqual(sampled_numbers[0], 1)
        self.assertEqual(sampled_numbers[-1], 100)
        self.assertTrue(any(40 <= n <= 60 for n in sampled_numbers))


class TestPDFStudyServicePersistenceAndSecurity(unittest.TestCase):
    def setUp(self):
        self.user_1 = 10001
        self.user_2 = 10002
        self.pdf_bytes = create_test_pdf_bytes([
            "Calculus Chapter 1: Limits and Derivatives.\nDef: Limit of f(x) as x approaches c.",
            "Calculus Chapter 2: Integrals and Applications.\nDef: Definite integral represents area under curve."
        ])

    def test_upload_and_user_isolation(self):
        service = PDFStudyService()
        doc = service.upload_and_process_pdf(
            user_id=self.user_1,
            filename="Calculus.pdf",
            file_bytes=self.pdf_bytes
        )
        doc_id = doc["id"]
        self.assertEqual(doc["filename"], "Calculus.pdf")
        self.assertEqual(doc["page_count"], 2)

        # User 1 can retrieve their document
        retrieved = service.get_document(doc_id, self.user_1)
        self.assertEqual(retrieved["id"], doc_id)

        # User 2 cannot access user 1's document (raises PDFSecurityError)
        with self.assertRaises(PDFSecurityError):
            service.get_document(doc_id, self.user_2)

        # Document list for User 1 contains doc, User 2 does not
        user1_docs = service.get_user_documents(self.user_1)
        user2_docs = service.get_user_documents(self.user_2)
        self.assertTrue(any(d["id"] == doc_id for d in user1_docs))
        self.assertFalse(any(d["id"] == doc_id for d in user2_docs))

    def test_supabase_persistence_layer_integration(self):
        """Simulates Supabase REST client and verifies durable table operations."""
        mock_sb_req = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": "mock-doc-123", "user_id": self.user_1, "filename": "Test.pdf"}]
        mock_sb_req.return_value = mock_response

        service = PDFStudyService(
            supabase_request_fn=mock_sb_req,
            supabase_url="https://mock-supabase.co",
            supabase_key="mock-key"
        )

        with patch.object(service, "_upload_to_supabase_storage", return_value="10001/mock-doc-123/original.pdf"):
            doc = service.upload_and_process_pdf(
                user_id=self.user_1,
                filename="IntegrationTest.pdf",
                file_bytes=self.pdf_bytes
            )

        # Verify calls to user_documents, document_pages, and document_study_progress
        tables_called = [call[0][1] for call in mock_sb_req.call_args_list if len(call[0]) > 1]
        self.assertIn("user_documents", tables_called)
        self.assertIn("document_pages", tables_called)
        self.assertIn("document_study_progress", tables_called)

    def test_simulated_backend_restart_and_reopen_documents(self):
        """Tests that documents survive service re-instantiation when connected to Supabase."""
        stored_db = {
            "user_documents": [
                {
                    "id": "persisted-doc-99",
                    "user_id": self.user_1,
                    "filename": "Persisted.pdf",
                    "file_size": 2048,
                    "page_count": 2,
                    "processing_status": "ready",
                    "created_at": "2026-10-26T00:00:00Z"
                }
            ],
            "document_notes": [
                {
                    "id": "note-1",
                    "document_id": "persisted-doc-99",
                    "user_id": self.user_1,
                    "title": "Study Notes: Persisted.pdf",
                    "content": "## Executive Summary\nKey points [Page 1].",
                    "citations": [1],
                    "created_at": "2026-10-26T00:00:00Z"
                }
            ]
        }

        def fake_sb_req(method, table, params="", json_body=None):
            resp = MagicMock()
            if table == "user_documents":
                resp.json.return_value = stored_db["user_documents"]
            elif table == "document_notes":
                resp.json.return_value = stored_db["document_notes"]
            else:
                resp.json.return_value = []
            return resp

        # Brand new service instance simulating server reboot
        new_service = PDFStudyService(
            supabase_request_fn=fake_sb_req,
            supabase_url="https://mock-supabase.co",
            supabase_key="mock-key"
        )

        user_docs = new_service.get_user_documents(self.user_1)
        self.assertEqual(len(user_docs), 1)
        self.assertEqual(user_docs[0]["id"], "persisted-doc-99")

        notes = new_service.get_notes("persisted-doc-99", self.user_1)
        self.assertEqual(len(notes), 1)
        self.assertIn("Executive Summary", notes[0]["content"])

    @patch("ai_routing.router.router.generate")
    def test_structured_notes_generation_with_citations(self, mock_generate):
        mock_generate.return_value = ProviderResult(
            text=(
                "# 📘 Calculus Fundamentals\n\n"
                "## 📌 Executive Summary\nCore limits and derivatives [Page 1].\n\n"
                "## 💡 Essential Definitions & Terminology\n**Derivative**: Instantaneous rate of change [Page 1].\n\n"
                "## 🧮 Governing Formulas & Mathematical Notation\n$$f'(x) = \\lim_{h \\to 0} \\frac{f(x+h)-f(x)}{h}$$ [Page 1]\n\n"
                "## 🎯 High-Yield Revision Takeaways\n1. Product rule: $(uv)' = u'v + uv'$ [Page 2]."
            ),
            model="llama-3.3-70b-versatile",
            provider="groq",
            latency_ms=120.0,
            tokens_out=150
        )

        service = PDFStudyService()
        doc = service.upload_and_process_pdf(
            user_id=self.user_1,
            filename="Calculus_Notes.pdf",
            file_bytes=self.pdf_bytes
        )
        note = service.generate_notes(doc["id"], self.user_1)
        self.assertIn("Executive Summary", note["content"])
        self.assertIn("Governing Formulas", note["content"])
        self.assertIn("[Page 1]", note["content"])
        self.assertIn(1, note["citations"])
        self.assertIn(2, note["citations"])

    @patch("ai_routing.router.router.generate")
    def test_long_document_multi_stage_notes_synthesis(self, mock_generate):
        """Tests that documents with > 15 pages trigger multi-stage chunking without hardcoded slices."""
        mock_generate.return_value = ProviderResult(
            text="# 📘 Comprehensive Master Study Guide\n## 📌 Executive Summary\nMastered [Page 1] to [Page 20].",
            model="mock-model",
            provider="mock-provider",
            latency_ms=200.0,
            tokens_out=250
        )

        # Create a 20-page document
        twenty_pages = [f"Page {i} comprehensive topic discussion." for i in range(1, 21)]
        long_pdf = create_test_pdf_bytes(twenty_pages)

        service = PDFStudyService()
        doc = service.upload_and_process_pdf(
            user_id=self.user_1,
            filename="Long_Textbook.pdf",
            file_bytes=long_pdf
        )
        self.assertEqual(doc["page_count"], 20)

        note = service.generate_notes(doc["id"], self.user_1)
        self.assertIn("Comprehensive Master Study Guide", note["content"])
        # Multi-stage calls should have happened (chunk calls + consolidation call)
        self.assertGreaterEqual(mock_generate.call_count, 2)

    @patch("ai_routing.router.router.generate_structured")
    def test_quiz_generation_strictly_4_options(self, mock_gen_struct):
        mock_gen_struct.return_value = {
            "title": "Calculus Exam Quiz",
            "questions": [
                {
                    "question": "What is the derivative of x^2?",
                    "options": ["2x", "x", "x^2", "2"],
                    "correct_index": 0,
                    "explanation": "Power rule: d/dx(x^2) = 2x.",
                    "page_ref": "Page 1"
                },
                {
                    "question": "What is the integral of 2x dx?",
                    "options": ["x^2 + C", "2x + C", "x^3 + C", "x + C"],
                    "correct_index": 0,
                    "explanation": "Reverse power rule.",
                    "page_ref": "Page 2"
                }
            ]
        }

        service = PDFStudyService()
        doc = service.upload_and_process_pdf(
            user_id=self.user_1,
            filename="Calculus_Quiz.pdf",
            file_bytes=self.pdf_bytes
        )
        quiz = service.generate_quiz(doc["id"], self.user_1, num_questions=2)
        self.assertEqual(len(quiz["questions"]), 2)

        for q in quiz["questions"]:
            self.assertEqual(len(q["options"]), 4)
            self.assertIn(q["correct_index"], [0, 1, 2, 3])
            self.assertTrue(q["page_ref"])

    def test_quiz_scoring_and_study_progress(self):
        service = PDFStudyService()
        doc = service.upload_and_process_pdf(
            user_id=self.user_1,
            filename="Progress_Test.pdf",
            file_bytes=self.pdf_bytes
        )

        with patch("ai_routing.router.router.generate_structured") as mock_gen:
            mock_gen.return_value = {
                "title": "Progress Quiz",
                "questions": [
                    {
                        "question": "Question 1?",
                        "options": ["A", "B", "C", "D"],
                        "correct_index": 1,
                        "explanation": "Because B",
                        "page_ref": "Page 1"
                    },
                    {
                        "question": "Question 2?",
                        "options": ["W", "X", "Y", "Z"],
                        "correct_index": 2,
                        "explanation": "Because Y",
                        "page_ref": "Page 2"
                    }
                ]
            }
            quiz = service.generate_quiz(doc["id"], self.user_1, num_questions=2)

        # Attempt: question 0 selected 1 (correct), question 1 selected 0 (incorrect)
        attempt = service.submit_quiz_attempt(
            quiz_id=quiz["id"],
            user_id=self.user_1,
            selected_indices=[1, 0]
        )

        self.assertEqual(attempt["score"], 1)
        self.assertEqual(attempt["total"], 2)
        self.assertEqual(attempt["percentage"], 50.0)

        # Check progress record
        progress = service.get_study_progress(doc["id"], self.user_1)
        self.assertEqual(progress["quizzes_taken"], 1)
        self.assertEqual(progress["best_quiz_score"], 1)

    @patch("ai_routing.router.router.generate_structured")
    def test_flashcards_generation_and_validation(self, mock_gen):
        mock_gen.return_value = {
            "cards": [
                {
                    "front": "What is a Limit?",
                    "back": "The value that a function approaches as input approaches some value.",
                    "page_ref": "Page 1",
                    "difficulty": "Easy"
                },
                {
                    "front": "What is a Derivative?",
                    "back": "The instantaneous rate of change of a function with respect to one of its variables.",
                    "page_ref": "Page 1",
                    "difficulty": "Medium"
                }
            ]
        }

        service = PDFStudyService()
        doc = service.upload_and_process_pdf(
            user_id=self.user_1,
            filename="Flashcards_Test.pdf",
            file_bytes=self.pdf_bytes
        )
        deck = service.generate_flashcards(doc["id"], self.user_1, count=2)
        self.assertEqual(len(deck["cards"]), 2)
        self.assertEqual(deck["cards"][0]["front"], "What is a Limit?")
        self.assertEqual(deck["cards"][0]["difficulty"], "Easy")

        # Decks can be retrieved
        decks = service.get_flashcards(doc["id"], self.user_1)
        self.assertEqual(len(decks), 1)

    @patch("ai_routing.router.router.generate")
    def test_document_grounded_qa(self, mock_generate):
        mock_generate.return_value = ProviderResult(
            text="The derivative measures instantaneous slope [Page 1].",
            model="llama-3.3-70b-versatile",
            provider="groq",
            latency_ms=80.0,
            tokens_out=40
        )

        service = PDFStudyService()
        doc = service.upload_and_process_pdf(
            user_id=self.user_1,
            filename="QA_Test.pdf",
            file_bytes=self.pdf_bytes
        )
        qa = service.ask_document(doc["id"], self.user_1, question="What does derivative measure?")
        self.assertIn("instantaneous slope", qa["answer"])
        self.assertIn("page_references", qa)
        self.assertIn(1, qa["page_references"])

    def test_delete_document_and_cascade_cleanup(self):
        service = PDFStudyService()
        doc = service.upload_and_process_pdf(
            user_id=self.user_1,
            filename="To_Delete.pdf",
            file_bytes=self.pdf_bytes
        )
        doc_id = doc["id"]

        # User 2 cannot delete user 1's document
        with self.assertRaises(PDFSecurityError):
            service.delete_document(doc_id, self.user_2)

        # User 1 successfully deletes
        self.assertTrue(service.delete_document(doc_id, self.user_1))

        # Re-fetching raises PDFNotFoundError
        with self.assertRaises(PDFNotFoundError):
            service.get_document(doc_id, self.user_1)


if __name__ == "__main__":
    unittest.main()
