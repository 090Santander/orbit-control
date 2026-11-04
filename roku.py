"""Roku ECP adapter; device-side external-control settings govern access."""
from urllib.request import build_opener, ProxyHandler
from discovery import read_metadata, NoRedirect
from app import private_ip


class RokuTelevision:
    def __init__(self):
        self.host = ''
        self.remote = None

    def connect(self, host):
        self.disconnect()
        host = private_ip(host)
        read_metadata(host, 'roku')
        self.host, self.remote = host, True

    def disconnect(self):
        self.host, self.remote = '', None

    def send(self, label):
        keys = {'Inicio':'Home', 'Atrás':'Back', 'Arriba':'Up', 'Abajo':'Down',
                'Izquierda':'Left', 'Derecha':'Right', 'Aceptar':'Select',
                'Volumen +':'VolumeUp', 'Volumen -':'VolumeDown', 'Silenciar':'VolumeMute',
                'Canal +':'ChannelUp', 'Canal -':'ChannelDown', 'Reproducir/pausa':'Play'}
        if not self.remote:
            raise ValueError('Roku desconectado.')
        if label not in keys:
            raise ValueError('Acción no compatible.')
        try:
            opener = build_opener(ProxyHandler({}), NoRedirect())
            with opener.open(f'http://{self.host}:8060/keypress/{keys[label]}', data=b'', timeout=3) as response:
                response.read(1024)
        except Exception as exc:
            self.disconnect()
            raise RuntimeError('Roku rechazó o no respondió al control. Revisa el acceso por aplicaciones en el TV.') from exc
