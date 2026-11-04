"""Use the system Wireshark engine to discover TV advertisements."""
import json
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from urllib.request import build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.parse import urlparse
from app import private_ip


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def read_metadata(ip, brand='samsung'):
    ip = private_ip(ip)
    url = f'http://{ip}:8001/api/v2/' if brand == 'samsung' else f'http://{ip}:8060/query/device-info'
    opener = build_opener(ProxyHandler({}), NoRedirect())
    with opener.open(url, timeout=2) as response:
        raw = response.read(262145)
    if len(raw) > 262144:
        raise ValueError('Respuesta de identificación demasiado grande.')
    if brand == 'samsung':
        data = json.loads(raw).get('device', {})
        if not isinstance(data, dict) or not any(key in data for key in ('modelName', 'TokenAuthSupport', 'type')):
            raise ValueError('La respuesta no identifica un Samsung compatible.')
        return dict(ip=ip, brand=brand, name=data.get('name') or 'Samsung', model=data.get('modelName', ''), verified=True)
    root = ET.fromstring(raw)
    if root.tag != 'device-info':
        raise ValueError('El equipo no respondió como Roku.')
    return dict(ip=ip, brand='roku', name=root.findtext('user-device-name') or 'Roku',
                model=root.findtext('model-name') or '', verified=True)


def candidate(ip, payload):
    try:
        ip = private_ip(ip)
        text = bytes.fromhex(payload.replace(':', '')).decode('utf-8', errors='replace')
    except ValueError:
        return None
    try:
        data = json.loads(text)
        uri = data.get('data', {}).get('v2', {}).get('uri', '')
        if data.get('type') == 'alive' and urlparse(uri).hostname == ip and '/api/v2/' in uri:
            return dict(ip=ip, brand='samsung', name='Samsung anunciado', model='', verified=False)
    except (ValueError, AttributeError):
        pass
    if not text.startswith(('HTTP/1.1 200', 'NOTIFY ')):
        return None
    lower = text.casefold()
    brand = 'samsung' if 'samsung' in lower else 'roku' if 'roku' in lower else 'lg' if 'webos' in lower or 'lge-com' in lower else ''
    return dict(ip=ip, brand=brand, name=brand.upper() + ' anunciado', model='', verified=False) if brand else None


def tshark():
    command = shutil.which('tshark')
    if not command:
        raise RuntimeError('No se encuentra TShark de Wireshark en el sistema.')
    return command


def interface_list():
    result = subprocess.run([tshark(), '-D'], capture_output=True, text=True, timeout=5)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'No se pudieron listar las interfaces.')
    return result.stdout


def discover(interface='any', capture_file=None):
    args = [tshark(), '-n']
    if capture_file:
        args += ['-r', str(capture_file)]
    else:
        args += ['-i', interface, '-a', 'duration:8', '-f', 'udp port 8001 or udp port 1900']
    args += ['-c', '2000', '-T', 'fields', '-E', 'separator=|', '-E', 'occurrence=f',
             '-e', 'ip.src', '-e', 'udp.payload']
    found = {}
    with tempfile.TemporaryFile(mode='w+b') as output, tempfile.TemporaryFile(mode='w+b') as errors:
        try:
            result = subprocess.run(args, stdout=output, stderr=errors, timeout=20)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('TShark excedió el tiempo de captura; revisa la interfaz.') from exc
        errors.seek(0)
        detail = errors.read(8000).decode('utf-8', errors='replace').strip()
        if result.returncode:
            raise RuntimeError(f'TShark no pudo leer/capturar: {detail or result.returncode}')
        output.seek(0)
        for line in output:
            parts = line.decode('utf-8', errors='replace').strip().split('|')
            if len(parts) != 2:
                continue
            item = candidate(*parts)
            if item:
                found[item['ip']] = item
    def enrich(item):
        if item['brand'] in ('samsung', 'roku'):
            try:
                return read_metadata(item['ip'], item['brand']), ''
            except Exception as exc:
                return item, f"{item['ip']}: anuncio detectado; no se pudo consultar nombre/modelo ({exc})"
        return item, item['ip'] + ': LG detectado; adaptador de control pendiente.'
    if not found:
        return [], ['No llegaron anuncios de TV en esta captura. Revisa interfaz, enciende el TV o usa agregar IP.']
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(enrich, found.values()))
    return [item for item, _ in results], [message for _, message in results if message]
