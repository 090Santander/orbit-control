import tempfile
import unittest
from pathlib import Path
from inventory import Inventory
from discovery import candidate


class InventoryTests(unittest.TestCase):
    def test_crud_and_rediscovery_preserve_alias_and_permissions(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Inventory(Path(folder) / 'inventory.sqlite3')
            token = Path(folder) / 'tokens' / '192.168.1.16.token'
            token.parent.mkdir();token.write_text('test-token')
            item = dict(ip='192.168.1.16', name='TV2000', brand='samsung', model='Model', verified=True)
            store.upsert(item)
            ident = store.all()[0]['id']
            store.rename(ident, 'TV sala')
            store.connected(ident)
            store.upsert(dict(item, name='Nombre anunciado'))
            reopened = Inventory(store.path)
            self.assertEqual(len(reopened.all()), 1)
            self.assertEqual(reopened.get(ident)['alias'], 'TV sala')
            self.assertTrue(reopened.get(ident)['last_connected'])
            reopened.delete(ident)
            self.assertEqual(reopened.all(), [])
            self.assertEqual(token.read_text(), 'test-token')

    def test_samsung_udp_8001_is_candidate_not_authorization(self):
        payload = b'{"type":"alive","data":{"v2":{"uri":"http://192.168.1.16:8001/api/v2/"}}}'.hex()
        found = candidate('192.168.1.16', payload)
        self.assertEqual(found['brand'], 'samsung')
        self.assertFalse(found['verified'])
        self.assertIsNone(candidate('192.168.1.20', payload))
        self.assertIsNone(candidate('192.168.1.16', b'M-SEARCH * HTTP/1.1\r\nST: samsung\r\n'.hex()))
