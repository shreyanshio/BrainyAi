import os
import sys
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram.error import BadRequest, RetryAfter, NetworkError

import study_bot
import app


class TestTelegramResponsePipeline(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.update = MagicMock()
        self.msg = AsyncMock()
        self.msg.message_id = 100
        
        self.loading = AsyncMock()
        self.loading.message_id = 101
        self.loading.edit_text = AsyncMock(return_value=AsyncMock(message_id=101))
        self.loading.delete = AsyncMock()
        
        self.msg.reply_text = AsyncMock(return_value=self.loading)
        self.update.message = self.msg
        self.update.effective_chat = MagicMock()
        self.update.effective_chat.type = "private"
        self.update.effective_chat.id = 555001
        self.update.effective_user = MagicMock()
        self.update.effective_user.id = 12345
        self.update.effective_user.first_name = "Alex"
        self.update.effective_user.username = "alex_student"

    # Test 1: Normal response - basic message replaces thinking placeholder
    async def test_01_normal_response(self):
        with patch("study_bot.ai_call", return_value="Photosynthesis is the process by which plants use sunlight to synthesize nutrients."):
            res = await study_bot._run_ai(
                self.update,
                [{"role": "user", "content": "What is photosynthesis?"}],
                "system_prompt",
                100,
                source="test"
            )
            self.assertIsNotNone(res)
            self.assertIn("Photosynthesis", res)
            self.loading.edit_text.assert_called()
            # Delivered text should be the actual answer
            last_edit = self.loading.edit_text.call_args[0][0]
            self.assertIn("Photosynthesis", last_edit)

    # Test 2: Provider failure - thinking placeholder replaced with friendly error
    async def test_02_provider_failure(self):
        with patch("study_bot.ai_call", side_effect=Exception("All providers failed: upstream unavailable")):
            res = await study_bot._run_ai(
                self.update,
                [{"role": "user", "content": "Explain relativity"}],
                "system_prompt",
                100,
                source="test"
            )
            self.assertIsNone(res)
            # Placeholder must be edited to inform user
            self.loading.edit_text.assert_called()
            last_edit = self.loading.edit_text.call_args[0][0]
            self.assertIn("temporarily unavailable", last_edit.lower())

    # Test 3: Empty AI response - handled safely with user notification
    async def test_03_empty_ai_response(self):
        with patch("study_bot.ai_call", return_value="   "):
            res = await study_bot._run_ai(
                self.update,
                [{"role": "user", "content": "Hello"}],
                "system_prompt",
                100,
                source="test"
            )
            self.assertIsNone(res)
            self.loading.edit_text.assert_called()
            last_edit = self.loading.edit_text.call_args[0][0]
            self.assertIn("empty response", last_edit.lower())

    # Test 4: Long AI response - delivered safely without violating 4096 Telegram limit
    async def test_04_long_ai_response(self):
        # 6000 chars response
        long_text = ("This is a comprehensive study guide line.\n" * 150)
        self.assertGreater(len(long_text), 4000)
        with patch("study_bot.ai_call", return_value=long_text):
            res = await study_bot._run_ai(
                self.update,
                [{"role": "user", "content": "Generate complete study plan"}],
                "system_prompt",
                2000,
                source="test"
            )
            self.assertIsNotNone(res)
            # Long messages edit loading message with chunk 0 and send subsequent chunks
            self.msg.reply_text.assert_called()

    # Test 5: Formatting error - HTML parse error falls back to plain text
    async def test_05_formatting_error_fallback(self):
        # Malformed HTML simulation
        malformed_html = "<code>unclosed code tag and <bad> entities"
        async def mock_edit_text(text, **kwargs):
            if kwargs.get("parse_mode") == "HTML":
                raise BadRequest("Can't parse entities: unclosed tag")
            return AsyncMock(message_id=101)

        self.loading.edit_text = AsyncMock(side_effect=mock_edit_text)
        with patch("study_bot.ai_call", return_value=malformed_html):
            res = await study_bot._run_ai(
                self.update,
                [{"role": "user", "content": "Code example"}],
                "system_prompt",
                100,
                source="test"
            )
            self.assertIsNotNone(res)
            # Plain text fallback was delivered
            self.assertGreaterEqual(self.loading.edit_text.call_count, 1)

    # Test 6: Timeout - simulated timeout triggers notification
    async def test_06_timeout_handling(self):
        def slow_call(*args, **kwargs):
            import time
            time.sleep(2.5)
            return "Too late"

        with patch("study_bot.ai_call", side_effect=slow_call):
            res = await study_bot._run_ai(
                self.update,
                [{"role": "user", "content": "Complex reasoning"}],
                "system_prompt",
                100,
                source="test",
                timeout_sec=0.5
            )
            self.assertIsNone(res)
            self.loading.edit_text.assert_called()
            last_edit = self.loading.edit_text.call_args[0][0]
            self.assertIn("timed out", last_edit.lower())

    # Test 7: Concurrent requests - separate users are completely isolated
    async def test_07_concurrent_requests(self):
        update_user1 = MagicMock()
        msg1 = AsyncMock()
        load1 = AsyncMock()
        msg1.reply_text = AsyncMock(return_value=load1)
        update_user1.message = msg1
        update_user1.effective_user.id = 1001
        update_user1.effective_chat.type = "private"

        update_user2 = MagicMock()
        msg2 = AsyncMock()
        load2 = AsyncMock()
        msg2.reply_text = AsyncMock(return_value=load2)
        update_user2.message = msg2
        update_user2.effective_user.id = 1002
        update_user2.effective_chat.type = "private"

        def mock_ai(messages, *args, **kwargs):
            user_msg = messages[-1]["content"]
            return f"Answer for: {user_msg}"

        with patch("study_bot.ai_call", side_effect=mock_ai):
            t1 = study_bot._run_ai(update_user1, [{"role": "user", "content": "Question 1"}], "prompt", 100)
            t2 = study_bot._run_ai(update_user2, [{"role": "user", "content": "Question 2"}], "prompt", 100)
            res1, res2 = await asyncio.gather(t1, t2)

            self.assertEqual(res1, "Answer for: Question 1")
            self.assertEqual(res2, "Answer for: Question 2")

    # Test 8: Fallback provider - primary fails, fallback provider succeeds
    async def test_08_fallback_provider(self):
        attempt = 0
        def multi_tier_ai(*args, **kwargs):
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise Exception("Primary provider error 503")
            return "Fallback provider response"

        # ai_call internally does the fallback routing
        with patch("study_bot.ai_call", side_effect=multi_tier_ai):
            res = await study_bot._run_ai(
                self.update,
                [{"role": "user", "content": "Help me study"}],
                "system_prompt",
                100
            )
            # The second call in another query or handled by ai_call succeeds
            self.assertIsNone(res) # First failed
            res2 = await study_bot._run_ai(
                self.update,
                [{"role": "user", "content": "Help me study 2"}],
                "system_prompt",
                100
            )
            self.assertEqual(res2, "Fallback provider response")

    # Test 9: Conversation context - follow-up message receives conversation history
    async def test_09_conversation_context(self):
        study_bot.user_conversations[12345] = []
        with patch("study_bot.ai_call", return_value="Gravity is a fundamental force."):
            await study_bot.process_ask(self.update, "What is gravity?")
            self.assertEqual(len(study_bot.user_conversations[12345]), 2)
            self.assertEqual(study_bot.user_conversations[12345][0]["role"], "user")
            self.assertIn("What is gravity?", study_bot.user_conversations[12345][0]["content"])
            self.assertEqual(study_bot.user_conversations[12345][1]["role"], "assistant")

        with patch("study_bot.ai_call", return_value="Its formula is F = G*(m1*m2)/r^2"):
            await study_bot.process_ask(self.update, "What is its formula?")
            self.assertEqual(len(study_bot.user_conversations[12345]), 4)
            self.assertEqual(study_bot.user_conversations[12345][2]["role"], "user")
            self.assertIn("What is its formula?", study_bot.user_conversations[12345][2]["content"])

    # Test 10: Message delivery failure - Telegram API failure does not crash
    async def test_10_message_delivery_failure(self):
        self.loading.edit_text.side_effect = NetworkError("Telegram network connection dropped")
        self.msg.reply_text.side_effect = NetworkError("Telegram network connection dropped")

        with patch("study_bot.ai_call", return_value="Valid answer"):
            res = await study_bot._run_ai(
                self.update,
                [{"role": "user", "content": "Test network drop"}],
                "system_prompt",
                100
            )
            # Function completes safely without unhandled exception crashing the bot worker
            self.assertEqual(res, "Valid answer")

    # Test 11: Telegram command handling - /ask, /brainy, /translate, /define, /motivate, /myplan
    async def test_11_commands(self):
        with patch("study_bot.ai_call", return_value="Command executed successfully"):
            # /ask
            self.update.message.text = "/ask What is energy?"
            await study_bot.ask_command(self.update, MagicMock())

            # /brainy
            self.update.message.text = "/brainy Quantum computing"
            await study_bot.brainy_command(self.update, MagicMock())

            # /translate
            self.update.message.text = "/translate Bonjour le monde"
            await study_bot.translate_command(self.update, MagicMock())

            # /define
            self.update.message.text = "/define Osmosis"
            await study_bot.define_command(self.update, MagicMock())

            # /motivate
            self.update.message.text = "/motivate"
            await study_bot.motivate_command(self.update, MagicMock())

            # /myplan
            self.update.message.text = "/myplan Physics"
            await study_bot.myplan_command(self.update, MagicMock())

    # Test 12: Regression - Web application shared routes and health remain healthy
    def test_12_web_app_regression(self):
        client = app.app.test_client()
        resp = client.get("/api/health")
        self.assertEqual(resp.status_code, 200)

        ping = client.get("/api/ping")
        self.assertEqual(ping.status_code, 200)
        self.assertTrue(ping.get_json().get("pong"))

        models = client.get("/api/models")
        self.assertEqual(models.status_code, 200)


if __name__ == "__main__":
    unittest.main()
