"""
Principal Engineering Test Suite for Brainy Telegram Architecture:
1. Idempotency Engine & Telegram Update Deduplication
2. Two-Phase Atomic Quota Reservation & Concurrency Race Protection
3. Stale Reservation TTL Auto-Expiry & Idempotent Quota Keys
4. Application Service Layer (telegram_service.py) Invariant Verification
5. Strict Group Boundary Enforcement & Private Memory Isolation
6. Effective Identity Mapping & Cross-Channel Persistence Sync
"""

import time
import threading
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

from ai_routing.idempotency import idempotency_engine, IdempotencyState
from ai_routing.quota import (
    IMAGE_FREE_LIMIT,
    get_user_image_quota,
    reserve_image_quota,
    commit_image_quota,
    release_image_quota,
    consume_user_image_quota,
    generate_telegram_link_code,
    link_telegram_to_web_account,
    resolve_effective_identity,
    _in_memory_quotas,
    _in_memory_reservations,
    _in_memory_link_codes,
    _in_memory_user_links,
)
from ai_routing.telegram_service import telegram_service


class TestIdempotencyEngine(unittest.TestCase):
    """Verifies atomic claim, deduplication, completion, failure retry, and TTL eviction."""

    def setUp(self):
        idempotency_engine.clear()

    def test_first_claim_succeeds_and_second_fails(self):
        key = "tg_update_987654"
        claimed, rec = idempotency_engine.claim(key)
        self.assertTrue(claimed)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.state, IdempotencyState.PROCESSING)

        # Immediate duplicate attempt must be rejected
        claimed_2, rec_2 = idempotency_engine.claim(key)
        self.assertFalse(claimed_2)
        self.assertEqual(rec_2.state, IdempotencyState.PROCESSING)

    def test_complete_stores_result_and_blocks_reclaim(self):
        key = "tg_update_111222"
        idempotency_engine.claim(key)
        idempotency_engine.complete(key, result="Answer to question")

        claimed, rec = idempotency_engine.claim(key)
        self.assertFalse(claimed)
        self.assertEqual(rec.state, IdempotencyState.COMPLETED)
        self.assertEqual(rec.result, "Answer to question")

    def test_failed_claim_allows_retry(self):
        key = "tg_update_333444"
        idempotency_engine.claim(key)
        idempotency_engine.release_or_fail(key)

        # Failure allows immediate retry
        claimed, rec = idempotency_engine.claim(key)
        self.assertTrue(claimed)
        self.assertEqual(rec.state, IdempotencyState.PROCESSING)

    def test_expired_claim_allows_reclaim(self):
        key = "tg_update_555666"
        idempotency_engine.claim(key, ttl_seconds=1)
        time.sleep(1.1)

        # After TTL expiration, key can be claimed again
        claimed, rec = idempotency_engine.claim(key)
        self.assertTrue(claimed)


class TestTwoPhaseQuotaReservation(unittest.TestCase):
    """Verifies two-phase reservation pattern, concurrency safety, auto-expiry, and idempotency."""

    def setUp(self):
        _in_memory_quotas.clear()
        _in_memory_reservations.clear()
        _in_memory_link_codes.clear()
        _in_memory_user_links.clear()

    def test_reservation_lifecycle_reserve_and_commit(self):
        user_id = 7001
        res_id, remaining, eff_id = reserve_image_quota(user_id)
        self.assertIsNotNone(res_id)
        self.assertEqual(remaining, 4)
        self.assertEqual(eff_id, str(user_id))

        # Check quota reflects the pending reservation
        status = get_user_image_quota(user_id)
        self.assertEqual(status["used"], 0)
        self.assertEqual(status["reserved"], 1)
        self.assertEqual(status["remaining"], 4)

        # Commit reservation
        success = commit_image_quota(res_id)
        self.assertTrue(success)

        # After commit, committed usage increments and reservation clears
        status_after = get_user_image_quota(user_id)
        self.assertEqual(status_after["used"], 1)
        self.assertEqual(status_after["reserved"], 0)
        self.assertEqual(status_after["remaining"], 4)

    def test_reservation_lifecycle_reserve_and_release(self):
        user_id = 7002
        res_id, remaining, eff_id = reserve_image_quota(user_id)
        self.assertIsNotNone(res_id)
        self.assertEqual(remaining, 4)

        # Upstream fails -> release reservation
        success = release_image_quota(res_id)
        self.assertTrue(success)

        # Quota is completely restored
        status = get_user_image_quota(user_id)
        self.assertEqual(status["used"], 0)
        self.assertEqual(status["reserved"], 0)
        self.assertEqual(status["remaining"], 5)

    def test_idempotent_reservation_with_same_key(self):
        user_id = 7003
        key = "req_uuid_abc_123"

        res_id_1, remaining_1, _ = reserve_image_quota(user_id, idempotency_key=key)
        res_id_2, remaining_2, _ = reserve_image_quota(user_id, idempotency_key=key)

        # Idempotent call returns the exact same reservation without consuming another slot
        self.assertEqual(res_id_1, res_id_2)
        self.assertEqual(remaining_1, remaining_2)
        status = get_user_image_quota(user_id)
        self.assertEqual(status["reserved"], 1)
        self.assertEqual(status["remaining"], 4)

    def test_stale_reservation_auto_expires(self):
        user_id = 7004
        # Reserve with 1-second TTL
        res_id, remaining, _ = reserve_image_quota(user_id, ttl_seconds=1)
        self.assertEqual(remaining, 4)

        time.sleep(1.1)

        # Stale uncommitted reservation should automatically expire on next check
        status = get_user_image_quota(user_id)
        self.assertEqual(status["reserved"], 0)
        self.assertEqual(status["remaining"], 5)

    def test_concurrent_reservations_race_condition_protection(self):
        """10 threads compete for 5 available slots. Exactly 5 must succeed and 5 must be rejected."""
        user_id = 7005
        results = []
        threads = []

        def worker():
            res_id, rem, _ = reserve_image_quota(user_id)
            results.append(bool(res_id))

        for _ in range(10):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        successes = [r for r in results if r is True]
        failures = [r for r in results if r is False]

        self.assertEqual(len(successes), 5, f"Expected exactly 5 granted reservations, got {len(successes)}")
        self.assertEqual(len(failures), 5, f"Expected exactly 5 rejected reservations, got {len(failures)}")

        quota = get_user_image_quota(user_id)
        self.assertEqual(quota["remaining"], 0)
        self.assertFalse(quota["allowed"])


class TestTelegramServiceApplicationLayer(unittest.TestCase):
    """Verifies TelegramService isolation, routing, language preservation, and linking."""

    def setUp(self):
        _in_memory_quotas.clear()
        _in_memory_reservations.clear()
        _in_memory_link_codes.clear()
        _in_memory_user_links.clear()
        idempotency_engine.clear()

    @patch("ai_routing.router.router.generate")
    def test_process_chat_query_preserves_hinglish_and_routes(self, mock_generate):
        mock_res = MagicMock()
        mock_res.text = "Newton ka third law simple hai bhai: har action ka opposite reaction hota hai."
        mock_res.provider = "gemini"
        mock_generate.return_value = mock_res

        user_id = 8001
        query = "bhai newton ka third law samjha de please"
        res = telegram_service.process_chat_query(
            user_id=user_id,
            query=query,
            is_group=False,
            update_id=10101
        )

        self.assertTrue(res.success)
        self.assertIn("Newton ka third law", res.text)
        self.assertFalse(res.is_duplicate)
        self.assertEqual(res.metadata["lang"], "hinglish")

        # Second call with same update_id must return cached result without calling router again
        res_duplicate = telegram_service.process_chat_query(
            user_id=user_id,
            query=query,
            is_group=False,
            update_id=10101
        )
        self.assertTrue(res_duplicate.success)
        self.assertTrue(res_duplicate.is_duplicate)
        mock_generate.assert_called_once()  # Called only once!

    @patch("ai_routing.router.router.generate")
    def test_group_chat_query_is_isolated_single_turn(self, mock_generate):
        mock_res = MagicMock()
        mock_res.text = "In group mode: Quick answer."
        mock_generate.return_value = mock_res

        user_id = 8002
        res = telegram_service.process_chat_query(
            user_id=user_id,
            query="Calculate 5 * 25",
            is_group=True,
            update_id=20202,
            history=[{"role": "user", "content": "previous private question"}]
        )

        self.assertTrue(res.success)
        # Verify call used ephemeral single turn, ignoring private history
        kwargs = mock_generate.call_args[1]
        self.assertEqual(len(kwargs["messages"]), 1)
        self.assertEqual(kwargs["messages"][0]["content"], "Calculate 5 * 25")
        self.assertEqual(kwargs["platform"], "telegram_group")

    def test_account_linking_and_quota_synchronization(self):
        telegram_id = 8003
        web_user_id = "web_user_999"

        # Web user used 2 images
        consume_user_image_quota(web_user_id)
        consume_user_image_quota(web_user_id)
        self.assertEqual(get_user_image_quota(web_user_id)["remaining"], 3)

        # Generate link code from Web
        code = generate_telegram_link_code(web_user_id)

        # Telegram user executes link via application service
        link_res = telegram_service.link_account(telegram_id, code)
        self.assertTrue(link_res.success)
        self.assertIn("unified with your Brainy Web account", link_res.text)

        # Effective identity is now web_user_999
        self.assertEqual(resolve_effective_identity(telegram_id), web_user_id)

        # Status reflects unified quota
        status = telegram_service.get_user_status(telegram_id)
        self.assertTrue(status["is_linked"])
        self.assertEqual(status["remaining"], 3)
        self.assertEqual(status["used"], 2)


class TestGroupMediaGovernanceInvariants(unittest.TestCase):
    """Verifies strict group chat restrictions: /image and /voice required; uncommanded media dropped."""

    def test_group_photo_without_image_command_dropped(self):
        import study_bot
        update = MagicMock()
        update.effective_chat.type = "group"
        update.message.caption = "Look at this textbook photo guys"
        context = MagicMock()

        import asyncio
        loop = asyncio.new_event_loop()
        with patch.object(study_bot, "_process_image_analysis", new_callable=AsyncMock) as mock_analyze:
            loop.run_until_complete(study_bot.handle_image(update, context))
            mock_analyze.assert_not_called()
        loop.close()

    def test_group_voice_without_voice_command_dropped(self):
        import study_bot
        update = MagicMock()
        update.effective_chat.type = "group"
        update.message.voice = MagicMock()
        context = MagicMock()

        import asyncio
        loop = asyncio.new_event_loop()
        with patch.object(study_bot, "process_query", new_callable=AsyncMock) as mock_pq:
            loop.run_until_complete(study_bot.handle_voice(update, context))
            mock_pq.assert_not_called()
        loop.close()


if __name__ == "__main__":
    unittest.main()
