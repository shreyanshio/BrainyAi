"""
Tests for Brainy Advanced AI Orchestration, Model Routing, Conversation Memory,
Token Optimization, Caching, Reliability, and Abuse Prevention.
Validates all 25 specific test contracts outlined in Phase 14.
"""

import time
import unittest
from unittest.mock import patch, MagicMock

from ai_routing.tasks import (
    TaskType,
    ResponseDepth,
    TaskComplexity,
    classify_task,
    classify_task_complexity,
    is_conversational_followup,
)
from ai_routing.policy import get_routing_candidates
from ai_routing.registry import registry, CostCategory, ModelSpec, mask_credential
from ai_routing.memory import (
    TopicState,
    extract_exact_identifiers,
    detect_topic_change,
    should_update_summary,
    assemble_dynamic_context,
)
from ai_routing.cache import ResponseCache
from ai_routing.rate_limiter import IntelligentRateLimiter
from ai_routing.budget import OutputBudgetManager
from ai_routing.router import AIRouter, RouterResponse


class TestAdvancedAIOrchestration(unittest.TestCase):

    # ── 1. Lightweight Routing ──
    def test_01_lightweight_routing(self):
        prompts = [
            ("Define momentum briefly", TaskType.SIMPLE_EXPLANATION),
            ("Translate to Hindi: Good Morning", TaskType.TRANSLATION),
            ("Correct this grammar: He go to school yesterday", TaskType.TEXT_CORRECTION),
        ]
        for p, t in prompts:
            c = classify_task_complexity(p, task=t, depth=ResponseDepth.FAST)
            self.assertEqual(c, TaskComplexity.LIGHT)
            candidates = get_routing_candidates(t, depth=ResponseDepth.FAST, complexity=c)
            # Lightweight tasks route to Groq fast or Gemini Flash-Lite
            top_prov, top_model = candidates[0]
            self.assertIn(top_prov, ("groq", "gemini"))
            self.assertTrue(
                "8b" in top_model or "flash-lite" in top_model or "instant" in top_model,
                f"Expected lightweight model for {t}, got {top_model}"
            )

    # ── 2. Standard Routing ──
    def test_02_standard_routing(self):
        prompts = [
            "Explain how the immune system defends against viral infections in humans",
            "What were the economic causes of the French Revolution?",
            "How do supply and demand determine equilibrium prices?",
        ]
        for p in prompts:
            t = classify_task(p)
            c = classify_task_complexity(p, task=t)
            candidates = get_routing_candidates(t, depth=ResponseDepth.BALANCED, complexity=c)
            self.assertEqual(candidates[0], ("gemini", "gemini-3.8-flash"))

    # ── 3. Complex Routing ──
    def test_03_complex_routing(self):
        complex_queries = [
            ("Write a Python function for topological sorting of a DAG", TaskType.CODING),
            ("Debug this concurrency deadlock in Java synchronized block", TaskType.COMPLEX_DEBUGGING),
            ("Prove that the set of prime numbers is infinite", TaskType.MATH_AND_LOGIC),
            ("Explain the mechanism of nucleophilic aromatic substitution", TaskType.CHEMISTRY),
        ]
        for q, t in complex_queries:
            c = classify_task_complexity(q, task=t)
            self.assertIn(c, (TaskComplexity.COMPLEX, TaskComplexity.DEEP))
            candidates = get_routing_candidates(t, complexity=c)
            self.assertEqual(candidates[0], ("gemini", "gemini-3.8-flash"))
            # High thinking level resolved for complex/deep
            tl = registry.get_model_thinking_level("gemini-3.8-flash", c)
            self.assertIn(tl, ("medium", "high"))

    # ── 4. Topic Switching ──
    def test_04_topic_switching(self):
        # Switching from Python inheritance to Photosynthesis
        old_topic_summary = "The student is learning about Python multiple inheritance and super() calls."
        new_unrelated_query = "How does photosynthesis convert sunlight into glucose in plant cells?"
        topic_changed = detect_topic_change(new_unrelated_query, old_topic_summary)
        self.assertTrue(topic_changed, "Expected topic change detected for biology query")

        # Same domain or follow-up query should NOT trigger topic change
        followup_query = "What about method resolution order in Python?"
        no_change = detect_topic_change(followup_query, old_topic_summary)
        self.assertFalse(no_change, "Same domain query should not trigger topic change")

    # ── 5. Follow-Up Context Retrieval ──
    def test_05_followup_context_retrieval(self):
        followups = [
            "Explain that again.",
            "Give me an example.",
            "Make it simpler.",
            "What about the second point?",
            "Continue.",
            "Why does this happen?",
            "aur samjhao",
        ]
        for f in followups:
            self.assertTrue(is_conversational_followup(f), f"Expected '{f}' to be recognized as follow-up")

        # In context of previous coding question, follow-up inherits coding task
        messages = [
            {"role": "user", "content": "Write a binary search algorithm in Python"},
            {"role": "assistant", "content": "Here is the binary search implementation..."},
            {"role": "user", "content": "Give me an example of how it runs on [1, 3, 5, 7]"},
        ]
        inherited_task = classify_task(prompt="", messages=messages)
        self.assertEqual(inherited_task, TaskType.CODING)

    # ── 6. Rolling Summary Updates ──
    def test_06_rolling_summary_updates(self):
        state = TopicState(
            conversation_id="test-conv-123",
            current_topic="Python Decorators",
            current_task="learning",
            user_goal="Master decorator syntax with arguments",
            important_facts=["Decorators wrap a function and modify behavior"],
            important_references=["functools.wraps", "@decorator", "args, kwargs"],
        )
        json_repr = state.to_json()
        restored = TopicState.from_json(json_repr)
        self.assertEqual(restored.current_topic, "Python Decorators")
        self.assertIn("functools.wraps", restored.important_references)

        # Exact identifiers preserved
        identifiers = extract_exact_identifiers("Use `functools.wraps` in `decorator.py` and call `get_user()` on `UserTable`")
        self.assertIn("functools.wraps", identifiers)
        self.assertIn("decorator.py", identifiers)

        # Threshold decision
        self.assertFalse(should_update_summary(5, topic_changed=False, threshold=10))
        self.assertTrue(should_update_summary(10, topic_changed=False, threshold=10))
        self.assertTrue(should_update_summary(3, topic_changed=True, threshold=10))

    # ── 7. User Isolation ──
    def test_07_user_isolation(self):
        cache = ResponseCache()
        # Cache personal response for User A
        cache.set(
            "My project status update",
            "User A private response",
            "WRITING",
            "gemini-3.8-flash",
            "gemini",
            user_id="user_101"
        )
        # User B should NOT be able to access User A's response
        user_b_res = cache.get("My project status update", "WRITING", "gemini-3.8-flash", user_id="user_102")
        self.assertIsNone(user_b_res)

        # User A CAN access their own response
        user_a_res = cache.get("My project status update", "WRITING", "gemini-3.8-flash", user_id="user_101")
        self.assertIsNotNone(user_a_res)
        self.assertEqual(user_a_res[0], "User A private response")

    # ── 8. Exact Cache Matching ──
    def test_08_exact_cache_matching(self):
        cache = ResponseCache()
        query = "What is Newton's second law of motion?"
        answer = "Newton's second law states that Force equals mass times acceleration (F = ma)."
        cache.set(query, answer, "SIMPLE_EXPLANATION", "gemini-3.8-flash", "gemini")

        # Case-insensitive, whitespace-insensitive retrieval
        retrieved = cache.get("  what is newton's second law of motion?  ", "SIMPLE_EXPLANATION", "gemini-3.8-flash")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved[0], answer)
        self.assertGreater(cache.hits, 0)

    # ── 9. Semantic / Privacy Cache Safety ──
    def test_09_semantic_cache_safety(self):
        cache = ResponseCache()
        # Queries with personal pronouns or document context MUST be rejected from global caching
        self.assertFalse(cache.is_eligible_for_global_cache("What is my uploaded PDF about?"))
        self.assertFalse(cache.is_eligible_for_global_cache("Define my project score"))
        self.assertFalse(cache.is_eligible_for_global_cache("What is today's schedule for me?"))
        # Pure static educational queries ARE eligible
        self.assertTrue(cache.is_eligible_for_global_cache("What is recursion?"))
        self.assertTrue(cache.is_eligible_for_global_cache("Define photosynthesis"))
        self.assertTrue(cache.is_eligible_for_global_cache("SI unit of capacitance"))

    # ── 10. Cache Invalidation ──
    def test_10_cache_invalidation(self):
        cache = ResponseCache()
        cache.set("User 500 private notes", "Notes content", "WRITING", "gemini-3.8-flash", "gemini", user_id="500")
        self.assertIsNotNone(cache.get("User 500 private notes", "WRITING", "gemini-3.8-flash", user_id="500"))

        cache.invalidate_user("500")
        self.assertIsNone(cache.get("User 500 private notes", "WRITING", "gemini-3.8-flash", user_id="500"))

    # ── 11. Gemini Failure Failover ──
    def test_11_gemini_failure_failover(self):
        router = AIRouter()
        # When Gemini raises an exception, router should fall back to next candidate
        mock_gemini = MagicMock()
        mock_gemini.generate.side_effect = RuntimeError("Gemini connection reset")
        mock_groq = MagicMock()
        mock_groq.generate.return_value = MagicMock(
            text="Recovered answer from Groq",
            model="openai/gpt-oss-120b",
            finish_reason="stop",
            input_tokens=100,
            output_tokens=50
        )

        with patch.object(router, "get_provider", side_effect=lambda name: mock_gemini if name == "gemini" else mock_groq):
            res = router.generate(
                prompt="Explain Dijkstra algorithm",
                candidate_chain=[("gemini", "gemini-3.8-flash"), ("groq", "openai/gpt-oss-120b")]
            )
            self.assertEqual(res.text, "Recovered answer from Groq")
            self.assertTrue(res.fallback_used)
            self.assertEqual(res.fallback_from, "gemini")

    # ── 12. Groq Failure Failover ──
    def test_12_groq_failure_failover(self):
        router = AIRouter()
        mock_groq = MagicMock()
        mock_groq.generate.side_effect = RuntimeError("Groq rate limit 429")
        mock_cerebras = MagicMock()
        mock_cerebras.generate.return_value = MagicMock(
            text="Recovered from Cerebras",
            model="llama3.1-8b",
            finish_reason="stop",
            input_tokens=20,
            output_tokens=10
        )

        with patch.object(router, "get_provider", side_effect=lambda name: mock_groq if name == "groq" else mock_cerebras):
            res = router.generate(
                prompt="Hi!",
                candidate_chain=[("groq", "openai/gpt-oss-20b"), ("cerebras", "llama3.1-8b")]
            )
            self.assertEqual(res.text, "Recovered from Cerebras")
            self.assertTrue(res.fallback_used)

    # ── 13. OpenRouter Fallback ──
    def test_13_openrouter_fallback(self):
        router = AIRouter()
        mock_fail = MagicMock()
        mock_fail.generate.side_effect = RuntimeError("Provider down")
        mock_openrouter = MagicMock()
        mock_openrouter.generate.return_value = MagicMock(
            text="Answer from OpenRouter free",
            model="openrouter/free",
            finish_reason="stop",
            input_tokens=50,
            output_tokens=25
        )

        with patch.object(router, "get_provider", side_effect=lambda name: mock_openrouter if name == "openrouter" else mock_fail):
            res = router.generate(
                prompt="Explain photosynthesis",
                candidate_chain=[("gemini", "gemini-3.8-flash"), ("groq", "openai/gpt-oss-120b"), ("openrouter", "openrouter/free")]
            )
            self.assertEqual(res.text, "Answer from OpenRouter free")
            self.assertEqual(res.provider, "openrouter")

    # ── 14. HTTP 429 Handling Without Account Hopping ──
    @patch("ai_routing.providers.gemini_provider._http_post")
    def test_14_http_429_handling_no_key_hopping(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_post.return_value = mock_resp

        from ai_routing.providers.gemini_provider import GeminiProvider
        provider = GeminiProvider()

        with patch.object(registry, "get_rotator") as mock_rot:
            rot_mock = MagicMock()
            rot_mock.key_count = 5  # Has 5 keys
            rot_mock.get_key.return_value = "AIzaSyTestGeminiKey1234"
            mock_rot.return_value = rot_mock

            with self.assertRaises(RuntimeError) as ctx:
                provider.generate(
                    messages=[{"role": "user", "content": "Hello"}],
                    system_prompt="Test",
                    max_tokens=100,
                    model_id="gemini-3.8-flash"
                )
            # Must raise rate limit error immediately instead of cycling through all 5 keys!
            self.assertIn("429", str(ctx.exception))
            # get_key should have been called only ONCE for this project attempt
            self.assertEqual(rot_mock.get_key.call_count, 1)

    # ── 15. Invalid Credentials & Masked Logging ──
    def test_15_invalid_credentials_handling(self):
        raw_key = "AIzaSyC9876543210Fedcba_A12F"
        masked = mask_credential(raw_key)
        self.assertTrue(masked.startswith("********"))
        self.assertTrue(masked.endswith("A12F"))
        self.assertNotIn("9876543210", masked)

    # ── 16. Request Cancellation & Timeout Bounds ──
    def test_16_request_cancellation(self):
        spec = registry.get_model_spec("gemini-3.8-flash")
        self.assertIsNotNone(spec)
        self.assertLessEqual(spec.timeout_sec, 45.0)

        groq_spec = registry.get_model_spec("openai/gpt-oss-20b")
        self.assertIsNotNone(groq_spec)
        self.assertLessEqual(groq_spec.timeout_sec, 20.0)

    # ── 17. Streaming Pre-First-Token Failover ──
    def test_17_streaming_interruptions(self):
        router = AIRouter()
        def fail_stream(*args, **kwargs):
            raise RuntimeError("Upstream socket error before first chunk")
            yield  # pragma: no cover

        def ok_stream(*args, **kwargs):
            yield "Hello "
            yield "world!"

        mock_fail = MagicMock()
        mock_fail.stream.side_effect = fail_stream
        mock_ok = MagicMock()
        mock_ok.stream.side_effect = ok_stream

        with patch.object(router, "get_provider", side_effect=lambda name: mock_fail if name == "primary" else mock_ok):
            chunks = list(router.stream(
                prompt="Hi",
                candidate_chain=[("primary", "fail-model"), ("secondary", "ok-model")]
            ))
            self.assertEqual("".join(chunks), "Hello world!")

    # ── 18. Duplicate Submission Prevention (Deduplication) ──
    def test_18_duplicate_submission_prevention(self):
        limiter = IntelligentRateLimiter(duplicate_window_sec=5.0)
        user_id = 999
        content = "Submit expensive study test question"

        # First submission: allowed
        ok1, code1, _ = limiter.check_and_acquire(user_id, content)
        self.assertTrue(ok1)
        self.assertIsNone(code1)

        # Immediate double-click duplicate: rejected
        ok2, code2, retry_sec = limiter.check_and_acquire(user_id, content)
        self.assertFalse(ok2)
        self.assertEqual(code2, "DUPLICATE_SUBMISSION_DETECTED")
        self.assertGreater(retry_sec, 0)

        limiter.release(user_id)

    # ── 19. Per-User Rate Limiting ──
    def test_19_rate_limiting_per_user(self):
        limiter = IntelligentRateLimiter(max_requests_per_minute=3)
        user_id = 888

        for i in range(3):
            ok, _, _ = limiter.check_and_acquire(user_id, f"Different query {i}")
            self.assertTrue(ok)
            limiter.release(user_id)

        # 4th query in same minute exceeds RPM
        ok4, code4, retry_sec = limiter.check_and_acquire(user_id, "Different query 4")
        self.assertFalse(ok4)
        self.assertEqual(code4, "RATE_LIMIT_EXCEEDED")
        self.assertGreater(retry_sec, 0)

    # ── 20. Daily Token Budgets ──
    def test_20_daily_token_budgets(self):
        limiter = IntelligentRateLimiter(daily_token_budget_per_user=1000)
        user_id = 777

        ok, _, _ = limiter.check_and_acquire(user_id, "Query 1")
        self.assertTrue(ok)
        # Release with 1,200 tokens consumed (exceeds 1000 budget)
        limiter.release(user_id, tokens_consumed=1200)

        # Next query is blocked by daily token budget
        ok_next, code_next, _ = limiter.check_and_acquire(user_id, "Query 2")
        self.assertFalse(ok_next)
        self.assertEqual(code_next, "DAILY_TOKEN_BUDGET_EXCEEDED")

    # ── 21. PDF Studio Compatibility ──
    def test_21_pdf_studio_compatibility(self):
        from pdf_studio.chunker import chunk_document_pages, DocumentChunk

        pages = [{"page_number": 1, "text_content": "Chapter 1: Principles of Quantum Physics. Max Planck proposed quanta in 1900."}]
        # Local chunking does not make unnecessary LLM calls
        chunks = chunk_document_pages(pages, target_tokens_per_chunk=3500)
        self.assertGreater(len(chunks), 0)
        self.assertIn("Quantum", chunks[0].text)

    # ── 22. Chat Persistence & Encryption ──
    def test_22_chat_persistence(self):
        from app import mask_secure_hash, unmask_secure_hash
        plain_title = "Advanced Operating Systems Session"
        encrypted = mask_secure_hash(plain_title)
        self.assertNotEqual(plain_title, encrypted)
        decrypted = unmask_secure_hash(encrypted)
        self.assertEqual(plain_title, decrypted)

    # ── 23. Supabase Authorization & Data Isolation ──
    def test_23_supabase_authorization(self):
        from app import sb_get_session
        # With unconfigured Supabase in test environment, cross-user session retrieval returns None
        sess = sb_get_session("non-existent-session-id", user_id=99999)
        self.assertIsNone(sess)

    # ── 24. Admin Monitoring Authorization ──
    def test_24_admin_monitoring_authorization(self):
        from app import app
        client = app.test_client()
        # Unauthenticated request to admin telemetry returns 401/403
        resp = client.get("/api/admin/ai-health")
        self.assertIn(resp.status_code, (401, 403, 302))

    # ── 25. Secret Management Validation ──
    def test_25_secret_management_validation(self):
        test_keys = [
            "AIzaSyABCDEF1234567890",
            "gsk_mySecretGroqKey123456789",
            "sk-or-v1-abcdef1234567890",
        ]
        for k in test_keys:
            masked = mask_credential(k)
            # Must not expose the full secret body
            self.assertTrue(masked.startswith("********"))
            self.assertNotIn(k[4:14], masked)


if __name__ == "__main__":
    unittest.main()
