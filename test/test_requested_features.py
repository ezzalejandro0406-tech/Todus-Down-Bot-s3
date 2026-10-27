import unittest
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock
from pathlib import Path

from bot import (
    button_callback,
    download_keyboard,
    download_menu_keyboard,
    link_txt_filename,
    main_keyboard,
    apply_referral,
    get_user_balance,
    grant_user_balance,
    plan_purchase_keyboard,
    plans_keyboard,
    plans_text,
    quota_exhausted_text,
    quota_lines,
    quota_exhausted_keyboard,
    membership_keyboard,
    membership_missing_text,
    membership_prompt_text,
    result_keyboard,
    result_multi_keyboard,
    task_detail_text,
    transfer_complete_text,
    user_has_required_memberships,
    welcome_text,
)
from task_queue import TransferTask


def all_buttons(markup):
    return [button for row in markup.inline_keyboard for button in row]


class RequestedFeatureTests(unittest.TestCase):
    def test_plans_menu_has_share_copy_and_purchase_actions(self):
        markup = plans_keyboard(123, "jk_bot")
        buttons = all_buttons(markup)
        self.assertTrue(any(button.callback_data == "plans:buy" for button in buttons))
        self.assertTrue(any(button.copy_text and "ref_123" in button.copy_text.text for button in buttons))
        self.assertTrue(any(button.url and "t.me/share/url" in button.url for button in buttons))
        self.assertIn("5$", plans_text(123, "jk_bot"))

    def test_referral_adds_five_to_inviter_only_once(self):
        import bot
        with tempfile.TemporaryDirectory() as directory:
            old_path = bot.USERS_DATA_FILE
            bot.USERS_DATA_FILE = str(Path(directory) / "users.json")
            try:
                bot._save_json(bot.USERS_DATA_FILE, {"users": {
                    "100": {"user_id": 100, "balance": 5},
                    "200": {"user_id": 200, "balance": 5},
                }})
                self.assertTrue(apply_referral(200, 100))
                self.assertEqual(get_user_balance(100), 10)
                self.assertEqual(get_user_balance(200), 5)
                self.assertFalse(apply_referral(200, 100))
                self.assertEqual(get_user_balance(100), 10)
            finally:
                bot.USERS_DATA_FILE = old_path

    def test_purchase_menu_shows_locked_plans_without_enough_balance(self):
        buttons = all_buttons(plan_purchase_keyboard(123))
        self.assertTrue(any(button.callback_data == "plans:unavailable:vip_basic" for button in buttons))
        self.assertTrue(any(button.callback_data == "plans:unavailable:vip_medium" for button in buttons))
        self.assertTrue(any(button.callback_data == "plans:unavailable:premium" for button in buttons))
        quota_buttons = all_buttons(quota_exhausted_keyboard())
        self.assertIn("plans:buy", [button.callback_data for button in quota_buttons])

    def test_quota_text_explains_buy_or_wait_and_quota_lines_show_reset(self):
        self.assertIn("ᴄᴏᴍᴘʀᴀʀ ᴘʟᴀɴ ᴏ ᴇꜱᴘᴇʀᴀʀ", quota_exhausted_text())
        lines = quota_lines(12345)
        self.assertTrue(any("Gastado hoy" in line for line in lines))
        self.assertTrue(any("Próximo reinicio" in line for line in lines))

    def test_download_keyboard_has_one_tap_copy_and_compact_row(self):
        url = "https://files.example/movie.mp4"
        markup = download_keyboard(url)
        self.assertEqual(len(markup.inline_keyboard), 1)
        self.assertEqual(len(markup.inline_keyboard[0]), 2)
        copy = next(button for button in all_buttons(markup) if button.copy_text)
        self.assertEqual(copy.copy_text.text, url)

    def test_download_method_menu_puts_two_methods_on_one_row(self):
        markup = download_menu_keyboard()
        self.assertEqual([len(row) for row in markup.inline_keyboard], [2, 1])
        self.assertEqual(
            [button.callback_data for button in markup.inline_keyboard[0]],
            ["download:telegram", "download:url"],
        )

    def test_ready_result_has_only_download_copy_and_convert_actions(self):
        url = "https://files.example/app.apk"
        markup = result_keyboard(url, "abc123")
        buttons = all_buttons(markup)
        self.assertEqual([len(row) for row in markup.inline_keyboard], [1, 2, 1])
        self.assertEqual(len(buttons), 4)
        download = next(button for button in buttons if button.url)
        copy = next(button for button in buttons if button.copy_text)
        convert = next(button for button in buttons if button.callback_data == "j:abc123:generate_txt")
        self.assertEqual(download.url, url)
        self.assertEqual(copy.copy_text.text, url)
        self.assertIn("ᴛˣᴛ", convert.text)
        self.assertEqual(buttons[-1].callback_data, "j:abc123:cloud_delete")

    def test_completion_message_contains_no_user_or_task_ids(self):
        text = transfer_complete_text("app.apk", 100, 1, "@ana", 12345, "abc123")
        self.assertIn("ᴀᴘᴘ.ᴀᴘᴋ", text)
        self.assertIn("0.00 ᴍʙ", text)
        self.assertIn("ᴅᴜʀᴀᴄ", text)
        self.assertNotIn("12345", text)
        self.assertNotIn("abc123", text)
        self.assertNotIn("@ana", text)

    def test_generated_txt_filename_uses_uploaded_file_stem(self):
        self.assertEqual(link_txt_filename("My App (final).apk"), "My App (final).txt")
        self.assertEqual(link_txt_filename(None), "archivo.txt")

    def test_multi_part_keyboard_is_compact_and_includes_txt_action(self):
        markup = result_multi_keyboard("abc123")
        self.assertEqual([len(row) for row in markup.inline_keyboard], [2, 1])
        self.assertIn("j:abc123:generate_txt", [button.callback_data for button in all_buttons(markup)])
        self.assertIn("j:abc123:cloud_delete", [button.callback_data for button in all_buttons(markup)])

    def test_task_detail_does_not_show_ids(self):
        job = TransferTask(98765, 98765, "url", None, None, username="@ana")
        text = task_detail_text(job)
        self.assertNotIn("98765", text)
        self.assertNotIn(job.task_id, text)
        self.assertNotIn("@ana", text)

    def test_welcome_shows_name_username_and_id_without_id_button(self):
        text = welcome_text(12345, "Ana Gómez", "ana")
        self.assertIn("ana", text.lower())
        self.assertIn("<code>12345</code>", text)
        self.assertIn("@ana", text)
        self.assertNotIn("Copiar ID", text)

    def test_main_keyboard_puts_downloads_on_top_and_other_buttons_in_pairs(self):
        markup = main_keyboard()
        self.assertEqual([len(row) for row in markup.inline_keyboard], [1, 1, 2, 2, 2, 1])
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "downloads")
        self.assertEqual(markup.inline_keyboard[1][0].callback_data, "balance")
        self.assertFalse(any("ID" in (button.text or "") for button in all_buttons(markup)))

    def test_admin_balance_grant_persists_for_an_id(self):
        import bot
        with tempfile.TemporaryDirectory() as directory:
            old_path = bot.USERS_DATA_FILE
            bot.USERS_DATA_FILE = str(Path(directory) / "users.json")
            try:
                ok, balance = grant_user_balance(8935843354, 250)
                self.assertTrue(ok)
                self.assertEqual(balance, 255)  # registro nuevo parte del saldo de bienvenida de 5$
                self.assertEqual(get_user_balance(8935843354), 255)
            finally:
                bot.USERS_DATA_FILE = old_path

    def test_membership_screen_has_requested_join_buttons_and_verifier(self):
        buttons = all_buttons(membership_keyboard())
        self.assertEqual([button.text for button in buttons], [
            "📢 ᴄᴀɴᴀʟ", "👥 ɢʀᴜᴘᴏ", "✅ ʏᴀ ᴍᴇ ᴜɴɪ́",
        ])
        prompt = membership_prompt_text()
        self.assertIn("ᴜ́ɴᴇᴛᴇ ᴀ ᴄᴀɴᴀʟ ʏ ɢʀᴜᴘᴏ", prompt)
        self.assertLessEqual(len(prompt), 70)

    def test_membership_screen_names_missing_channel(self):
        text = membership_missing_text(["@canal_prueba"])
        self.assertIn("@canal_prueba", text)
        self.assertIn("ᴅᴇɴᴛʀᴏ", text)


class MembershipCheckTests(unittest.IsolatedAsyncioTestCase):
    async def test_accepts_member_of_both_chats(self):
        bot = SimpleNamespace(get_chat_member=AsyncMock(
            side_effect=[SimpleNamespace(status="member"), SimpleNamespace(status="administrator")]
        ))
        self.assertTrue(await user_has_required_memberships(bot, 123))
        self.assertEqual(bot.get_chat_member.await_count, 2)

    async def test_rejects_user_missing_any_required_chat(self):
        bot = SimpleNamespace(get_chat_member=AsyncMock(
            side_effect=[SimpleNamespace(status="member"), SimpleNamespace(status="left")]
        ))
        self.assertFalse(await user_has_required_memberships(bot, 123))

    async def test_allows_user_when_membership_lookup_is_forbidden(self):
        bot = SimpleNamespace(get_chat_member=AsyncMock(side_effect=RuntimeError("administrator required")))
        self.assertFalse(await user_has_required_memberships(bot, 123))

    async def test_joined_callback_acknowledges_and_opens_bot_after_both_memberships(self):
        bot = SimpleNamespace(get_chat_member=AsyncMock(
            side_effect=[SimpleNamespace(status="member"), SimpleNamespace(status="administrator")]
        ))
        query_message = SimpleNamespace(edit_text=AsyncMock())
        query = SimpleNamespace(data="membership:verify", answer=AsyncMock(), message=query_message)
        update = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(
            id=123456, full_name="Ana Pérez", first_name="Ana", username="ana"
        ))

        await button_callback(update, SimpleNamespace(bot=bot))

        query.answer.assert_awaited_once()
        self.assertEqual(bot.get_chat_member.await_count, 2)
        args, kwargs = query_message.edit_text.call_args
        self.assertIn("ʜᴏʟᴀ, ᴀɴᴀ", args[0])
        self.assertIsNotNone(kwargs["reply_markup"])

    async def test_joined_callback_keeps_prompt_when_membership_is_missing(self):
        bot = SimpleNamespace(get_chat_member=AsyncMock(return_value=SimpleNamespace(status="left")))
        query_message = SimpleNamespace(edit_text=AsyncMock())
        query = SimpleNamespace(data="membership:verify", answer=AsyncMock(), message=query_message)
        update = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(
            id=123456, full_name="Ana Pérez", first_name="Ana", username="ana"
        ))

        await button_callback(update, SimpleNamespace(bot=bot))

        query.answer.assert_awaited_once()
        self.assertIn("ᴜ́ɴᴇᴛᴇ ᴀ ᴄᴀɴᴀʟ ʏ ɢʀᴜᴘᴏ", query_message.edit_text.call_args.args[0])
        self.assertIsNotNone(query_message.edit_text.call_args.kwargs["reply_markup"])


class TxtCallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_convert_callback_sends_named_txt_attachment_to_chat(self):
        original_url = "https://files.example/app.apk"
        job = TransferTask(7935796405, 7935796405, "url", None, None)
        job.task_id = "abc123"
        job.state = "done"
        job.filename = "app.apk"
        job.part_urls = {0: original_url}
        query_message = SimpleNamespace(edit_text=AsyncMock(), reply_text=AsyncMock())
        query = SimpleNamespace(data="j:abc123:generate_txt", answer=AsyncMock(), message=query_message)
        update = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=7935796405))
        manager = SimpleNamespace(jobs={job.task_id: job})
        sent_documents = []

        async def capture_document(**kwargs):
            sent_documents.append({
                "chat_id": kwargs["chat_id"],
                "filename": kwargs["filename"],
                "content": kwargs["document"].read(),
                "caption": kwargs["caption"],
            })

        context = SimpleNamespace(
            application=SimpleNamespace(bot_data={"task_queue": manager}),
            bot=SimpleNamespace(send_document=AsyncMock(side_effect=capture_document)),
            user_data={},
        )

        await button_callback(update, context)

        self.assertEqual(len(sent_documents), 1)
        self.assertEqual(sent_documents[0]["chat_id"], job.chat_id)
        self.assertEqual(sent_documents[0]["filename"], "app.txt")
        self.assertEqual(sent_documents[0]["content"], (original_url + "\n").encode())
        self.assertIn("ᴛˣᴛ", sent_documents[0]["caption"])
        query_message.edit_text.assert_not_awaited()
        context.bot.send_document.assert_awaited_once()
        self.assertFalse(job.txt_generating)
        self.assertFalse(hasattr(job, "txt_url"))
