import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from ablesci.cli import main
from ablesci.models import Account, Outcome, OK, ERROR
from ablesci.notifications import send_mail
from ablesci.reports import build_bodies, write_step_summary


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.account = Account("甲 | <b>备注</b>", "private@example.com", "secret")
        self.outcome = Outcome(self.account, OK, '<img src=x> | 第一行\n第二行', "100", "7")
        env = patch.dict(os.environ, {k: v for k, v in os.environ.items() if k.upper() in ("SYSTEMROOT", "WINDIR", "SYSTEMDRIVE")}, clear=True)
        env.start()
        self.addCleanup(env.stop)

    def test_summary_escapes_html_and_table_delimiters(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "summary.md"
            os.environ["GITHUB_STEP_SUMMARY"] = str(path)
            write_step_summary([self.outcome])
            summary = path.read_text(encoding="utf-8")
        self.assertNotIn("<img", summary)
        self.assertNotIn("private@example.com", summary)
        self.assertIn("&#124;", summary)
        self.assertEqual(len(summary.splitlines()), 5)

    def test_mail_html_is_escaped(self):
        text, html = build_bodies([self.outcome])
        self.assertNotIn("private@example.com", text + html)
        self.assertNotIn("<img", html)
        self.assertIn("&lt;img", html)

    def configure_mail(self, **extra):
        os.environ.update(SMTP_HOST="smtp.example.com", SMTP_USER="mail@example.com", SMTP_PASS="smtp-secret", **extra)

    @patch("ablesci.notifications.smtplib.SMTP_SSL")
    def test_no_mail_configuration_is_noop(self, smtp):
        send_mail([self.outcome])
        smtp.assert_not_called()

    @patch("ablesci.notifications.smtplib.SMTP_SSL")
    def test_failure_only_and_never_do_not_send_success(self, smtp):
        for when in ("failure", "never"):
            self.configure_mail(MAIL_WHEN=when)
            with redirect_stdout(io.StringIO()):
                send_mail([self.outcome])
        smtp.assert_not_called()

    @patch("ablesci.notifications.smtplib.SMTP_SSL")
    def test_ssl_verifies_certificates(self, smtp):
        self.configure_mail()
        with redirect_stdout(io.StringIO()):
            send_mail([self.outcome])
        self.assertTrue(smtp.call_args.kwargs["context"].check_hostname)
        smtp.return_value.__enter__.return_value.send_message.assert_called_once()

    @patch("ablesci.notifications.smtplib.SMTP")
    def test_starttls_verifies_certificates(self, smtp):
        self.configure_mail(SMTP_PORT="587")
        with redirect_stdout(io.StringIO()):
            send_mail([self.outcome])
        server = smtp.return_value.__enter__.return_value
        self.assertTrue(server.starttls.call_args.kwargs["context"].check_hostname)
        server.send_message.assert_called_once()

    @patch("ablesci.notifications.smtplib.SMTP_SSL")
    def test_mail_failure_is_contained_and_private(self, smtp):
        self.configure_mail()
        smtp.side_effect = RuntimeError("smtp-secret")
        output = io.StringIO()
        with redirect_stdout(output):
            send_mail([self.outcome])
        self.assertNotIn("smtp-secret", output.getvalue())

    @patch("ablesci.notifications.smtplib.SMTP_SSL")
    def test_header_error_is_contained(self, smtp):
        self.configure_mail(MAIL_TO="a@example.com\nBcc: another@example.com")
        with redirect_stdout(io.StringIO()):
            send_mail([self.outcome])
        smtp.assert_not_called()

    @patch("ablesci.cli.send_mail")
    @patch("ablesci.cli.write_step_summary")
    @patch("ablesci.cli.run_account")
    def test_exit_code_tracks_account_failures(self, run, summary, mail):
        os.environ.update(ABLESCI_EMAIL="private@example.com", ABLESCI_PASSWORD="secret")
        for status, expected in ((OK, 0), (ERROR, 1)):
            run.return_value = Outcome(self.account, status, "结果")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main([]), expected)
        self.assertEqual(summary.call_count, 2)
        self.assertEqual(mail.call_count, 2)


if __name__ == "__main__":
    unittest.main()
