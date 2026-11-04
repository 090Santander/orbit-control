"""Daily terminal remote, sharing the web adapter and authorization tokens."""
import curses
import time
import textwrap
from control_queue import CommandQueue
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
        screen.timeout(20)
        screen.keypad(True)
        events = deque(maxlen=100)
        def log(text):
            events.append(time.strftime('%H:%M:%S') + '  ' + str(text))
        future = pool.submit(connect)
        operation = 'Conectar'
        sent = 0
        pending = CommandQueue()
        log_view = False
        log_offset = 0
        latency = None
        operation_started = time.monotonic()
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
                        latency = round((time.monotonic() - operation_started) * 1000)
                        log(operation + f' · enviado en {latency} ms')
                except Exception as exc:
                    pending.clear()
                    log('ERROR: ' + str(exc))
                    log('Cola cancelada. No se repetirán comandos al reconectar.')
                future = None
            if future is None and tv.remote and not log_view:
                expired_before = pending.expired
                next_action = pending.pop()
                if pending.expired > expired_before:
                    log(f'{pending.expired - expired_before} órdenes antiguas descartadas.')
                if next_action:
                    operation = next_action
                    flash_until = time.monotonic() + .25
                    operation_started = time.monotonic()
                    future = pool.submit(tv.send, operation)
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
            state = 'CONECTANDO' if future and operation == 'Conectar' else 'ENVIANDO' if future else 'CANAL ABIERTO' if tv.remote and brand == 'samsung' else 'ROKU IDENTIFICADO' if tv.remote else 'DESCONECTADO'
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
                put(8, f'Envíos: {sent} · Ritmo: {round(tv.key_delay * 1000)} ms' if brand == 'samsung' else f'Comandos enviados: {sent}', 0, x + 2, panel_width - 4)
                put(9, f'Cola: {len(pending)}/8  ·  Último envío: {str(latency) + " ms" if latency is not None else "—"}', 0, x + 2, panel_width - 4)
                put(10, 'Ratón: ' + ('clics activos' if mouse else 'selección de texto'), 0, x + 2, panel_width - 4)
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
            if log_view:
                screen.erase()
                put(0, 'ORBIT / HISTORIAL COMPLETO', color('title') | curses.A_BOLD)
                lines = [line for event in events for line in textwrap.wrap(event, max(10, width - 4))]
                capacity = max(1, height - 5)
                log_offset = min(log_offset, max(0, len(lines) - capacity))
                end = max(0, len(lines) - log_offset)
                for row, line in enumerate(lines[max(0, end - capacity):end], 2):
                    put(row, line)
                put(height - 2, '↑↓ desplazar · L/Esc volver al mando · Q salir', color('title') | curses.A_BOLD)
            else:
                put(height - 2, 'Q volver  R conectar  T ratón  L historial  C cancelar  V ritmo', color('title') | curses.A_BOLD)
            screen.refresh()
            key = screen.getch()
            if key in (ord('q'), ord('Q')):
                return
            if key in (ord('l'), ord('L')) or (key == 27 and log_view):
                log_view = not log_view
                pending.clear()
                continue
            if log_view:
                if key == curses.KEY_UP:
                    log_offset += 1
                elif key == curses.KEY_DOWN:
                    log_offset = max(0, log_offset - 1)
                continue
            if key in (ord('v'), ord('V')):
                if brand == 'samsung' and future is None:
                    values = (0.08, 0.15, 0.3)
                    tv.key_delay = values[(values.index(tv.key_delay) + 1) % len(values)]
                    log(f'Separación entre teclas: {round(tv.key_delay * 1000)} ms')
                elif future:
                    log('Espera a que termine el envío para cambiar el ritmo.')
                continue
            if key in (ord('c'), ord('C')):
                log(f'{pending.clear()} órdenes pendientes canceladas; el envío en curso termina.')
                continue
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
                pending.clear()
                operation = 'Conectar'
                future = pool.submit(connect)
                log('Reconectando…')
            elif action:
                if tv.remote is None:
                    log('Sin conexión. Pulsa R para reintentar.')
                else:
                    if not pending.push(action):
                        log('Cola llena: pulsación descartada. C cancela las pendientes.')
    try:
        curses.wrapper(draw)
    except curses.error as exc:
        raise RuntimeError('Ejecuta el control en una terminal interactiva con TERM configurado.') from exc
    finally:
        # Finish the current operation before closing its socket.
        pool.shutdown(wait=True, cancel_futures=True)
        tv.disconnect()
