#!/usr/bin/env python3
"""Install the requested COSMIC Super+N shortcut with backup and conflict checks."""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import tempfile


def updated_config(text, command):
    if not text.strip().startswith('{') or not text.strip().endswith('}'):
        raise ValueError('Formato de atajos COSMIC desconocido; no se ha modificado.')
    pattern = r'\(\s*modifiers:\s*\[\s*Super\s*,?\s*\]\s*,\s*key:\s*"[nN]".*?\)\s*:\s*Spawn\(("(?:[^"\\]|\\.)*")\)'
    match = re.search(pattern, text, re.S)
    if match:
        if json.loads(match.group(1)) == command:
            return text
        raise ValueError('Super+N ya está asignado. No se ha reemplazado su acción.')
    # Refuse other actions on the same chord as well.
    if re.search(r'modifiers:\s*\[\s*Super\s*,?\s*\]\s*,\s*key:\s*"[nN]"', text, re.S):
        raise ValueError('Super+N ya figura en la configuración; revisa el conflicto.')
    end = text.rfind('}')
    prefix = text[:end].rstrip()
    if prefix.endswith(')'):
        prefix += ','
    return prefix + '\n    (\n        modifiers: [Super],\n        key: "n",\n        description: Some("ORBIT · Controles TV"),\n    ): Spawn(' + json.dumps(command, ensure_ascii=False) + '),\n}\n'


def main():
    parser = argparse.ArgumentParser(description='Configurar Super+N para ORBIT en COSMIC.')
    parser.add_argument('--apply', action='store_true', help='Escribir el atajo tras crear copia de seguridad.')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    launcher = root / 'scripts' / 'launch-terminal'
    command = shlex.join([str(launcher)])
    config_root = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    target = config_root / 'cosmic/com.system76.CosmicSettings.Shortcuts/v1/custom'
    text = target.read_text() if target.exists() else '{}\n'
    result = updated_config(text, command)
    print('Atajo: Super+N → ' + command)
    print('Archivo: ' + str(target))
    if text == result:
        print('El atajo ya está instalado.')
        return
    if not args.apply:
        print('Vista previa; ejecuta con --apply para instalar.')
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        backup = target.with_name('custom.orbit-backup-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        shutil.copy2(target, backup)
        print('Copia de seguridad: ' + str(backup))
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=target.parent, delete=False) as stream:
            temporary = stream.name
            stream.write(result)
        os.replace(temporary, target)
    finally:
        if temporary and Path(temporary).exists():
            Path(temporary).unlink()
    print('Atajo guardado. Prueba Super+N; si COSMIC no lo recoge, cierra sesión y vuelve a entrar.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as exc:
        raise SystemExit('No se instaló el atajo: ' + str(exc))
