"""Maintain an open WebSocket without sending TV key presses."""
import threading
import time


class ConnectionKeeper:
    def __init__(self, connection, interval=20, pong_timeout=15):
        self.connection = connection
        self.interval = interval
        self.pong_timeout = pong_timeout
        self.error = ''
        self.alive = True
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name='orbit-keepalive', daemon=True)
        # Bound reads so leaving ORBIT does not wait for an idle socket forever.
        self.connection.settimeout(1)
        self.thread.start()

    def _run(self):
        from websocket import ABNF, WebSocketTimeoutException
        next_ping = time.monotonic() + self.interval
        awaiting = None
        try:
            while not self.stop_event.is_set():
                now = time.monotonic()
                if awaiting is not None and now - awaiting >= self.pong_timeout:
                    raise TimeoutError('El TV no respondió al ping WebSocket.')
                if awaiting is None and now >= next_ping:
                    self.connection.ping(b'orbit-keepalive')
                    awaiting = now
                try:
                    opcode, payload = self.connection.recv_data(control_frame=True)
                except (WebSocketTimeoutException, TimeoutError):
                    continue
                if opcode == ABNF.OPCODE_CLOSE:
                    raise ConnectionError('El TV cerró el canal WebSocket.')
                if opcode == ABNF.OPCODE_PONG and payload == b'orbit-keepalive':
                    awaiting = None
                    next_ping = time.monotonic() + self.interval
                # websocket-client automatically answers server PING frames in recv_data.
        except Exception as exc:
            if not self.stop_event.is_set():
                self.error = str(exc)
        finally:
            self.alive = False

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=2)
        if self.thread.is_alive():
            self.connection.shutdown()
            self.thread.join(timeout=1)
