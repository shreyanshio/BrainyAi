"""
Comprehensive Test Suite for Brainy Telegram Bot Upgrade and Web Image Integration:
1. Language Intelligence (30+ test cases covering English, Hinglish, Devanagari Hindi, Gujarati, Overrides)
2. Safe Telegram Message Chunking & Code Fence Protection
3. Unified 5-Image Quota Engine & Account Linking
4. Group Chat Isolation & Media Restrictions
5. Web Image Attachment Schema Verification
"""

import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from ai_routing.language import detect_language, apply_language_directive
from ai_routing.quota import (
    IMAGE_FREE_LIMIT,
    get_user_image_quota,
    consume_user_image_quota,
    refund_user_image_quota,
    generate_telegram_link_code,
    link_telegram_to_web_account,
    resolve_effective_identity,
    _in_memory_quotas,
    _in_memory_link_codes,
    _in_memory_user_links,
)
from study_bot import safe_split_telegram_message


class TestLanguageIntelligence(unittest.TestCase):
    """Verifies deterministic language detection and prompt directive application across 30+ test cases."""

    def test_english_queries(self):
        english_cases = [
            "Explain Newton's third law of motion.",
            "How does backpropagation work in deep neural networks?",
            "What is the difference between TCP and UDP?",
            "Can you write a binary search algorithm in Python?",
            "Define photosynthesis and describe the light reactions.",
            "What are the main causes of World War 1?",
            "How do React hooks differ from class component lifecycle methods?",
            "Solve the quadratic equation 2x^2 + 5x - 3 = 0.",
        ]
        for query in english_cases:
            with self.subTest(query=query):
                profile = detect_language(query)
                self.assertEqual(profile.language, "english", f"Expected 'english' for '{query}', got '{profile.language}'")
                directive = apply_language_directive("Base prompt", profile)
                self.assertIn("Detected Language: ENGLISH", directive)
                self.assertIn("Respond in clear, accurate, natural English", directive)

    def test_hinglish_roman_queries(self):
        hinglish_cases = [
            "bhai newton ka third law simple words me explain kar do",
            "kya mujhe physics ke formulas ki list mil sakti hai?",
            "yeh concept samajh nahi aaya, thoda easily samjhao",
            "kal mera exam hai, revision kaise karu?",
            "machine learning me overfitting kya hota hai aur isse kaise bache?",
            "photosynthesis ka process step by step batana bhai",
            "react me useState hook kaise use karte hai example ke sath?",
            "bhai ek simple study timetable bana de 12th board ke liye",
            "integration ke important question bata do na",
            "ye code run kyu nahi ho raha, error solve kar do",
        ]
        for query in hinglish_cases:
            with self.subTest(query=query):
                profile = detect_language(query)
                self.assertEqual(profile.language, "hinglish", f"Expected 'hinglish' for '{query}', got '{profile.language}'")
                directive = apply_language_directive("Base prompt", profile)
                self.assertIn("Detected Language: HINGLISH", directive)
                self.assertIn("Latin/Roman script", directive)
                self.assertIn("NEVER translate into formal Hindi or output Devanagari script", directive)
                self.assertIn("standard English", directive)

    def test_devanagari_hindi_queries(self):
        hindi_cases = [
            "न्यूटन के गति के तीसरे नियम को समझाइए।",
            "प्रकाश संश्लेषण क्या है और यह पौधों के लिए क्यों आवश्यक है?",
            "कंप्यूटर नेटवर्किंग में प्रोटोकॉल का क्या अर्थ है?",
            "गणित में समाकलन के मुख्य सूत्र कौन से हैं?",
        ]
        for query in hindi_cases:
            with self.subTest(query=query):
                profile = detect_language(query)
                self.assertEqual(profile.language, "hindi", f"Expected 'hindi' for '{query}', got '{profile.language}'")
                directive = apply_language_directive("Base prompt", profile)
                self.assertIn("Detected Language: HINDI", directive)
                self.assertIn("Devanagari script", directive)

    def test_gujarati_queries(self):
        gujarati_cases = [
            "મને ન્યુટનના નિયમો સમજાવો.",
            "પ્રકાશસંશ્લેષણ એટલે શું? વિગતવાર સમજાવો.",
            "ગણિતમાં ત્રિકોણમિતિના મહત્વપૂર્ણ સૂત્રો કયા છે?",
            "mane aa physics no concept samjavone please",
            "kem cho bhai, mane revision ma madad karo",
        ]
        for query in gujarati_cases:
            with self.subTest(query=query):
                profile = detect_language(query)
                self.assertEqual(profile.language, "gujarati", f"Expected 'gujarati' for '{query}', got '{profile.language}'")
                directive = apply_language_directive("Base prompt", profile)
                self.assertIn("Detected Language: GUJARATI", directive)

    def test_explicit_language_overrides(self):
        override_cases = [
            ("bhai mujhe yeh concept english me explain karo please", "english"),
            ("Please answer strictly in English.", "english"),
            ("Can you explain this in Hindi?", "hindi"),
            ("mujhe hindi me samjhao", "hindi"),
            ("explain this topic in gujarati", "gujarati"),
        ]
        for query, expected_lang in override_cases:
            with self.subTest(query=query):
                profile = detect_language(query)
                self.assertEqual(profile.language, expected_lang, f"Expected override '{expected_lang}' for '{query}', got '{profile.language}'")


class TestSafeSplitTelegramMessage(unittest.TestCase):
    """Verifies that long messages are cleanly split without breaking code blocks."""

    def test_short_message_not_split(self):
        text = "Hello, this is a normal length message."
        chunks = safe_split_telegram_message(text, max_chunk=100)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], text)

    def test_long_message_splits_without_breaking_code_block(self):
        code_block = "\n".join([f"line_{i} = {i} * 2" for i in range(50)])
        long_text = f"Here is the program:\n```python\n{code_block}\n```\nDone."
        chunks = safe_split_telegram_message(long_text, max_chunk=400)
        self.assertGreater(len(chunks), 1)
        # Verify every chunk has balanced code fences
        for i, chunk in enumerate(chunks):
            fence_count = chunk.count("```")
            self.assertEqual(fence_count % 2, 0, f"Chunk {i} has unclosed code fence! Fences: {fence_count}")


class TestUnifiedImageQuotaAndLinking(unittest.TestCase):
    """Verifies shared 5-image quota, atomic consumption, refund on failure, and account linking."""

    def setUp(self):
        _in_memory_quotas.clear()
        _in_memory_link_codes.clear()
        _in_memory_user_links.clear()

    def test_initial_image_quota(self):
        quota = get_user_image_quota(12345)
        self.assertEqual(quota["limit"], 5)
        self.assertEqual(quota["used"], 0)
        self.assertEqual(quota["remaining"], 5)
        self.assertFalse(quota["is_linked"])

    def test_consume_quota_up_to_5_and_block_sixth(self):
        user_id = 99901
        for i in range(1, 6):
            allowed, remaining, eff_id = consume_user_image_quota(user_id)
            self.assertTrue(allowed)
            self.assertEqual(remaining, 5 - i)
            self.assertEqual(eff_id, str(user_id))

        # 6th request must be rejected
        allowed, remaining, eff_id = consume_user_image_quota(user_id)
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)

    def test_refund_on_failure(self):
        user_id = 99902
        allowed, remaining, eff_id = consume_user_image_quota(user_id)
        self.assertTrue(allowed)
        self.assertEqual(remaining, 4)

        # Failure occurs -> refund
        refund_user_image_quota(eff_id)
        quota = get_user_image_quota(user_id)
        self.assertEqual(quota["remaining"], 5)
        self.assertEqual(quota["used"], 0)

    def test_account_linking_synchronizes_quota(self):
        web_user_id = "web_user_abc"
        tg_user_id = 88801

        # Web user uses 2 images
        consume_user_image_quota(web_user_id)
        consume_user_image_quota(web_user_id)
        self.assertEqual(get_user_image_quota(web_user_id)["remaining"], 3)

        # Generate link code from Web
        code = generate_telegram_link_code(web_user_id)
        self.assertEqual(len(code), 6)

        # Telegram user links account
        success, linked_id = link_telegram_to_web_account(tg_user_id, code)
        self.assertTrue(success)
        self.assertEqual(linked_id, web_user_id)

        # Telegram user quota is now unified with Web user
        tg_quota = get_user_image_quota(tg_user_id)
        self.assertTrue(tg_quota["is_linked"])
        self.assertEqual(tg_quota["remaining"], 3)
        self.assertEqual(tg_quota["used"], 2)

        # Consuming from Telegram reflects on Web
        allowed, rem, _ = consume_user_image_quota(tg_user_id)
        self.assertTrue(allowed)
        self.assertEqual(rem, 2)
        self.assertEqual(get_user_image_quota(web_user_id)["remaining"], 2)


class TestGroupMediaAndChatRestrictions(unittest.TestCase):
    """Verifies group media rules: /image and /voice required; uncommanded media ignored."""

    def test_group_image_without_command_ignored(self):
        import study_bot
        # Mock group update with photo but no /image caption
        update = MagicMock()
        update.effective_chat.type = "supergroup"
        update.message.caption = "Just a photo in group"
        context = MagicMock()

        # Run handle_image
        import asyncio
        loop = asyncio.new_event_loop()
        with patch.object(study_bot, "_process_image_analysis", new_callable=AsyncMock) as mock_analyze:
            loop.run_until_complete(study_bot.handle_image(update, context))
            mock_analyze.assert_not_called()
        loop.close()

    def test_group_voice_without_command_ignored(self):
        import study_bot
        update = MagicMock()
        update.effective_chat.type = "supergroup"
        update.message.voice = MagicMock()
        context = MagicMock()

        import asyncio
        loop = asyncio.new_event_loop()
        with patch.object(study_bot, "process_query", new_callable=AsyncMock) as mock_pq:
            loop.run_until_complete(study_bot.handle_voice(update, context))
            mock_pq.assert_not_called()
        loop.close()


class TestWebImageIntegrationSchema(unittest.TestCase):
    """Verifies that frontend API payload and types preserve image parameter."""

    def test_frontend_api_ts_contains_image_payload(self):
        with open("lib/api.ts", "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("image: req.image,", content)
        self.assertIn("web_search: req.web_search,", content)

    def test_frontend_types_contains_image_field(self):
        with open("types/api.ts", "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("image?: string", content)


if __name__ == "__main__":
    unittest.main()
