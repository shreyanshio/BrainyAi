"""
Comprehensive Automated Test Suite for Brainy Multimodal Image Intelligence & Centralized Google Drive Storage
=============================================================================================================
Tests:
- Valid image uploads (PNG, JPEG, WebP)
- Rejection of oversized images (> 3 MB)
- Rejection of corrupted / spoofed / non-image files
- IDOR isolation: User B cannot preview, download, or delete User A's file
- Preview serving with private headers and correct MIME types
- Deletion of files and cleanup
- Deterministic Drive folder hierarchy (Brainy/Users/user_{opaque_id}/Images/{year}/{month})
- Empty-text image question handling (auto-prompting)
- Vision model routing and strict text-only model exclusion
- Safe error fallback message ("Image analysis is temporarily unavailable. Please try again later.")
- Chat history persistence and image restoration across reloads
"""

import os
import io
import time
import json
import unittest
from unittest.mock import patch, MagicMock
from PIL import Image

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, sb_insert_message, sb_get_messages, sb_create_session
from security import create_auth_token
import file_service
from file_service import (
    validate_image_file, FileTooLargeError, InvalidImageError,
    save_file, get_file, delete_file, _FILES_STORE
)
from pdf_studio.google_drive import drive_storage
from ai_routing.policy import get_routing_candidates
from ai_routing.tasks import TaskType
from ai_routing.registry import registry
from ai_routing.providers.gemini_provider import GeminiProvider
from ai_routing.providers.openrouter_provider import _format_openrouter_messages


def _create_sample_image(fmt="PNG", size=(50, 50), color=(70, 130, 180)):
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format=fmt)
    return buf.getvalue()


class TestImageIntelligenceAndDrive(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = app.test_client()
        self.user_a_id = 9001
        self.user_b_id = 9002

        self.token_a = create_auth_token(
            user_id=self.user_a_id,
            username="student_alpha",
            first_name="Alpha",
            role="student"
        )
        self.token_b = create_auth_token(
            user_id=self.user_b_id,
            username="student_beta",
            first_name="Beta",
            role="student"
        )

        # Clear test user cache files
        from pdf_studio.google_drive import DATA_DIR
        for uid in [self.user_a_id, self.user_b_id]:
            cf = os.path.join(DATA_DIR, f"user_folder_{uid}.json")
            if os.path.exists(cf):
                try:
                    os.remove(cf)
                except Exception:
                    pass

    # ── 1. Image Validation Tests ────────────────────────────────────

    def test_valid_image_formats_accepted(self):
        for fmt, mime in [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")]:
            raw_bytes = _create_sample_image(fmt=fmt)
            meta = validate_image_file(raw_bytes, f"test.{fmt.lower()}")
            self.assertEqual(meta["mime_type"], mime)
            self.assertEqual(meta["image_width"], 50)
            self.assertEqual(meta["image_height"], 50)

    def test_oversized_image_rejected(self):
        huge_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * (3 * 1024 * 1024 + 100)
        with self.assertRaises(FileTooLargeError):
            validate_image_file(huge_bytes, "huge.png")

    def test_corrupted_image_rejected(self):
        corrupted = b"NOT_A_VALID_IMAGE_HEADER_CONTENT_BYTES"
        with self.assertRaises(InvalidImageError):
            validate_image_file(corrupted, "corrupt.png")

    def test_extension_spoofing_rejected(self):
        spoofed = b"%PDF-1.5 some pdf data pretending to be an image"
        with self.assertRaises(InvalidImageError):
            validate_image_file(spoofed, "fake.png")

    # ── 2. Endpoint Upload & Drive Storage Tests ────────────────────

    def test_upload_endpoint_success(self):
        png_bytes = _create_sample_image("PNG", size=(60, 60))
        data = {
            "file": (io.BytesIO(png_bytes), "sample_math.png", "image/png")
        }
        res = self.client.post(
            "/api/upload",
            data=data,
            content_type="multipart/form-data",
            headers={"Authorization": f"Bearer {self.token_a}"}
        )
        self.assertIn(res.status_code, (200, 201))
        body = res.get_json()
        self.assertIn("file_id", body)
        self.assertEqual(body["original_filename"], "sample_math.png")
        self.assertEqual(body["mime_type"], "image/png")
        self.assertIn("preview_url", body)

    @patch.object(drive_storage, "initialize_root_hierarchy", return_value=("root_folder", "users_folder"))
    @patch.object(drive_storage, "_find_or_create_folder")
    def test_drive_folder_hierarchy_structure(self, mock_create, mock_init):
        mock_create.side_effect = lambda name, parent_id: f"id_{name}"
        folder_id = drive_storage.get_or_create_user_image_folder(self.user_a_id)
        opaque_a = drive_storage.derive_user_opaque_id(self.user_a_id)

        # Verify folder calls: user folder first under users_folder, then Images inside it
        mock_create.assert_any_call(f"user_{opaque_a}", parent_id="users_folder")
        mock_create.assert_any_call("Images", parent_id=f"id_user_{opaque_a}")
        self.assertTrue(folder_id)

    # ── 3. IDOR Protection & Access Control ─────────────────────────

    def test_idor_protection_between_users(self):
        # User A uploads a file
        png_bytes = _create_sample_image("PNG")
        meta = save_file(
            file_bytes=png_bytes,
            filename="private_a.png",
            mime_type="image/png",
            user_id=self.user_a_id
        )
        file_id = meta["file_id"]

        # User A can preview it
        res_a = self.client.get(
            f"/api/files/{file_id}/preview",
            headers={"Authorization": f"Bearer {self.token_a}"}
        )
        self.assertEqual(res_a.status_code, 200)
        self.assertEqual(res_a.headers["Content-Type"], "image/png")
        self.assertIn("private", res_a.headers.get("Cache-Control", ""))

        # User B CANNOT preview it (403 or 404 to prevent enumeration / access)
        res_b = self.client.get(
            f"/api/files/{file_id}/preview",
            headers={"Authorization": f"Bearer {self.token_b}"}
        )
        self.assertIn(res_b.status_code, (403, 404))

        # User B CANNOT delete it
        res_b_del = self.client.delete(
            f"/api/files/{file_id}",
            headers={"Authorization": f"Bearer {self.token_b}"}
        )
        self.assertIn(res_b_del.status_code, (403, 404))

        # File is still intact for User A
        res_a_check = self.client.get(
            f"/api/files/{file_id}/preview",
            headers={"Authorization": f"Bearer {self.token_a}"}
        )
        self.assertEqual(res_a_check.status_code, 200)

        # User A deletes their own file
        res_a_del = self.client.delete(
            f"/api/files/{file_id}",
            headers={"Authorization": f"Bearer {self.token_a}"}
        )
        self.assertEqual(res_a_del.status_code, 200)

        # After deletion, preview returns 404
        res_a_post_del = self.client.get(
            f"/api/files/{file_id}/preview",
            headers={"Authorization": f"Bearer {self.token_a}"}
        )
        self.assertEqual(res_a_post_del.status_code, 404)

    # ── 4. Empty Text with Attached Image Query ─────────────────────

    def test_empty_text_with_image_accepted(self):
        png_bytes = _create_sample_image("PNG")
        meta = save_file(
            file_bytes=png_bytes,
            filename="geometry_problem.png",
            mime_type="image/png",
            user_id=self.user_a_id
        )
        file_id = meta["file_id"]

        with patch("study_bot.ai_call", return_value="The image shows a geometric diagram."):
            res = self.client.post(
                "/api/chat/send",
                json={
                    "message": "",
                    "file_id": file_id
                },
                headers={"Authorization": f"Bearer {self.token_a}"}
            )
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertIn("response", data)
            self.assertEqual(data["response"], "The image shows a geometric diagram.")

    # ── 5. AI Policy & Vision-Only Model Selection ───────────────────

    def test_text_only_models_excluded_for_multimodal_request(self):
        # Normal text-only request includes text-only providers (e.g. Groq)
        text_candidates = get_routing_candidates(TaskType.GENERAL_STUDY)
        text_providers = [c[0] for c in text_candidates]
        self.assertIn("groq", text_providers)

        # Multimodal request with image_input / has_image strictly excludes text-only providers
        multimodal_candidates = get_routing_candidates(TaskType.GENERAL_STUDY, document_context={"has_image": True})
        multimodal_providers = [c[0] for c in multimodal_candidates]

        # Groq must be excluded
        self.assertNotIn("groq", multimodal_providers)
        # Vision providers must be present
        self.assertIn("gemini", multimodal_providers)
        self.assertIn("openrouter", multimodal_providers)

        # OpenRouter model selected must be vision-capable
        openrouter_models = [c[1] for c in multimodal_candidates if c[0] == "openrouter"]
        self.assertEqual(openrouter_models, ["nvidia/nemotron-3.5-super-vl:free"])

    # ── 6. Multimodal Payload Construction ──────────────────────────

    @patch("ai_routing.providers.gemini_provider._http_post")
    def test_gemini_multimodal_parts_on_latest_turn(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Analysis of the uploaded diagram."}]}}],
            "usageMetadata": {"promptTokenCount": 50, "candidatesTokenCount": 20}
        }
        mock_post.return_value = mock_resp

        provider = GeminiProvider()
        with patch.object(registry, "get_rotator") as mock_rotator:
            mock_rot = MagicMock()
            mock_rot.key_count = 1
            mock_rot.get_key.return_value = "fake_gemini_key_123"
            mock_rotator.return_value = mock_rot

            messages = [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there! How can I help?"},
                {"role": "user", "content": "What is in this picture?"}
            ]
            multimodal_parts = [{
                "inline_data": {
                    "mime_type": "image/png",
                    "data": "fakebase64data"
                }
            }]
            result = provider.generate(
                model_id="gemini-2.5-flash",
                messages=messages,
                system_prompt="You are Brainy.",
                max_tokens=100,
                multimodal_parts=multimodal_parts
            )
            self.assertEqual(result.text, "Analysis of the uploaded diagram.")
            req_payload = mock_post.call_args[1]["json"]
            contents = req_payload["contents"]
            # The latest turn (idx 2) must include both the text and the multimodal part
            last_turn = contents[-1]
            self.assertEqual(len(last_turn["parts"]), 2)
            self.assertEqual(last_turn["parts"][0]["inline_data"]["data"], "fakebase64data")

    def test_openrouter_vision_message_formatting(self):
        messages = [
            {"role": "user", "content": "Analyze this math problem"}
        ]
        multimodal_parts = [{
            "inline_data": {
                "mime_type": "image/png",
                "data": "aW1hZ2VkYXRh"
            }
        }]
        formatted = _format_openrouter_messages(messages, "You are Brainy.", multimodal_parts)
        last_msg = formatted[-1]
        self.assertIsInstance(last_msg["content"], list)
        self.assertEqual(last_msg["content"][0]["type"], "text")
        self.assertEqual(last_msg["content"][1]["type"], "image_url")
        self.assertEqual(
            last_msg["content"][1]["image_url"]["url"],
            "data:image/png;base64,aW1hZ2VkYXRh"
        )

    # ── 7. Safe Error Handling When Vision Fails ────────────────────

    def test_vision_failure_error_message(self):
        png_bytes = _create_sample_image("PNG")
        meta = save_file(
            file_bytes=png_bytes,
            filename="diagram.png",
            mime_type="image/png",
            user_id=self.user_a_id
        )
        file_id = meta["file_id"]

        with patch("study_bot.ai_call", side_effect=RuntimeError("Vision provider API quota exceeded")):
            res = self.client.post(
                "/api/chat/send",
                json={
                    "message": "Explain this diagram",
                    "file_id": file_id
                },
                headers={"Authorization": f"Bearer {self.token_a}"}
            )
            self.assertEqual(res.status_code, 502)
            data = res.get_json()
            self.assertEqual(
                data["message"],
                "Image analysis is temporarily unavailable. Please try again later."
            )

    # ── 8. Chat History Attachment Persistence ──────────────────────

    def test_attachment_persists_in_chat_history(self):
        png_bytes = _create_sample_image("PNG")
        meta = save_file(
            file_bytes=png_bytes,
            filename="saved_figure.png",
            mime_type="image/png",
            user_id=self.user_a_id
        )
        file_id = meta["file_id"]

        # Create session owned by user_a
        sess = sb_create_session(self.user_a_id, "Vision Session")
        session_id = sess["id"]

        # Insert user message with attachment_id
        sb_insert_message(
            session_id=session_id,
            role="user",
            content="Can you explain this chart?",
            user_id=self.user_a_id,
            attachment_id=file_id
        )

        # Retrieve messages
        msgs = sb_get_messages(session_id, user_id=self.user_a_id)
        self.assertTrue(len(msgs) >= 1)
        user_msg = msgs[0]
        self.assertEqual(user_msg.get("attachment_id"), file_id)
        self.assertEqual(user_msg.get("image"), f"/api/files/{file_id}/preview")


if __name__ == "__main__":
    unittest.main()
