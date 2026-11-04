import queue
import time
import unittest
from websocket import ABNF, WebSocketTimeoutException, WebSocket
from unittest.mock import Mock
from keepalive import ConnectionKeeper


class Socket:
    def __init__(self, reply=True):
        self.frames = queue.Queue()
        self.pings = []
        self.reply = reply
    def settimeout(self, timeout):
        pass
    def ping(self, payload):
        self.pings.append(payload)
        if self.reply:
            self.frames.put((ABNF.OPCODE_PONG, payload))
    def recv_data(self, control_frame=False):
        try:
            return self.frames.get(timeout=.005)
        except queue.Empty:
            raise WebSocketTimeoutException()


def wait_until(predicate, timeout=1):
    end = time.monotonic() + timeout
    while not predicate() and time.monotonic() < end:
        time.sleep(.005)
    return predicate()


class KeepAliveTests(unittest.TestCase):
    def test_idle_connection_stays_alive_without_keypresses(self):
        socket = Socket()
        keeper = ConnectionKeeper(socket, interval=.02, pong_timeout=.08)
        try:
            self.assertTrue(wait_until(lambda: len(socket.pings) >= 3))
            self.assertTrue(keeper.alive)
            self.assertEqual(keeper.error, '')
        finally:
            keeper.stop()
        count = len(socket.pings)
        time.sleep(.03)
        self.assertEqual(len(socket.pings), count)
        self.assertFalse(keeper.thread.is_alive())

    def test_missing_pong_marks_connection_lost(self):
        keeper = ConnectionKeeper(Socket(reply=False), interval=.01, pong_timeout=.03)
        try:
            self.assertTrue(wait_until(lambda: not keeper.alive))
            self.assertIn('ping', keeper.error)
        finally:
            keeper.stop()

    def test_server_close_is_detected(self):
        socket = Socket()
        socket.frames.put((ABNF.OPCODE_CLOSE, b''))
        keeper = ConnectionKeeper(socket)
        try:
            self.assertTrue(wait_until(lambda: not keeper.alive))
            self.assertIn('cerró', keeper.error)
        finally:
            keeper.stop()

    def test_installed_websocket_answers_server_ping(self):
        socket = WebSocket()
        socket.recv_frame = Mock(return_value=ABNF.create_frame(b'ping-from-tv', ABNF.OPCODE_PING))
        socket.pong = Mock()
        opcode, _ = socket.recv_data(control_frame=True)
        self.assertEqual(opcode, ABNF.OPCODE_PING)
        socket.pong.assert_called_once_with(b'ping-from-tv')
