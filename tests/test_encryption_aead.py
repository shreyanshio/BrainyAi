"""
BrainyAi - Standard AEAD (AES-256-GCM) & Legacy Migration Test Suite
Verifies:
- Standard AES-256-GCM encryption/decryption roundtrip (enc_v2_)
- Unicode, mathematical symbols, long prose, and empty payloads
- Rejection of tampered ciphertext and modified authentication tags
- Dedicated CHAT_ENCRYPTION_KEY usage
- Multi-key rotation support via CHAT_ENCRYPTION_PREVIOUS_KEYS
- Backward compatibility with historical hsh_v1_ records
- Non-destructive migration utility migrate_record_to_v2()
"""

import os
import re
import unittest
import base64
import hashlib
import hmac
from unittest.mock import patch

import app


def _create_legacy_v1_record(text: str, secret: str) -> str:
    """Helper to generate an exact hsh_v1_ record for migration testing."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, 50000, dklen=32)
    text_bytes = text.encode("utf-8")
    keystream = bytearray()
    counter = 0
    while len(keystream) < len(text_bytes):
        keystream.extend(hmac.new(key, counter.to_bytes(4, "big"), hashlib.sha256).digest())
        counter += 1
    ciphertext = bytes(a ^ b for a, b in zip(text_bytes, keystream[:len(text_bytes)]))
    mac = hmac.new(key, ciphertext, hashlib.sha256).digest()[:16]
    encoded = base64.urlsafe_b64encode(salt + mac + ciphertext).decode("ascii")
    return f"hsh_v1_{encoded}"


class TestAEADEncryption(unittest.TestCase):

    def setUp(self):
        # Ensure clean environment for each test
        self.patcher = patch.dict(os.environ, {
            "CHAT_ENCRYPTION_KEY": "test-super-secret-aead-key-2026-xyz",
            "CHAT_ENCRYPTION_PREVIOUS_KEYS": "",
            "CHAT_ENCRYPTION_PREVIOUS_KEY": "",
            "AUTH_SECRET_KEY": "test-auth-signing-key-independent"
        })
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_aead_v2_roundtrip_basic(self):
        """Plaintext encrypted with AES-256-GCM can be accurately decrypted."""
        original = "What is the second derivative of e^(2x)?"
        encrypted = app.mask_secure_hash(original)
        self.assertTrue(encrypted.startswith("enc_v2_"))
        self.assertNotIn("derivative", encrypted)

        decrypted = app.unmask_secure_hash(encrypted)
        self.assertEqual(decrypted, original)

    def test_aead_v2_unique_nonce_per_operation(self):
        """Encrypting the exact same text twice must produce different ciphertexts due to fresh nonces."""
        text = "Constant message content"
        enc1 = app.mask_secure_hash(text)
        enc2 = app.mask_secure_hash(text)
        self.assertNotEqual(enc1, enc2)
        self.assertEqual(app.unmask_secure_hash(enc1), text)
        self.assertEqual(app.unmask_secure_hash(enc2), text)

    def test_aead_v2_unicode_and_mathematics(self):
        """Verifies complex Unicode, KaTeX notation, and emojis decrypt perfectly."""
        text = "Euler's Identity: e^{i\\pi} + 1 = 0 \u2248 \u222b_{0}^{\\infty} x^2 dx \U0001F9E0 \U0001F525"
        encrypted = app.mask_secure_hash(text)
        self.assertEqual(app.unmask_secure_hash(encrypted), text)

    def test_aead_v2_empty_string_handling(self):
        """Empty string returns unmodified without error."""
        self.assertEqual(app.mask_secure_hash(""), "")
        self.assertEqual(app.unmask_secure_hash(""), "")

    def test_aead_v2_tampered_ciphertext_fails_closed(self):
        """Tampering with a single bit in the ciphertext or tag fails authentication cleanly."""
        text = "Sensitive student diagnostic test"
        encrypted = app.mask_secure_hash(text)
        
        # Tamper near the middle of payload
        prefix = "enc_v2_"
        payload = list(encrypted[len(prefix):])
        payload[15] = 'A' if payload[15] != 'A' else 'B'
        tampered = prefix + "".join(payload)

        with self.assertRaises(app.StoredChatContentUnavailable) as cm:
            app.unmask_secure_hash(tampered)
        self.assertNotIn(tampered, str(cm.exception))

    def test_aead_v2_truncated_payload_fails_closed(self):
        """Truncated payload missing the required nonce or 16-byte tag fails closed."""
        truncated = "enc_v2_" + base64.urlsafe_b64encode(b"short").decode("ascii")
        with self.assertRaises(app.StoredChatContentUnavailable):
            app.unmask_secure_hash(truncated)

    def test_aead_v2_key_rotation_via_previous_keys(self):
        """Payloads encrypted under an older key can be decrypted after key rotation."""
        old_key = "old-encryption-key-season-1"
        new_key = "new-encryption-key-season-2"

        with patch.dict(os.environ, {"CHAT_ENCRYPTION_KEY": old_key, "CHAT_ENCRYPTION_PREVIOUS_KEYS": ""}):
            stored = app.mask_secure_hash("Encrypted with old key")

        # Now rotate to new_key, keeping old_key in previous list
        with patch.dict(os.environ, {
            "CHAT_ENCRYPTION_KEY": new_key,
            "CHAT_ENCRYPTION_PREVIOUS_KEYS": f"legacy-key,{old_key},unused-key"
        }):
            decrypted = app.unmask_secure_hash(stored)
            self.assertEqual(decrypted, "Encrypted with old key")

    def test_legacy_hsh_v1_backward_compatibility(self):
        """Historical records using hsh_v1_ format can still be decrypted seamlessly."""
        secret = "historical-auth-secret-key"
        legacy_record = _create_legacy_v1_record("Old chat message from previous semester", secret)
        self.assertTrue(legacy_record.startswith("hsh_v1_"))

        with patch.dict(os.environ, {
            "AUTH_SECRET_KEY": secret,
            "CHAT_ENCRYPTION_KEY": "new-aead-key"
        }):
            decrypted = app.unmask_secure_hash(legacy_record)
            self.assertEqual(decrypted, "Old chat message from previous semester")

    def test_migration_utility_converts_v1_to_v2(self):
        """migrate_record_to_v2 converts hsh_v1_ to enc_v2_ with verified round-trip integrity."""
        secret = "historical-auth-secret-key"
        original_text = "Physics mechanics notes: F = ma"
        legacy_record = _create_legacy_v1_record(original_text, secret)

        with patch.dict(os.environ, {
            "AUTH_SECRET_KEY": secret,
            "CHAT_ENCRYPTION_KEY": "new-aead-key"
        }):
            migrated_val, was_migrated = app.migrate_record_to_v2(legacy_record)
            self.assertTrue(was_migrated)
            self.assertTrue(migrated_val.startswith("enc_v2_"))
            self.assertNotEqual(migrated_val, legacy_record)
            self.assertEqual(app.unmask_secure_hash(migrated_val), original_text)

    def test_migration_utility_skips_already_migrated(self):
        """migrate_record_to_v2 is a no-op on already migrated enc_v2_ records."""
        v2_record = app.mask_secure_hash("Already modern")
        val, was_migrated = app.migrate_record_to_v2(v2_record)
        self.assertFalse(was_migrated)
        self.assertEqual(val, v2_record)


if __name__ == "__main__":
    unittest.main()
