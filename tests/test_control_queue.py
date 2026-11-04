import unittest
from control_queue import CommandQueue


class QueueTests(unittest.TestCase):
    def test_fast_presses_keep_order_without_unbounded_backlog(self):
        queue = CommandQueue(capacity=2)
        self.assertTrue(queue.push('Volumen +', now=0))
        self.assertTrue(queue.push('Silenciar', now=.1))
        self.assertFalse(queue.push('Inicio', now=.2))
        self.assertEqual(queue.pop(now=.3), 'Volumen +')
        self.assertEqual(queue.pop(now=.4), 'Silenciar')
        self.assertIsNone(queue.pop(now=.5))

    def test_stale_keys_are_not_sent_later(self):
        queue = CommandQueue(lifetime=2)
        queue.push('Volumen +', now=0)
        queue.push('Aceptar', now=2)
        self.assertEqual(queue.pop(now=2.5), 'Aceptar')
        self.assertEqual(queue.expired, 1)

    def test_discarding_queue_prevents_replay_after_reconnect(self):
        queue = CommandQueue()
        queue.push('Aceptar')
        queue.push('Silenciar')
        self.assertEqual(queue.clear(), 2)
        self.assertIsNone(queue.pop())
