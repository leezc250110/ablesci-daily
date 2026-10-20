import unittest
from unittest.mock import Mock, patch

import requests

from ablesci.client import AbleSciClient, ResponseError, extract_csrf, parse_json
from ablesci.models import Account, ALREADY, CAPTCHA, ERROR, FAILED, OK
from ablesci.runner import run_account


class ClientTests(unittest.TestCase):
    def test_csrf_attribute_order_entities_and_quotes(self):
        self.assertEqual(extract_csrf("<input value='a&amp;b' type='hidden' name='_csrf'>"), "a&b")
        self.assertEqual(extract_csrf('<META content="meta" name="csrf-token">'), "meta")
        self.assertEqual(extract_csrf('<input value="old" id="csrf-val">'), "old")

    def test_csrf_prefers_form_over_meta(self):
        self.assertEqual(extract_csrf('<meta name="csrf-token" content="meta"><input name="_csrf" value="form">'), "form")
        with self.assertRaises(ResponseError):
            extract_csrf('<html>blocked</html>')

    def test_invalid_json_shapes(self):
        for value in ([], None, 0, {}, {"code": False}, {"code": 0, "msg": []}):
            with self.subTest(value=value):
                response = Mock()
                response.json.return_value = value
                with self.assertRaises(ResponseError):
                    parse_json(response)

    def test_non_json_does_not_echo_body(self):
        response = Mock(status_code=200, text="SUPERSECRET")
        response.json.side_effect = ValueError("SUPERSECRET")
        with self.assertRaises(ResponseError) as error:
            parse_json(response)
        self.assertNotIn("SUPERSECRET", str(error.exception))

    def test_http_error_precedes_json(self):
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError()
        with self.assertRaises(requests.HTTPError):
            parse_json(response)
        response.json.assert_not_called()

    @patch("ablesci.client.requests.Session")
    def test_login_fetches_new_csrf_each_time(self, session_factory):
        session = session_factory.return_value
        session.get.side_effect = [Mock(text='<input name="_csrf" value="one">'), Mock(text='<input name="_csrf" value="two">')]
        session.post.return_value.json.return_value = {"code": 0}
        client = AbleSciClient()
        client.login("user", "pass")
        client.login("user", "pass")
        self.assertEqual([c.kwargs["data"]["_csrf"] for c in session.post.call_args_list], ["one", "two"])
        client.close()
        session.close.assert_called_once()


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.account = Account("甲", "private@example.com", "SUPERSECRET")
        patcher = patch("ablesci.runner.AbleSciClient")
        self.factory = patcher.start()
        self.addCleanup(patcher.stop)
        sleeper = patch("ablesci.runner.time.sleep")
        sleeper.start()
        self.addCleanup(sleeper.stop)
        self.client = self.factory.return_value
        self.client.login.return_value = {"code": 0}
        self.client.sign.return_value = {"code": 0, "msg": "成功"}
        self.client.stats.return_value = ("100", "7")

    def test_success_and_close(self):
        result = run_account(self.account)
        self.assertEqual((result.status, result.points, result.streak), (OK, "100", "7"))
        self.client.close.assert_called_once()

    def test_captcha_is_never_retried(self):
        for payload in ({"code": 1, "msg": "验证码"}, {"code": 1, "verify": 1}):
            self.client.reset_mock()
            self.client.login.return_value = payload
            self.assertEqual(run_account(self.account).status, CAPTCHA)
            self.assertEqual(self.client.login.call_count, 1)
            self.client.sign.assert_not_called()
            self.client.close.assert_called_once()

    def test_wrong_password_redacted_and_no_retry(self):
        self.client.login.return_value = {"code": 1, "msg": "private@example.com SUPERSECRET 错误"}
        result = run_account(self.account)
        self.assertEqual(result.status, FAILED)
        self.assertNotIn(self.account.email, result.message)
        self.assertNotIn(self.account.password, result.message)
        self.client.login.assert_called_once()

    def test_login_network_retry_is_bounded(self):
        self.client.login.side_effect = requests.Timeout("SUPERSECRET")
        result = run_account(self.account)
        self.assertEqual(result.status, ERROR)
        self.assertEqual(self.client.login.call_count, 2)
        self.assertEqual(self.client.close.call_count, 2)
        self.assertNotIn("SUPERSECRET", result.message)

    def test_sign_network_error_does_not_resubmit(self):
        self.client.sign.side_effect = requests.Timeout()
        self.assertEqual(run_account(self.account).status, ERROR)
        self.client.sign.assert_called_once()

    def test_lost_session_retry(self):
        self.client.sign.side_effect = [{"code": 1, "msg": "需要登录"}, {"code": 0}]
        self.assertEqual(run_account(self.account).status, OK)
        self.assertEqual(self.client.close.call_count, 2)

    def test_already_requires_specific_message(self):
        for msg, expected in (("签到失败，您今天已于 [13:45] 签到。", ALREADY), ("账号已被限制", FAILED), ("今天暂时无法签到", FAILED)):
            self.client.sign.return_value = {"code": 1, "msg": msg}
            self.assertEqual(run_account(self.account).status, expected)

    def test_malformed_response_closes_session(self):
        self.client.login.side_effect = ResponseError("无效响应")
        self.assertEqual(run_account(self.account).status, ERROR)
        self.client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
