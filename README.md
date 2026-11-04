# ORBIT · control e inventario desde terminal

Utiliza Wireshark/TShark **del sistema**, SQLite para el inventario y el adaptador Samsung con los tokens existentes. El inicio predeterminado abre el CRUD visual azul dentro de la terminal. El prompt de comandos sigue disponible con `./orbit --shell`.

## Super+N en COSMIC y sistema unificado

El lanzador `scripts/launch-terminal` abre ORBIT en COSMIC Terminal, igual que tus otras terminales. Para registrar el atajo una sola vez:

```sh
cd ~/Proyectos/experimentos_python/control-remoto
.venv/bin/python scripts/install-shortcut.py --apply
```

El instalador conserva los otros atajos, rechaza conflictos en Super+N y crea una copia de seguridad de `custom` antes de escribir. Sin `--apply` solo muestra una vista previa. Si COSMIC no recoge el cambio inmediatamente, vuelve a iniciar sesión.

Al abrir con Super+N o `./orbit`, primero aparece **Mis controles remotos**:

- N: crear una ficha con nombre, IP y marca.
- E: editar nombre, IP o marca. Cambiar IP no traslada automáticamente permisos a otro equipo.
- D: eliminar ficha con confirmación; los tokens se conservan.
- B: buscar usando el TShark instalado en tu sistema, incluyendo UDP 8001 y SSDP.
- I: importar tu captura Wireshark/pcapng.
- F: filtrar equipos por nombre, IP, modelo o marca.
- Flechas: seleccionar. Enter: entrar al mando azul.
- Q desde el mando: volver al CRUD. Q desde el CRUD: salir.

El CRUD no necesita un servidor web. Capturar requiere los permisos de Wireshark del usuario. Detectar un equipo no solicita autorización; esta se comprueba al entrar al mando. Samsung conserva sus tokens; Roku usa sus ajustes de acceso; LG no dispone aún de mando implementado.

## Inicio diario

```sh
cd ~/Proyectos/experimentos_python/control-remoto
./orbit
```

No necesitas reinstalar las dependencias ni abrir el navegador. Para entrar directamente al control Samsung guardado: `./orbit --terminal`. Para indicar otra IP Samsung: `./orbit --terminal --ip 192.168.1.16`. La web permanece disponible con `./orbit --web`.

Primera instalación, si falta el entorno:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Comandos del inventario

```text
interfaces
buscar
buscar wlan0
importar "/home/blessed/Escritorio/myred.pcapng"
equipos
agregar 192.168.1.16
ver 1
editar 1 TV sala
control 1
eliminar 1
salir
```

Si no existe inventario ni una IP autorizada guardada, ORBIT inicia una búsqueda automáticamente. Con un equipo guardado, evita esa espera. `buscar` captura durante ocho segundos con el TShark del sistema. En Linux usa `any` salvo que indiques una interfaz; `interfaces` lista las disponibles. Incluye **UDP 8001** (anuncios Samsung observados en tu captura) y **UDP 1900** (SSDP). `importar` usa el mismo motor para una grabación existente, con límite de 2000 paquetes. Los equipos detectados se guardan sin pedir autorización. Cuando es posible consulta nombre y modelo por HTTP local; si falla, conserva el candidato y muestra el motivo. Una captura antigua no demuestra presencia actual.

El inventario registra alias, IP, marca, modelo, estado de identificación, última detección y última conexión. Editar el alias no borra permisos. Eliminar exige escribir `SI` y borra solo la ficha; conserva los tokens. La selección por defecto de `control` prioriza la conexión más reciente.

La detección es pasiva: requiere anuncios que lleguen a la interfaz elegida. No garantiza encontrar todos los TVs. Algunos equipos Roku son reproductores, no televisores. Si no aparecen anuncios, usa `agregar IP` o importa una captura. TShark requiere permisos de captura configurados en tu sistema; ORBIT muestra el error y no eleva privilegios.

## Control y autorización

Samsung: se abre un canal WebSocket autorizado en 8002/8001 y se mantiene durante la sesión. Los tokens existentes de `.data/tokens/` se reutilizan. La IP y puerto correctos se guardan en `.data/tv.json`. El televisor puede revocar el permiso o pedirlo de nuevo según sus ajustes. La primera autorización requiere aceptar ORBIT Remoto en la pantalla.

Roku: identifica mediante ECP y envía teclas por su API HTTP. El control por aplicaciones debe estar habilitado en el dispositivo; no se inventa un token. LG webOS se detecta por anuncios, pero todavía no dispone de adaptador de control.

Atajos del control: flechas, Enter, H inicio, B/Esc atrás, +/− volumen, M silencio, [/] canal, espacio reproducción/pausa, R reconectar, Q salir. Los envíos fallidos no se repiten automáticamente. Al salir puede esperar a que termine una conexión en curso. Un envío correcto no acredita el estado físico de la pantalla.

Conserva `.data/`: contiene el inventario y las autorizaciones. No publiques sus tokens. Una IP reasignada por DHCP requiere revisar la ficha; las autorizaciones actuales se guardan por IP.

## Validación

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Las pruebas de autorización/control usan adaptadores simulados. El lector de captura se comprobó además con el TShark real contra `myred.pcapng`, donde detectó los dos anuncios Samsung de 192.168.1.16 y 192.168.1.20. Esto no sustituye una comprobación con el TV físico.

## Mando visual azul

Desde el inventario, `control 1` abre el mando del TV con ID 1. Usa `./orbit --terminal` para abrir directamente el Samsung guardado. Con una terminal de al menos 78 columnas y 26 filas se muestra cruceta, botones, sesión y actividad en paneles azules; en tamaños menores se activa una vista compacta. El color requiere soporte de colores de la terminal.

Los botones resaltan al enviar una acción. `T` activa/desactiva clics del ratón. Por defecto los clics están desactivados para permitir seleccionar y copiar texto normalmente. `Q` vuelve al inventario cuando se abrió desde `control`, o sale si se inició directamente.
