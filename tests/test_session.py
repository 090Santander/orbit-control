import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import app


class SessionTests(unittest.TestCase):
    def test_reuses_existing_token_and_remembers_successful_port(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app, 'ROOT', Path(folder)):
            tokens = Path(folder) / '.data' / 'tokens'
            tokens.mkdir(parents=True)
            token = tokens / '192.168.1.16.token'
            token.write_text('test-authorization')
            self.assertEqual(app.saved_tv()['ip'], '192.168.1.16')
            remote = Mock()
            factory = Mock(return_value=remote)
            with patch.dict('sys.modules', {'samsungtvws': SimpleNamespace(SamsungTVWS=factory)}):
                tv = app.Television()
                tv.connect('192.168.1.16')
                tv.send('Volumen +')
                tv.disconnect()
                tv.connect('192.168.1.16')
                self.assertEqual(factory.call_args.kwargs['token_file'], str(token))
                self.assertEqual(token.read_text(), 'test-authorization')
                self.assertEqual(app.saved_tv(), {'ip': '192.168.1.16', 'port': 8002})
                self.assertEqual(token.stat().st_mode & 0o777, 0o600)
                self.assertEqual((Path(folder) / '.data' / 'tv.json').stat().st_mode & 0o777, 0o600)
                remote.send_key.assert_called_once_with('KEY_VOLUP')

    def test_rejected_connection_does_not_replace_saved_tv(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app, 'ROOT', Path(folder)):
            app.save_tv('192.168.1.16', 8002)
            remote = Mock()
            remote.open.side_effect = RuntimeError('rejected')
            with patch.dict('sys.modules', {'samsungtvws': SimpleNamespace(SamsungTVWS=Mock(return_value=remote))}):
                tv = app.Television()
                with self.assertRaises(RuntimeError):
                    tv.connect('192.168.1.20')
                self.assertIsNone(tv.remote)
                self.assertEqual(app.saved_tv()['ip'], '192.168.1.16')

    def test_remembers_port_without_losing_token_on_exit(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app, 'ROOT', Path(folder)):
            app.save_tv('192.168.1.16', 8001)
            remote = Mock()
            factory = Mock(return_value=remote)
            with patch.dict('sys.modules', {'samsungtvws': SimpleNamespace(SamsungTVWS=factory)}):
                tv = app.Television()
                tv.connect('192.168.1.16')
                self.assertEqual(factory.call_args.kwargs['port'], 8001)
                tv.disconnect()
                self.assertEqual(app.saved_tv()['port'], 8001)
