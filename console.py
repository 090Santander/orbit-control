"""Terminal-first CRUD and system-Wireshark discovery."""
import shlex
from pathlib import Path
from app import saved_tv
from discovery import discover, interface_list, read_metadata, tshark
from inventory import Inventory


def clean(value):
    return ''.join(c if c.isprintable() else ' ' for c in str(value))


def launch():
    store = Inventory()
    saved = saved_tv()
    if not store.all() and saved:
        store.upsert(dict(ip=saved['ip'], brand='samsung', name='TV2000', verified=False))
    try:
        import readline
        commands = ['ayuda', 'interfaces', 'buscar', 'importar', 'equipos', 'agregar', 'editar', 'eliminar', 'ver', 'control', 'salir']
        def complete(text, index):
            matches = [c for c in commands if c.startswith(text)]
            return matches[index] if index < len(matches) else None
        readline.set_completer(complete)
        readline.parse_and_bind('tab: complete')
    except ImportError:
        pass
    print('ORBIT · Inventario y control de televisores\nEscribe ayuda. Puedes pegar IP y rutas; Tab completa comandos.')
    def listing():
        rows = store.all()
        print(f"{'ID':<4} {'NOMBRE':<24} {'IP':<16} {'MARCA':<9} MODELO")
        for item in rows:
            print(f"{item['id']:<4} {clean(item['alias'] or item['name'])[:23]:<24} {item['ip']:<16} {item['brand']:<9} {clean(item['model'])}")
        if not rows:
            print('Inventario vacío. Usa buscar o agregar IP.')
    if not store.all():
        print('Inventario vacío: búsqueda automática con Wireshark/TShark…')
        try:
            items, notes = discover()
            for item in items:
                store.upsert(item)
            for note in notes:
                print(clean(note))
        except Exception as exc:
            print('No se pudo descubrir automáticamente: ' + clean(exc))
    listing()
    while True:
        try:
            args = shlex.split(input('\norbit> '))
            if not args:
                continue
            command, *params = args
            if command in ('salir', 'q', 'exit'):
                return
            if command == 'ayuda':
                print('''interfaces                  Listar interfaces de Wireshark del sistema
buscar [interfaz]            Capturar anuncios de TV durante 8 segundos
importar "ruta.pcapng"       Detectar TVs desde una grabación Wireshark
agregar IP [samsung|roku]    Identificar y guardar un equipo por IP
equipos                     Listar inventario guardado
ver ID                      Ver ficha y última conexión
editar ID nuevo nombre      Cambiar alias sin perder permisos
eliminar ID                 Borrar ficha con confirmación; conserva tokens
control [ID]                Abrir control; reutiliza autorización guardada
salir                       Cerrar ORBIT

Buscar e importar detectan Samsung (UDP 8001), Samsung/Roku/LG por SSDP.
Detectar no autoriza. Samsung solicita permiso al conectar si no hay token válido.
Roku requiere control por aplicaciones habilitado. LG aún no tiene adaptador.''')
            elif command == 'interfaces':
                print(clean(tshark()))
                print(interface_list())
            elif command in ('buscar', 'importar'):
                if len(params) > 1 or command == 'importar' and not params:
                    raise ValueError('Uso: buscar [interfaz] o importar "ruta.pcapng"')
                print('Leyendo anuncios con Wireshark/TShark del sistema…')
                items, notes = discover(interface=params[0] if params and command == 'buscar' else 'any',
                                        capture_file=Path(params[0]).expanduser() if command == 'importar' else None)
                for item in items:
                    store.upsert(item)
                for note in notes:
                    print(clean(note))
                print(f'{len(items)} equipos detectados; inventario actualizado. No se ha pedido autorización.')
                listing()
            elif command == 'equipos':
                listing()
            elif command == 'agregar':
                if not 1 <= len(params) <= 2:
                    raise ValueError('Uso: agregar IP [samsung|roku]')
                brands = [params[1]] if len(params) == 2 else ['samsung', 'roku']
                errors = []
                for brand in brands:
                    if brand not in ('samsung', 'roku'):
                        raise ValueError('La identificación manual admite samsung o roku.')
                    try:
                        item = read_metadata(params[0], brand)
                        break
                    except Exception as exc:
                        errors.append(str(exc))
                else:
                    raise ValueError('No se pudo identificar: ' + ' | '.join(errors))
                store.upsert(item)
                listing()
            elif command == 'ver' and len(params) == 1:
                for key, value in store.get(params[0]).items():
                    print(f'{key}: {clean(value)}')
            elif command == 'editar' and len(params) >= 2:
                store.rename(params[0], ' '.join(params[1:]))
                listing()
            elif command == 'eliminar' and len(params) == 1:
                item = store.get(params[0])
                answer = input(f"Eliminar ficha {clean(item['alias'] or item['name'])} ({item['ip']})? Escribe SI: ")
                if answer == 'SI':
                    store.delete(item['id'])
                    print('Ficha eliminada. Los tokens de autorización se conservan.')
                else:
                    print('Cancelado.')
            elif command == 'control' and len(params) <= 1:
                rows = store.all()
                if params:
                    item = store.get(params[0])
                else:
                    recent = [d for d in rows if d['last_connected']]
                    item = max(recent, key=lambda d: d['last_connected']) if recent else next((d for d in rows if d['ip'] == saved_tv().get('ip')), rows[0] if len(rows) == 1 else None)
                    if item is None:
                        raise ValueError('Selecciona un equipo: control ID')
                if item['brand'] not in ('samsung', 'roku'):
                    raise ValueError('Equipo detectado, pero falta su adaptador de autorización/control.')
                from terminal import launch as remote
                remote(item['ip'], brand=item['brand'], title=item['alias'] or item['name'],
                       on_connected=lambda: store.connected(item['id']))
            else:
                print('Comando o argumentos inválidos. Escribe ayuda.')
        except (EOFError, KeyboardInterrupt):
            print('\nORBIT cerrado.')
            return
        except Exception as exc:
            print('ERROR: ' + clean(exc))
