"""Single terminal application: visual TV CRUD and remote control."""
import curses
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from app import saved_tv, private_ip
from inventory import Inventory
from discovery import discover


def launch():
    store = Inventory()
    saved = saved_tv()
    if not store.all() and saved:
        store.upsert(dict(ip=saved['ip'], name='TV2000', brand='samsung', verified=False))
    selected = 0
    query = ''
    message = 'Enter abre el mando. B busca televisores usando Wireshark del sistema.'
    future = None
    pool = ThreadPoolExecutor(max_workers=1)

    def draw(screen):
        nonlocal selected, query, message, future
        screen.keypad(True)
        screen.timeout(120)
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        blue = cyan = 0
        if curses.has_colors():
            curses.start_color()
            try:
                curses.use_default_colors()
                background = -1
            except curses.error:
                background = curses.COLOR_BLACK
            curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
            curses.init_pair(2, curses.COLOR_CYAN, background)
            blue, cyan = curses.color_pair(1), curses.color_pair(2)

        def put(y, x, value, style=0, limit=None):
            h, w = screen.getmaxyx()
            if 0 <= y < h - 1 and 0 <= x < w - 1:
                text = ''.join(c if c.isprintable() else ' ' for c in str(value))
                try:
                    screen.addnstr(y, x, text, min(w - x - 1, limit or w), style)
                except curses.error:
                    pass

        def prompt(label, default=''):
            # Normal terminal paste works here; Escape cancels the form.
            chars = list(str(default))
            screen.timeout(-1)
            try:
                curses.curs_set(1)
                while True:
                    h, w = screen.getmaxyx()
                    screen.move(h - 2, 0);screen.clrtoeol()
                    shown = label + ': ' + ''.join(chars)
                    offset = max(0, len(shown) - w + 4)
                    put(h - 2, 1, shown[offset:])
                    screen.refresh()
                    key = screen.get_wch()
                    if key in ('\n', '\r', curses.KEY_ENTER):
                        return ''.join(chars).strip()
                    if key == '\x1b':
                        return None
                    if key in ('\b', '\x7f', curses.KEY_BACKSPACE):
                        if chars:chars.pop()
                    elif key == '\x15':
                        chars.clear()
                    elif isinstance(key, str) and key.isprintable() and len(chars) < 512:
                        chars.append(key)
            finally:
                screen.timeout(120)
                curses.curs_set(0)

        def edit(item=None):
            nonlocal message
            name = prompt('Nombre (Ctrl+U borra, Esc cancela)', (item['alias'] or item['name']) if item else '')
            if name is None:return
            ip = prompt('IP del televisor', item['ip'] if item else '')
            if ip is None:return
            brand = prompt('Marca: samsung / roku / lg', item['brand'] if item else 'samsung')
            if brand is None:return
            private_ip(ip)
            if not name or len(name) > 80 or brand not in ('samsung', 'roku', 'lg'):
                raise ValueError('Nombre inválido o marca desconocida.')
            if item:
                store.update(item['id'], name, ip, brand)
            else:
                if any(d['ip'] == ip for d in store.all()):
                    raise ValueError('Esa IP ya existe; selecciona su ficha y pulsa E.')
                store.upsert(dict(ip=ip, brand=brand, name=name, verified=False))
            message = 'Control guardado. Entra con Enter para solicitar o reutilizar autorización.'

        while True:
            if future and future.done():
                try:
                    items, notes = future.result()
                    for item in items:store.upsert(item)
                    message = f'{len(items)} equipos encontrados. ' + (' | '.join(notes) if notes else 'Selecciona uno y pulsa Enter.')
                except Exception as exc:
                    message = 'Error de Wireshark/TShark: ' + str(exc)
                future = None
            rows = [d for d in store.all() if query.casefold() in ' '.join(str(d[k]) for k in ('alias', 'name', 'ip', 'brand', 'model')).casefold()]
            selected = min(selected, max(0, len(rows) - 1))
            item = rows[selected] if rows else None
            screen.erase()
            h, w = screen.getmaxyx()
            put(0, 0, ' ' * (w - 1), blue)
            put(0, 2, 'ORBIT  /  MIS CONTROLES REMOTOS', blue | curses.A_BOLD)
            put(2, 2, f'{len(rows)} controles  ·  ' + ('Buscando con Wireshark…' if future else 'Inventario local'), cyan)
            put(3, 2, 'Filtro: ' + (query or 'todos'), curses.A_DIM)
            put(5, 2, 'NOMBRE / IP / MARCA', curses.A_BOLD)
            split = max(36, w // 2)
            capacity = max(1, (h - 13) // 2)
            first = max(0, min(selected - capacity // 2, len(rows) - capacity))
            if w >= 70 and h >= 20:
                for line, d in enumerate(rows[first:first + capacity]):
                    attr = blue | curses.A_BOLD if first + line == selected else 0
                    put(7 + 2 * line, 2, f"{d['id']:02d}  {d['alias'] or d['name']}", attr, split - 4)
                    put(8 + 2 * line, 6, f"{d['ip']} · {d['brand']}", curses.A_DIM, split - 8)
                put(5, split, 'FICHA DEL CONTROL', cyan | curses.A_BOLD)
                if item:
                    token = Path(__file__).parent / '.data' / 'tokens' / (item['ip'] + '.token')
                    details = [item['alias'] or item['name'], 'IP: ' + item['ip'], 'Marca: ' + item['brand'],
                               'Modelo: ' + (item['model'] or 'Sin verificar'),
                               'Permiso: ' + ('token guardado' if token.exists() else 'se comprueba al conectar'),
                               'Última conexión: ' + (item['last_connected'] or 'no registrada'),
                               'ENTER → Abrir control remoto']
                    for line, value in enumerate(details):put(7 + line, split, value)
                else:
                    put(7, 2, 'Sin controles. N para crear; B para detectar TVs.')
            else:
                put(7, 2, 'Amplía la terminal a 70×20. Q para salir.')
            put(h - 5, 2, message, cyan)
            put(h - 3, 2, 'N crear  E editar  D eliminar  B buscar  I importar pcap  F filtrar', curses.A_BOLD)
            put(h - 2, 2, '↑↓ seleccionar  Enter mando  Q salir', blue | curses.A_BOLD)
            screen.refresh()
            key = screen.getch()
            if key in (ord('q'), ord('Q')):return None
            if w < 70 or h < 20:continue
            try:
                if key in (curses.KEY_UP, curses.KEY_DOWN) and rows:
                    selected = (selected + (-1 if key == curses.KEY_UP else 1)) % len(rows)
                elif key in (ord('n'), ord('N')):
                    edit()
                elif key in (ord('e'), ord('E')) and item:
                    edit(item)
                elif key in (ord('d'), ord('D')) and item:
                    if prompt(f"Eliminar {item['alias'] or item['name']}? Escribe SI") == 'SI':
                        store.delete(item['id'])
                        message = 'Ficha eliminada. Se conservan los tokens de autorización.'
                elif key in (ord('f'), ord('F')):
                    value = prompt('Filtro')
                    if value is not None:query=value;selected=0
                elif key == 27:
                    query='';selected=0
                elif key in (ord('b'), ord('B'), ord('i'), ord('I')) and future is None:
                    if key in (ord('i'), ord('I')):
                        path = prompt('Ruta del archivo pcap/pcapng')
                        if path:future=pool.submit(discover, capture_file=Path(path).expanduser())
                    else:
                        interface = prompt('Interfaz TShark (any = todas)', 'any')
                        if interface:future=pool.submit(discover, interface=interface)
                elif key in (10, 13, curses.KEY_ENTER) and item:
                    if future:
                        message = 'Espera a que termine la búsqueda antes de abrir el mando.'
                    elif item['brand'] not in ('samsung', 'roku'):
                        message = 'LG detectado, pero su adaptador de control aún no está implementado.'
                    else:
                        return item
            except Exception as exc:
                message = 'Error: ' + str(exc)

    try:
        while True:
            chosen = curses.wrapper(draw)
            if chosen is None:return
            from terminal import launch as remote
            try:
                remote(chosen['ip'], brand=chosen['brand'], title=chosen['alias'] or chosen['name'],
                       on_connected=lambda:store.connected(chosen['id']))
                message = 'Has vuelto al inventario. Los permisos siguen guardados.'
            except Exception as exc:
                message = 'No se pudo abrir el mando: ' + str(exc)
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
