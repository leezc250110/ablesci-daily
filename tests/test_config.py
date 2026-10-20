import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from ablesci.config import ConfigError, collect_accounts, jitter_limit
from ablesci.cli import main


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_no_accounts_fails(self):
        with self.assertRaises(ConfigError):
            collect_accounts()

    def test_incomplete_slot_cannot_silently_succeed(self):
        os.environ.update(ABLESCI_1_EMAIL="one@example.com", ABLESCI_1_PASSWORD="valid", ABLESCI_2_EMAIL="two@example.com")
        with self.assertRaisesRegex(ConfigError, "ABLESCI_2"):
            collect_accounts()

    def test_legacy_incomplete_fails(self):
        os.environ["ABLESCI_PASSWORD"] = "secret"
        with self.assertRaises(ConfigError):
            collect_accounts()

    def test_cleanup_preserves_password_spaces(self):
        os.environ.update(ABLESCI_1_EMAIL="\ufeff one@example.com\r\n", ABLESCI_1_PASSWORD="\ufeff secret \r\n")
        account = collect_accounts()[0]
        self.assertEqual(account.email, "one@example.com")
        self.assertEqual(account.password, " secret ")
        self.assertNotIn("secret", repr(account))
        self.assertNotIn("one@example", repr(account))

    def test_json_and_slots_deduplicate(self):
        os.environ.update(ABLESCI_ACCOUNTS_JSON=json.dumps([{"email": "ONE@example.com", "password": "p", "name": "甲"}]), ABLESCI_1_EMAIL="one@example.com", ABLESCI_1_PASSWORD="p")
        self.assertEqual(len(collect_accounts()), 1)
        self.assertEqual(collect_accounts()[0].label, "甲")

    def test_conflicting_password_fails(self):
        os.environ.update(ABLESCI_1_EMAIL="one@example.com", ABLESCI_1_PASSWORD="a", ABLESCI_EMAIL="one@example.com", ABLESCI_PASSWORD="b")
        with self.assertRaises(ConfigError):
            collect_accounts()

    def test_invalid_json_is_private(self):
        for value in ('{"password":"SUPERSECRET",', '{}', '[]', '[1]', '[{"email":1}]'):
            with self.subTest(value=value):
                os.environ["ABLESCI_ACCOUNTS_JSON"] = value
                with self.assertRaises(ConfigError) as error:
                    collect_accounts()
                self.assertNotIn("SUPERSECRET", str(error.exception))

    def test_all_twenty_slots(self):
        for i in range(1, 21):
            os.environ[f"ABLESCI_{i}_EMAIL"] = f"{i}@example.com"
            os.environ[f"ABLESCI_{i}_PASSWORD"] = "password"
        self.assertEqual(len(collect_accounts()), 20)
        os.environ.update(ABLESCI_EMAIL="extra@example.com", ABLESCI_PASSWORD="password")
        with self.assertRaises(ConfigError):
            collect_accounts()

    def test_jitter_bounds(self):
        for value in ("abc", "-1", "1501"):
            os.environ["ABLESCI_JITTER_MAX"] = value
            with self.assertRaises(ConfigError):
                jitter_limit()
        os.environ["ABLESCI_JITTER_MAX"] = "0"
        self.assertEqual(jitter_limit(), 0)

    @patch("ablesci.cli.run_account")
    @patch("ablesci.cli.send_mail")
    @patch("ablesci.cli.AbleSciClient")
    def test_check_config_does_not_use_network(self, client, mail, run):
        os.environ.update(ABLESCI_EMAIL="one@example.com", ABLESCI_PASSWORD="p")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--check-config"]), 0)
        client.assert_not_called()
        mail.assert_not_called()
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
