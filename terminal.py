"""Daily terminal remote, sharing the web adapter and authorization tokens."""
import curses
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from app import Television, saved_tv, private_ip, find_named_tv, ROOT


def launch(ip=None, brand='samsung', title='TV2000', on_connected=None):
    if brand == 'roku':
        from roku import RokuTelevision
        tv = RokuTelevision()
    else:
        tv = Television()
    target = private_ip(ip) if ip else saved_tv().get('ip', '')
    pool = ThreadPoolExecutor(max_workers=1)

    def connect():
        nonlocal target
        if not target:
            target = find_named_tv('TV2000', ['192.168.1.16', '192.168.1.20'])
        tv.connect(target)
        if on_connected:
            on_connected()

    def draw(screen):
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        colors = {}
        if curses.has_colors():
            curses.start_color()
            background = curses.COLOR_BLACK
            try:
                curses.use_default_colors()
                background = -1
            except curses.error:
                pass
            for index, (name, fg, bg) in enumerate((("title", curses.COLOR_WHITE, curses.COLOR_BLUE),
                    ("line", curses.COLOR_BLUE, background), ("accent", curses.COLOR_CYAN, background),
                    ("ok", curses.COLOR_GREEN, background), ("error", curses.COLOR_RED, background)), 1):
                curses.init_pair(index, fg, bg)
                colors[name] = curses.color_pair(index)
        def color(name):
            return colors.get(name, 0)
        mouse = False
        flash_until = 0
        screen.timeout(100)
        screen.keypad(True)
        events = deque(maxlen=100)
        def log(text):
            events.append(time.strftime('%H:%M:%S') + '  ' + str(text))
        future = pool.submit(connect)
        operation = 'Conectar'
        sent = 0
        log('Conectando con autorización guardada. Revisa el TV si solicita permiso.')
        bindings = {curses.KEY_UP: 'Arriba', curses.KEY_DOWN: 'Abajo',
                    curses.KEY_LEFT: 'Izquierda', curses.KEY_RIGHT: 'Derecha',
                    10: 'Aceptar', 13: 'Aceptar', curses.KEY_ENTER: 'Aceptar',
                    27: 'Atrás', ord('b'): 'Atrás', ord('h'): 'Inicio',
                    ord('+'): 'Volumen +', ord('='): 'Volumen +', ord('-'): 'Volumen -',
                    ord('m'): 'Silenciar', ord('['): 'Canal -', ord(']'): 'Canal +',
                    ord(' '): 'Reproducir/pausa'}
        while True:
            if future and future.done():
                try:
                    future.result()
                    if operation == 'Conectar':
                        log('Canal Samsung autorizado y guardado.' if brand == 'samsung' else 'Roku identificado. El acceso se comprueba al enviar controles.')
                    else:
                        sent += 1
                        log(operation + ' · enviado')
                except Exception as exc:
                    log('ERROR: ' + str(exc))
                future = None
            screen.erase()
            height, width = screen.getmaxyx()
            def put(y, text, style=0, x=1, limit=None):
                if 0 <= y < height - 1 and 0 <= x < width - 1:
                    try:
                        value = ''.join(c if c.isprintable() else ' ' for c in str(text))
                        screen.addnstr(y, x, value, min(width - x - 1, limit or width), style)
                    except curses.error:
                        pass
            hits = []
            def box(y, x, w, h, label):
                put(y, '╭' + '─' * (w - 2) + '╮', color('line'), x)
                for row in range(y + 1, y + h - 1):
                    put(row, '│', color('line'), x)
                    put(row, '│', color('line'), x + w - 1)
                put(y + h - 1, '╰' + '─' * (w - 2) + '╯', color('line'), x)
                put(y, ' ' + label + ' ', color('accent') | curses.A_BOLD, x + 2, w - 4)
            def button(y, x, label, action, w=12):
                active = operation == action and (future is not None or time.monotonic() < flash_until)
                style = color('title') | curses.A_BOLD if active else color('accent') if tv.remote else curses.A_DIM
                put(y, ('[ ' + label + ' ]').center(w), style, x, w)
                hits.append((y, x, x + w, action))
            put(0, ' ' * (width - 1), color('title'), 0)
            put(0, ' ORBIT  /  CONTROL REMOTO', color('title') | curses.A_BOLD)
            state = 'CONECTANDO' if future and operation == 'Conectar' else 'ENVIANDO' if future else 'CANAL AUTORIZADO' if tv.remote and brand == 'samsung' else 'ROKU IDENTIFICADO' if tv.remote else 'DESCONECTADO'
            put(2, title, curses.A_BOLD | color('accent'))
            put(3, f'{state}  ·  {tv.host or target or "buscando TV2000"}', color('ok') if tv.remote else color('accent'))
            token = ROOT / '.data' / 'tokens' / f'{tv.host or target}.token'
            permission = 'Acceso por aplicaciones Roku' if brand == 'roku' else 'Token guardado' if token.exists() else 'Sin token guardado'
            if width >= 78 and height >= 26:
                left = min(46, width // 2)
                box(5, 1, left, 19, 'MANDO')
                center = 1 + left // 2 - 6
                button(7, 4, 'H Inicio', 'Inicio', 16)
                button(7, 1 + left - 20, 'B Atrás', 'Atrás', 16)
                button(10, center, '↑', 'Arriba')
                button(12, center - 12, '←', 'Izquierda')
                button(12, center, 'ENTER / OK', 'Aceptar')
                button(12, center + 12, '→', 'Derecha')
                button(14, center, '↓', 'Abajo')
                button(17, 4, '− VOL', 'Volumen -', 16)
                button(17, 1 + left - 20, '+ VOL', 'Volumen +', 16)
                button(19, 4, '[ CANAL', 'Canal -', 16)
                button(19, 1 + left - 20, '] CANAL', 'Canal +', 16)
                button(21, 4, 'M Silencio', 'Silenciar', 16)
                button(21, 1 + left - 20, '␣ Play/Pausa', 'Reproducir/pausa', 16)
                x = left + 3
                panel_width = width - x - 2
                box(5, x, panel_width, 7, 'SESIÓN')
                put(7, permission, color('accent'), x + 2, panel_width - 4)
                put(8, f'Comandos enviados: {sent}', 0, x + 2, panel_width - 4)
                put(9, 'Ratón: ' + ('clics activos' if mouse else 'selección de texto'), 0, x + 2, panel_width - 4)
                box(13, x, panel_width, 11, 'ACTIVIDAD')
                for row, event in enumerate(list(events)[-8:], 15):
                    put(row, event, color('error') if 'ERROR:' in event else 0, x + 2, panel_width - 4)
            else:
                for row, text in enumerate(('Flechas navegar · Enter aceptar', 'H inicio · B/Esc atrás · M silencio',
                    '+/− volumen · [/] canal · Espacio play/pausa', permission), 5):
                    put(row, text, color('accent') if row == 5 else 0)
                put(10, 'ACTIVIDAD', curses.A_BOLD | color('line'))
                capacity = max(0, height - 14)
                for row, event in enumerate(list(events)[-capacity:] if capacity else [], 11):
                    put(row, event, color('error') if 'ERROR:' in event else 0)
            put(height - 2, ' Q volver al inventario   R reconectar   T activar/desactivar clics ', color('title') | curses.A_BOLD)
            screen.refresh()
            key = screen.getch()
            if key in (ord('q'), ord('Q')):
                return
            action = bindings.get(key)
            if key in (ord('t'), ord('T')):
                mouse = not mouse
                curses.mousemask(curses.BUTTON1_PRESSED if mouse else 0)
            elif key == curses.KEY_MOUSE and mouse:
                try:
                    _, mx, my, _, flags = curses.getmouse()
                    if flags & curses.BUTTON1_PRESSED:
                        action = next((a for y, left, right, a in hits if my == y and left <= mx < right), None)
                except curses.error:
                    pass
            if key in (ord('r'), ord('R')) and future is None:
                operation = 'Conectar'
                future = pool.submit(connect)
                log('Reconectando…')
            elif action and future is None:
                if tv.remote is None:
                    log('Sin conexión. Pulsa R para reintentar.')
                else:
                    operation = action
                    flash_until = time.monotonic() + .25
                    future = pool.submit(tv.send, operation)
    try:
        curses.wrapper(draw)
    except curses.error as exc:
        raise RuntimeError('Ejecuta el control en una terminal interactiva con TERM configurado.') from exc
    finally:
        # Finish the current operation before closing its socket.
        pool.shutdown(wait=True, cancel_futures=True)
        tv.disconnect()
