"""SQLite TV inventory. Authorization files are kept separate."""
from contextlib import contextmanager
import sqlite3
import time
from pathlib import Path
from app import ROOT, private_ip


class Inventory:
    def __init__(self, path=None):
        self.path = Path(path) if path else ROOT / '.data' / 'inventory.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        with self.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS televisions (
                id INTEGER PRIMARY KEY, ip TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
                alias TEXT NOT NULL DEFAULT '', brand TEXT NOT NULL, model TEXT NOT NULL DEFAULT '',
                verified INTEGER NOT NULL DEFAULT 0, last_seen TEXT NOT NULL,
                last_connected TEXT NOT NULL DEFAULT '')''')
        self.path.chmod(0o600)

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def all(self):
        with self.db() as db:
            return [dict(row) for row in db.execute('SELECT * FROM televisions ORDER BY id')]

    def get(self, ident):
        with self.db() as db:
            row = db.execute('SELECT * FROM televisions WHERE id=?', (int(ident),)).fetchone()
        if row is None:
            raise ValueError('No existe ese ID. Usa equipos para listar.')
        return dict(row)

    def upsert(self, item):
        ip = private_ip(item['ip'])
        brand = item['brand']
        if brand not in ('samsung', 'roku', 'lg'):
            raise ValueError('Fabricante no reconocido.')
        with self.db() as db:
            db.execute('''INSERT INTO televisions(ip,name,brand,model,verified,last_seen) VALUES(?,?,?,?,?,?)
                ON CONFLICT(ip) DO UPDATE SET name=excluded.name,brand=excluded.brand,
                model=CASE WHEN excluded.model<>'' THEN excluded.model ELSE televisions.model END,
                verified=excluded.verified,last_seen=excluded.last_seen''',
                (ip, str(item.get('name') or brand), brand, str(item.get('model') or ''),
                 int(bool(item.get('verified'))), time.strftime('%Y-%m-%d %H:%M:%S')))

    def rename(self, ident, alias):
        self.get(ident)
        alias = alias.strip()
        if not alias or len(alias) > 80:
            raise ValueError('El nombre debe tener entre 1 y 80 caracteres.')
        with self.db() as db:
            db.execute('UPDATE televisions SET alias=? WHERE id=?', (alias, int(ident)))

    def update(self, ident, alias, ip, brand):
        current = self.get(ident)
        ip = private_ip(ip)
        alias = alias.strip()
        if not alias or len(alias) > 80 or brand not in ('samsung', 'roku', 'lg'):
            raise ValueError('Indica un nombre de 1–80 caracteres y marca samsung, roku o lg.')
        changed = ip != current['ip'] or brand != current['brand']
        with self.db() as db:
            db.execute("""UPDATE televisions SET alias=?,ip=?,brand=?,
                model=CASE WHEN ? THEN '' ELSE model END,
                verified=CASE WHEN ? THEN 0 ELSE verified END,
                last_connected=CASE WHEN ? THEN '' ELSE last_connected END WHERE id=?""",
                (alias, ip, brand, changed, changed, changed, int(ident)))

    def delete(self, ident):
        self.get(ident)
        with self.db() as db:
            db.execute('DELETE FROM televisions WHERE id=?', (int(ident),))

    def connected(self, ident):
        with self.db() as db:
            db.execute('UPDATE televisions SET last_connected=? WHERE id=?',
                       (time.strftime('%Y-%m-%d %H:%M:%S'), int(ident)))
