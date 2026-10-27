import os
import unittest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test:token")
os.environ.setdefault("OWNER_TELEGRAM_ID", "999999999")

import bot


class StorageTtlPlanTests(unittest.TestCase):
    def test_storage_ttl_matches_requested_plan_table(self):
        expected = {
            "free": 12,
            "vip_basic": 24,
            "vip_medium": 48,
            "premium": 72,
        }
        actual = {key: bot.get_plan_info(key)["storage_hours"] for key in expected}
        self.assertEqual(actual, expected)

    def test_storage_expiry_uses_active_plan(self):
        from datetime import datetime, timezone
        from unittest.mock import patch

        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for plan_key, hours in {
            "free": 12,
            "vip_basic": 24,
            "vip_medium": 48,
            "premium": 72,
        }.items():
            with self.subTest(plan=plan_key), patch.object(bot, "get_user_plan", return_value=plan_key):
                self.assertEqual(
                    bot.storage_expiry(123, base),
                    base.replace(hour=base.hour) + bot.timedelta(hours=hours),
                )


if __name__ == "__main__":
    unittest.main()
