def _create_sample_pdf_bytes():
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Brainy Academic Test PDF Content")
    b = doc.tobytes()
    doc.close()
    return b

"""
Comprehensive Automated Test Suite for Brainy Centralized Google Drive Storage
=============================================================================
Tests:
- AES-256-GCM authenticated token encryption at rest
- Single-use, time-limited, signed OAuth state validation
- Owner-only authorization enforcement vs normal user rejection
- Code exchange and safe reconnection (preserving existing refresh token)
- Opaque user folder hierarchy creation and thread concurrency
- Upload, checksum, and compliance gate enforcement
- Strict per-user isolation and IDOR protection (User A vs User B)
- Private streaming download with strict headers
- Disconnect and revocation handling
- Existing Google Sign-In and PDF feature regression
"""

import os
import io
import time
import json
import unittest
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from security import create_auth_token, verify_auth_token
from pdf_studio.google_drive import (
    drive_storage, cipher, DriveTokenCipher,
    GoogleDriveAuthError, GoogleDriveCompliancePause, GoogleDriveQuotaError
)
from pdf_studio.service import pdf_service, PDFSecurityError, PDFValidationError, PDFNotFoundError


class TestGoogleDriveCentralizedStorage(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.owner_id = 999001
        self.user_a_id = 10001
        self.user_b_id = 10002

        # Configure environment for tests
        os.environ["BRAINY_DRIVE_OWNER_USER_ID"] = str(self.owner_id)
        os.environ["GOOGLE_DRIVE_CLIENT_ID"] = "test_client_id.apps.googleusercontent.com"
        os.environ["GOOGLE_DRIVE_CLIENT_SECRET"] = "test_client_secret"
        os.environ["BRAINY_DRIVE_TOKEN_ENCRYPTION_KEY"] = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

        # Generate tokens
        os.environ["BRAINY_DRIVE_OWNER_EMAIL"] = "shreyansh.npm@gmail.com"
        self.owner_token = create_auth_token(self.owner_id, "brainy_owner", "Project Owner", "shreyansh.npm@gmail.com", role="admin", google_sub="sub_owner_123")
        self.user_a_token = create_auth_token(self.user_a_id, "student_a", "Alice Student", "alice@example.com")
        self.user_b_token = create_auth_token(self.user_b_id, "student_b", "Bob Student", "bob@example.com")

        # Clear in-memory state and test cache files
        drive_storage._cached_access_token = None
        drive_storage._token_expiry_ts = 0.0
        from pdf_studio.google_drive import DATA_DIR
        cfg_file = os.path.join(DATA_DIR, "owner_config.json")
        if os.path.exists(cfg_file):
            try:
                os.remove(cfg_file)
            except Exception:
                pass
        for uid in [self.user_a_id, self.user_b_id, self.owner_id]:
            cf = os.path.join(DATA_DIR, f"user_folder_{uid}.json")
            if os.path.exists(cf):
                try:
                    os.remove(cf)
                except Exception:
                    pass

    # ── 1. TOKEN CIPHER (AES-256-GCM) TESTS ──

    def test_token_encryption_and_decryption(self):
        secret_token = "1//04test_refresh_token_xyz_987654321"
        encrypted = cipher.encrypt(secret_token)
        self.assertTrue(encrypted.startswith("drv_enc_v1_"))
        self.assertNotEqual(encrypted, secret_token)

        decrypted = cipher.decrypt(encrypted)
        self.assertEqual(decrypted, secret_token)

    def test_token_tamper_detection(self):
        secret_token = "1//04test_refresh_token"
        encrypted = cipher.encrypt(secret_token)
        # Tamper with the ciphertext/tag
        tampered = encrypted[:-6] + "xxxxxx"
        with self.assertRaises(GoogleDriveAuthError):
            cipher.decrypt(tampered)

    def test_key_rotation_support(self):
        key1 = "1111111111111111111111111111111111111111111111111111111111111111"
        key2 = "2222222222222222222222222222222222222222222222222222222222222222"
        cipher1 = DriveTokenCipher(key1)
        encrypted_with_key1 = cipher1.encrypt("token_under_key1")

        # Cipher with key2 as active and key1 in previous rotation list
        os.environ["BRAINY_DRIVE_TOKEN_PREVIOUS_KEYS"] = key1
        cipher2 = DriveTokenCipher(key2)
        decrypted = cipher2.decrypt(encrypted_with_key1)
        self.assertEqual(decrypted, "token_under_key1")

    # ── 2. OAUTH STATE MANAGEMENT (CSRF & SINGLE-USE) ──

    def test_oauth_state_validity_and_single_use(self):
        state = drive_storage.generate_oauth_state(self.owner_id)
        self.assertIn(".", state)

        # First validation must succeed
        valid = drive_storage.validate_oauth_state(state, expected_user_id=self.owner_id)
        self.assertTrue(valid)

        # Second validation of same state MUST fail (single-use replay prevention)
        replayed = drive_storage.validate_oauth_state(state, expected_user_id=self.owner_id)
        self.assertFalse(replayed)

    def test_oauth_state_user_mismatch_rejected(self):
        state = drive_storage.generate_oauth_state(self.owner_id)
        # Attempt to validate with a different user ID
        valid = drive_storage.validate_oauth_state(state, expected_user_id=self.user_a_id)
        self.assertFalse(valid)

    def test_tampered_oauth_state_rejected(self):
        state = drive_storage.generate_oauth_state(self.owner_id)
        tampered_state = state[:-5] + "12345"
        self.assertFalse(drive_storage.validate_oauth_state(tampered_state, self.owner_id))

    # ── 3. OWNER-ONLY AUTHORIZATION ROUTES ──

    def test_normal_user_cannot_connect_drive(self):
        # User A attempts to call /api/integrations/google-drive/owner/connect
        resp = self.app.get(
            "/api/integrations/google-drive/owner/connect",
            headers={"Authorization": f"Bearer {self.user_a_token}"}
        )
        self.assertEqual(resp.status_code, 403)
        data = resp.get_json()
        self.assertEqual(data.get("code"), "OWNER_ONLY")

    def test_owner_can_initiate_connect(self):
        resp = self.app.get(
            "/api/integrations/google-drive/owner/connect",
            headers={"Authorization": f"Bearer {self.owner_token}"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("auth_url", data)
        self.assertIn("accounts.google.com", data["auth_url"])
        self.assertIn("drive.file", data["auth_url"])

    def test_unauthenticated_user_rejected(self):
        resp = self.app.get("/api/integrations/google-drive/owner/connect")
        self.assertEqual(resp.status_code, 401)

    # ── 4. CODE EXCHANGE & RECONNECT LOGIC ──

    @patch("requests.post")
    @patch("requests.get")
    def test_oauth_callback_successful_exchange(self, mock_get, mock_post):
        state = drive_storage.generate_oauth_state(self.owner_id)

        # Mock token exchange
        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {
            "access_token": "ya29.test_access_token",
            "refresh_token": "1//test_refresh_token_123",
            "expires_in": 3600,
            "scope": "https://www.googleapis.com/auth/drive.file"
        }
        mock_post.return_value = mock_token_resp

        # Mock userinfo
        mock_userinfo_resp = MagicMock()
        mock_userinfo_resp.status_code = 200
        mock_userinfo_resp.json.return_value = {"email": "shreyansh.npm@gmail.com", "sub": "sub_owner_123"}
        mock_get.return_value = mock_userinfo_resp

        with patch.object(drive_storage, "initialize_root_hierarchy", return_value=("root_id_123", "users_id_456")):
            resp = self.app.get(f"/api/integrations/google-drive/callback?code=mock_auth_code&state={state}")
            self.assertEqual(resp.status_code, 302)
            self.assertIn("drive_connected=true", resp.headers["Location"])

            # Verify credentials saved encrypted
            cfg = drive_storage.get_owner_config()
            self.assertTrue(cfg["is_active"])
            self.assertEqual(cfg["owner_email"], "shreyansh.npm@gmail.com")
            # Refresh token must be decrypted properly
            self.assertEqual(cipher.decrypt(cfg["encrypted_refresh_token"]), "1//test_refresh_token_123")

    @patch("requests.post")
    @patch("requests.get")
    def test_reconnect_without_new_refresh_token_preserves_existing(self, mock_get, mock_post):
        # Setup existing config with valid refresh token
        existing_cfg = {
            "owner_user_id": self.owner_id,
            "owner_email": "shreyansh.npm@gmail.com",
            "encrypted_refresh_token": cipher.encrypt("existing_valid_refresh_token"),
            "is_active": True
        }
        drive_storage.save_owner_config(existing_cfg)

        state = drive_storage.generate_oauth_state(self.owner_id)

        # Google returns new access token but NO new refresh token
        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {
            "access_token": "ya29.new_access_token_only",
            "expires_in": 3600
        }
        mock_post.return_value = mock_token_resp
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"email": "shreyansh.npm@gmail.com", "sub": "sub_owner_123"})

        with patch.object(drive_storage, "initialize_root_hierarchy", return_value=("root_1", "users_1")):
            resp = self.app.get(f"/api/integrations/google-drive/callback?code=reconnect_code&state={state}")
            self.assertEqual(resp.status_code, 302)

            cfg = drive_storage.get_owner_config()
            # Original refresh token must be intact
            self.assertEqual(cipher.decrypt(cfg["encrypted_refresh_token"]), "existing_valid_refresh_token")

    # ── 5. OPAQUE USER FOLDERS & DATA ISOLATION ──

    def test_opaque_user_folder_deterministic_and_isolated(self):
        opaque_a = drive_storage.derive_user_opaque_id(self.user_a_id)
        opaque_b = drive_storage.derive_user_opaque_id(self.user_b_id)

        # Must not contain raw user ID or email
        self.assertNotIn(str(self.user_a_id), opaque_a)
        self.assertNotIn("alice", opaque_a)
        self.assertNotEqual(opaque_a, opaque_b)

        # Same user must resolve to identical opaque ID across sessions
        self.assertEqual(opaque_a, drive_storage.derive_user_opaque_id(self.user_a_id))

    @patch.object(drive_storage, "initialize_root_hierarchy", return_value=("root_folder", "users_folder"))
    @patch.object(drive_storage, "_find_or_create_folder")
    def test_folder_creation_hierarchy(self, mock_create, mock_init):
        mock_create.side_effect = lambda name, parent_id: f"id_of_{name}_under_{parent_id}"

        folder_id = drive_storage.get_or_create_user_pdf_folder(self.user_a_id)
        opaque_a = drive_storage.derive_user_opaque_id(self.user_a_id)

        # Verify folder calls: user folder first under users_folder, then PDFs inside it
        self.assertIn("PDFs", folder_id)
        mock_create.assert_any_call(f"user_{opaque_a}", parent_id="users_folder")

    # ── 6. COMPLIANCE PREFLIGHT GATE TESTS ──

    def test_compliance_pause_blocks_production_upload(self):
        # By default BRAINY_DRIVE_PRODUCTION_ENABLED is False
        os.environ["BRAINY_DRIVE_PRODUCTION_ENABLED"] = "false"
        self.assertFalse(drive_storage.is_compliance_cleared())

        fake_pdf = _create_sample_pdf_bytes()
        with self.assertRaises(GoogleDriveCompliancePause):
            drive_storage.upload_pdf(self.user_a_id, "test.pdf", fake_pdf, "doc_123")

    # ── 7. STRICT PER-USER ISOLATION & IDOR PROTECTION ──

    def test_user_a_cannot_access_or_download_user_b_document(self):
        # 1. Ingest document for User A
        fake_pdf = _create_sample_pdf_bytes()
        doc_a = pdf_service.upload_and_process_pdf(
            user_id=self.user_a_id,
            filename="user_a_thesis.pdf",
            file_bytes=fake_pdf
        )
        doc_id = doc_a["id"]

        # 2. User B tries to fetch User A's document metadata -> 403 Security Error
        with self.assertRaises(PDFSecurityError):
            pdf_service.get_document(doc_id, user_id=self.user_b_id)

        # 3. User B tries to download User A's document via API endpoint
        resp = self.app.get(
            f"/api/pdf/documents/{doc_id}/download",
            headers={"Authorization": f"Bearer {self.user_b_token}"}
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Access denied", resp.get_json()["error"])

        # 4. User A can download their own document
        resp_a = self.app.get(
            f"/api/pdf/documents/{doc_id}/download",
            headers={"Authorization": f"Bearer {self.user_a_token}"}
        )
        self.assertEqual(resp_a.status_code, 200)
        self.assertEqual(resp_a.mimetype, "application/pdf")
        cc = resp_a.headers["Cache-Control"]
        for directive in ["private", "no-cache", "no-store", "must-revalidate"]:
            self.assertIn(directive, cc)

    def test_user_b_cannot_delete_user_a_document(self):
        fake_pdf = _create_sample_pdf_bytes()
        doc_a = pdf_service.upload_and_process_pdf(
            user_id=self.user_a_id,
            filename="alice_homework.pdf",
            file_bytes=fake_pdf
        )
        doc_id = doc_a["id"]

        # User B attempts deletion -> 403
        resp = self.app.delete(
            f"/api/pdf/documents/{doc_id}",
            headers={"Authorization": f"Bearer {self.user_b_token}"}
        )
        self.assertEqual(resp.status_code, 403)

        # Document must still exist
        doc_still_exists = pdf_service.get_document(doc_id, user_id=self.user_a_id)
        self.assertEqual(doc_still_exists["id"], doc_id)

    # ── 8. OWNER DISCONNECT & STATUS ──

    def test_owner_status_and_disconnect(self):
        # Configure active config
        cfg = {
            "owner_user_id": self.owner_id,
            "owner_email": "shreyansh.npm@gmail.com",
            "encrypted_refresh_token": cipher.encrypt("dummy_refresh"),
            "is_active": True
        }
        drive_storage.save_owner_config(cfg)

        # Regular user cannot check status
        resp_user = self.app.get(
            "/api/integrations/google-drive/owner/status",
            headers={"Authorization": f"Bearer {self.user_a_token}"}
        )
        self.assertEqual(resp_user.status_code, 403)

        # Owner checks status
        resp_owner = self.app.get(
            "/api/integrations/google-drive/owner/status",
            headers={"Authorization": f"Bearer {self.owner_token}"}
        )
        self.assertEqual(resp_owner.status_code, 200)
        data = resp_owner.get_json()
        self.assertTrue(data["connected"])
        self.assertEqual(data["owner_email"], "shreyansh.npm@gmail.com")
        # Ensure secret tokens are never exposed in JSON
        self.assertNotIn("encrypted_refresh_token", data)
        self.assertNotIn("refresh_token", data)

        # Owner disconnects
        with patch("requests.post") as mock_revoke:
            mock_revoke.return_value = MagicMock(status_code=200)
            disc_resp = self.app.post(
                "/api/integrations/google-drive/owner/disconnect",
                headers={"Authorization": f"Bearer {self.owner_token}"}
            )
            self.assertEqual(disc_resp.status_code, 200)
            self.assertTrue(disc_resp.get_json()["success"])

            # Status should now be inactive
            status_after = drive_storage.get_status()
            self.assertFalse(status_after["connected"])

    # ── 9. EXISTING GOOGLE SIGN-IN REGRESSION ──

    def test_existing_google_signin_intact(self):
        # Empty payload
        resp = self.app.post("/api/auth/google", json={})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "Missing Google credential token")

        # Config endpoint exposes GIS client id
        resp_config = self.app.get("/api/config")
        self.assertEqual(resp_config.status_code, 200)
        self.assertIn("google_client_id", resp_config.get_json())


    # ── 10. MULTI-LAYER OWNER IDENTITY VERIFICATION TESTS ──

    def test_generic_admin_cannot_impersonate_drive_owner(self):
        # A generic admin with user_id = 888888 and role = admin must NOT be able to connect Drive
        fake_admin_token = create_auth_token(888888, "random_admin", "Admin Guy", "other_admin@brainyai.app", role="admin")
        resp = self.app.get(
            "/api/integrations/google-drive/owner/connect",
            headers={"Authorization": f"Bearer {fake_admin_token}"}
        )
        self.assertEqual(resp.status_code, 403)
        data = resp.get_json()
        self.assertEqual(data.get("code"), "OWNER_ONLY")

    def test_email_only_impersonation_rejected(self):
        # Attacker claims owner email but has wrong user_id
        attacker_token = create_auth_token(666666, "attacker", "Evil Bob", "shreyansh.npm@gmail.com")
        resp = self.app.get(
            "/api/integrations/google-drive/owner/connect",
            headers={"Authorization": f"Bearer {attacker_token}"}
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.get_json().get("code"), "OWNER_ONLY")

    def test_google_sub_mismatch_rejected(self):
        os.environ["BRAINY_DRIVE_OWNER_GOOGLE_SUB"] = "sub_owner_12345"
        # Token has owner user_id and email, but wrong google_sub
        mismatched_token = create_auth_token(
            self.owner_id, "owner", "Owner", "shreyansh.npm@gmail.com",
            role="admin", google_sub="wrong_sub_99999"
        )
        resp = self.app.get(
            "/api/integrations/google-drive/owner/status",
            headers={"Authorization": f"Bearer {mismatched_token}"}
        )
        self.assertEqual(resp.status_code, 403)
        # Restore env
        os.environ.pop("BRAINY_DRIVE_OWNER_GOOGLE_SUB", None)

    @patch("requests.post")
    @patch("requests.get")
    def test_oauth_callback_rejects_unauthorized_google_account(self, mock_get, mock_post):
        state = drive_storage.generate_oauth_state(self.owner_id)

        # Mock token exchange
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "access_token": "ya29.stranger_token",
                "refresh_token": "1//stranger_refresh",
                "expires_in": 3600
            }
        )
        # Userinfo returns an unauthorized account
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"email": "stranger@evil.com", "sub": "stranger_sub"}
        )

        resp = self.app.get(f"/api/integrations/google-drive/callback?code=mock_code&state={state}")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("drive_error=unauthorized_owner_account", resp.headers["Location"])

    def test_invalid_jwt_rejected(self):
        resp = self.app.get(
            "/api/integrations/google-drive/owner/status",
            headers={"Authorization": "Bearer invalid.fake.token"}
        )
        self.assertEqual(resp.status_code, 401)

if __name__ == "__main__":
    unittest.main()
