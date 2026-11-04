"""Control local Samsung: autorización explícita y una sesión persistente."""
import argparse
import errno
import ipaddress
import json
import os
import tempfile
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.request import build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parent
KEYS = {'Inicio': 'KEY_HOME', 'Atrás': 'KEY_RETURN', 'Arriba': 'KEY_UP', 'Abajo': 'KEY_DOWN',
        'Izquierda': 'KEY_LEFT', 'Derecha': 'KEY_RIGHT', 'Aceptar': 'KEY_ENTER',
        'Volumen +': 'KEY_VOLUP', 'Volumen -': 'KEY_VOLDOWN', 'Silenciar': 'KEY_MUTE',
        'Canal +': 'KEY_CHUP', 'Canal -': 'KEY_CHDOWN', 'Reproducir/pausa': 'KEY_PLAYPAUSE'}


def private_ip(value):
    address = ipaddress.IPv4Address(str(value).strip())
    if not any(address in ipaddress.IPv4Network(net) for net in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')):
        raise ValueError('Introduce la IPv4 privada del TV, por ejemplo 192.168.1.50.')
    return str(address)


def saved_tv():
    try:
        data = json.loads((ROOT / '.data' / 'tv.json').read_text())
        return {'ip': private_ip(data['ip']), 'port': int(data.get('port', 8002))}
    except (OSError, ValueError, KeyError, TypeError):
        candidates = list((ROOT / '.data' / 'tokens').glob('*.token'))
        if len(candidates) == 1 and candidates[0].stat().st_size:
            try:
                return {'ip': private_ip(candidates[0].stem), 'port': 8002}
            except ValueError:
                pass
    return {}


def save_tv(ip, port):
    directory = ROOT / '.data'
    directory.mkdir(exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=directory, delete=False) as stream:
            name = stream.name
            json.dump({'ip': private_ip(ip), 'port': port}, stream)
        os.replace(name, directory / 'tv.json')
    finally:
        if name and Path(name).exists():
            Path(name).unlink()


def find_named_tv(name, candidates):
    if not isinstance(name, str) or not name.strip():
        raise ValueError('Indica el nombre del televisor.')
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 8:
        raise ValueError('Indica entre una y ocho IP candidatas.')
    addresses = list(dict.fromkeys(private_ip(ip) for ip in candidates))
    def normalize(value):
        value = str(value).strip().casefold()
        return value[4:].strip() if value.startswith('[tv]') else value
    def identify(ip):
        try:
            opener = build_opener(ProxyHandler({}))
            with opener.open(f'http://{ip}:8001/api/v2/', timeout=3) as response:
                raw = response.read(262145)
                if len(raw) > 262144:
                    raise ValueError('Respuesta demasiado grande')
            data = json.loads(raw)
            found = data.get('device', data).get('name', '')
            return ip, str(found), ''
        except Exception as exc:
            return ip, '', str(exc)
    with ThreadPoolExecutor(max_workers=len(addresses)) as pool:
        results = list(pool.map(identify, addresses))
    matches = [ip for ip, found, error in results if not error and normalize(found) == normalize(name)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError('Varios equipos tienen ese nombre. Selecciona su IP manualmente: ' + ', '.join(matches))
    details = ' | '.join(f'{ip}: {error or found or "sin nombre"}' for ip, found, error in results)
    raise ValueError(f'No se pudo identificar {name}. ' + details)


class Television:
    def __init__(self):
        self.remote = None
        self.host = ''
        self.key_delay = 0.08
        self.lock = threading.Lock()

    def disconnect(self):
        remote, self.remote = self.remote, None
        self.host = ''
        if remote:
            try:
                remote.close()
            except Exception:
                pass

    def connect(self, host):
        host = private_ip(host)
        try:
            from samsungtvws import SamsungTVWS
        except ImportError as exc:
            raise RuntimeError('Falta el adaptador Samsung. Ejecuta: .venv/bin/python -m pip install -r requirements.txt') from exc
        self.disconnect()
        directory = ROOT / '.data'
        directory.mkdir(exist_ok=True, mode=0o700)
        directory.chmod(0o700)
        tokens = directory / 'tokens'
        tokens.mkdir(parents=True, exist_ok=True, mode=0o700)
        tokens.chmod(0o700)
        token_file = tokens / (host + '.token')
        errors = []
        saved = saved_tv()
        ports = (8001, 8002) if saved.get('ip') == host and saved.get('port') == 8001 else (8002, 8001)
        for port in ports:
            remote = SamsungTVWS(host=host, port=port, name='ORBIT Remoto', token_file=str(token_file), timeout=10 if token_file.exists() else 30)
            try:
                remote.open()
                if token_file.exists():
                    token_file.chmod(0o600)
                save_tv(host, port)
                self.remote, self.host = remote, host
                return
            except Exception as exc:
                try:
                    remote.close()
                except Exception:
                    pass
                errors.append(f'Puerto {port}: {type(exc).__name__}: {exc}')
        raise RuntimeError('No se abrió el canal de control. Enciende el TV, comprueba la IP y acepta ORBIT Remoto en pantalla. ' + ' | '.join(errors))

    def send(self, label):
        if label not in KEYS:
            raise ValueError('Control desconocido.')
        if not self.remote:
            raise ValueError('Solicita conexión primero.')
        try:
            self.remote.send_key(KEYS[label], key_press_delay=self.key_delay)
        except Exception as exc:
            self.disconnect()
            raise RuntimeError('Falló el envío. Vuelve a solicitar conexión. No se ha repetido el comando automáticamente.') from exc


def make_server(port):
    tv = Television()
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def respond(self, code, payload, html=False):
            body = payload.encode() if html else json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'text/html; charset=utf-8' if html else 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def trusted(self):
            host = f'127.0.0.1:{self.server.server_port}'
            return self.headers.get('Host') == host and self.headers.get('Origin', 'http://' + host) == 'http://' + host

        def do_GET(self):
            if not self.trusted():
                return self.respond(403, {'error': 'Abre la URL 127.0.0.1 indicada en la terminal.'})
            if self.path == '/':
                return self.respond(200, (ROOT / 'static' / 'index.html').read_text().replace('__TOKEN__', token), True)
            self.respond(404, {'error': 'Página desconocida.'})

        def do_POST(self):
            if not self.trusted() or not secrets.compare_digest(self.headers.get('X-Session', ''), token):
                return self.respond(403, {'error': 'Sesión inválida. Recarga la página.'})
            if not tv.lock.acquire(blocking=False):
                return self.respond(409, {'error': 'Espera a que termine la operación actual.'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 1024:
                    raise ValueError('Petición inválida.')
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError('Petición inválida.')
                if self.path == '/connect-name':
                    ip = find_named_tv(data.get('name'), data.get('candidates'))
                    tv.connect(ip)
                    message = f'TV2000 identificado en {ip}; canal autorizado.'
                elif self.path == '/connect':
                    tv.connect(data.get('ip', ''))
                    message = 'El TV autorizó el canal de control.'
                elif self.path == '/send':
                    tv.send(data.get('key'))
                    message = 'Comando enviado. Comprueba la respuesta en el TV.'
                elif self.path == '/disconnect':
                    tv.disconnect()
                    message = 'Canal cerrado.'
                else:
                    return self.respond(404, {'error': 'Operación desconocida.'})
                self.respond(200, {'message': message, 'connected': tv.remote is not None, 'ip': tv.host})
            except Exception as exc:
                self.respond(400, {'error': str(exc), 'connected': tv.remote is not None, 'ip': tv.host})
            finally:
                tv.lock.release()

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    server.tv = tv
    return server


def available_server(port=8765, attempts=10):
    if not 1 <= port <= 65535:
        raise ValueError('El puerto debe estar entre 1 y 65535.')
    for candidate in range(port, min(65536, port + attempts)):
        try:
            return make_server(candidate)
        except OSError as exc:
            if exc.errno != errno.EADDRINUSE:
                raise
    raise OSError(errno.EADDRINUSE, f'Los puertos {port}–{min(65535, port + attempts - 1)} están ocupados. Elige otro con --port.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='ORBIT: inventario de televisores y control desde terminal.')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--shell', action='store_true', help='Usar prompt de comandos en vez del CRUD visual.')
    parser.add_argument('--web', action='store_true', help='Abrir interfaz web opcional.')
    parser.add_argument('--terminal', action='store_true', help='Abrir control de terminal con autorización guardada.')
    parser.add_argument('--ip', help='IPv4 del Samsung para el control de terminal.')
    args = parser.parse_args()
    try:
        if args.terminal or args.ip:
            from terminal import launch
            launch(args.ip)
            raise SystemExit(0)
        if not args.web:
            if args.shell:
                from console import launch
            else:
                from manager import launch
            launch()
            raise SystemExit(0)
        with available_server(args.port) as server:
            if server.server_port != args.port:
                print(f'Puerto {args.port} ocupado; usando {server.server_port}.', flush=True)
            print(f'Abre http://127.0.0.1:{server.server_port} — Ctrl+C para salir.', flush=True)
            try:
                server.serve_forever()
            finally:
                server.tv.disconnect()
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f'No se pudo iniciar ORBIT: {exc}\n')
