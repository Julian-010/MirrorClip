# MirrorClip 📋✨

**MirrorClip** es una aplicación de escritorio diseñada para compartir de forma sencilla el contenido de tu portapapeles (actualmente texto) entre múltiples dispositivos conectados a la misma red local. Se ejecuta discretamente en la bandeja del sistema, facilitando un flujo de trabajo más rápido y eficiente entre tus ordenadores.

## Características Principales

* **Compartir Portapapeles**: Sincroniza el contenido de texto de tu portapapeles entre dispositivos conectados.
* **Descubrimiento Automático de Peers**: Encuentra automáticamente otros dispositivos con MirrorClip en tu red local mediante transmisiones UDP.
* **Gestión de Confianza**: Decide en qué dispositivos confiar para recibir y enviar contenido del portapapeles.
    * **Usuarios Confiables**: Lista de IPs de dispositivos autorizados.
    * **Usuarios Bloqueados**: Lista de IPs de dispositivos de los que se ignorará el contenido.
* **Integración con la Bandeja del Sistema**: Accede a todas las funciones a través de un icono en la bandeja del sistema para una mínima intrusión.
* **Puerto Configurable**: Permite al usuario cambiar el puerto TCP utilizado para las conexiones de datos.
* **Ventana de Estado**: Visualiza información de tu dispositivo y una lista de otros peers MirrorClip detectados en la red, con opción de confiar o bloquear directamente.
* **Gestión de Usuarios Simplificada**: Interfaz para administrar las listas de usuarios confiables y bloqueados.
* **Configuración Persistente**: Guarda tus preferencias y listas de usuarios en archivos de configuración locales.

## Tecnologías Utilizadas

* **Python 3**: Lenguaje principal de la aplicación.
* **Tkinter**: Para las interfaces gráficas de usuario (editor de puerto, ventana de estado, gestión de usuarios).
* **Pystray**: Para la creación y gestión del icono en la bandeja del sistema.
* **Pyperclip**: Para el acceso multiplataforma al portapapeles del sistema.
* **Netifaces**: Para obtener información de las interfaces de red y determinar las direcciones de broadcast de forma más fiable.

## Instalación

### Windows
Puedes descargar el instalador `.exe` desde la sección de [Releases](https://github.com/Julian-010/MirrorClip/releases) de este repositorio (si has creado uno). El instalador te guiará a través del proceso y te permitirá:
* Crear accesos directos.
* Configurar MirrorClip para que se inicie automáticamente con Windows.

### Desde el Código Fuente (para desarrollo o uso en otras plataformas como Linux)

1.  **Prerrequisitos**:
    * Python 3.7 o superior.
    * `pip` (el instalador de paquetes de Python).
    * En Linux, para `pyperclip`, necesitarás `xclip` o `xsel`: `sudo apt install xclip` (o `xsel`).
    * En Linux, para `tkinter`, necesitarás `python3-tk`: `sudo apt install python3-tk`.
    * En Linux, para `Pillow`, necesitarás `python3-pil` y `python3-pil.imagetk`: `sudo apt install python3-pil python3-pil.imagetk`.
    * En Linux, para compilar `netifaces` si no hay un wheel disponible, podrías necesitar `python3-dev` y `build-essential`: `sudo apt install python3-dev build-essential`.

2.  **Clonar el Repositorio**:
    ```bash
    git clone https://github.com/Julian-010/MirrorClip.git
    cd MirrorClip
    ```

3.  **Crear un Entorno Virtual (Recomendado)**:
    ```bash
    python -m venv .venv
    # Activar en Windows
    .\.venv\Scripts\activate
    # Activar en Linux/macOS
    source .venv/bin/activate
    ```

4.  **Instalar Dependencias**:
    Asegúrate de tener un archivo `requirements.txt` con el siguiente contenido:
    ```txt
    Pillow>=9.0.0
    pystray>=0.19.0
    pyperclip>=1.8.0
    netifaces>=0.11.0
    ```
    Luego instala las dependencias:
    ```bash
    pip install -r requirements.txt
    ```

5.  **Ejecutar la Aplicación**:
    ```bash
    python src/mirror_clip.py
    ```

## Configuración

MirrorClip guarda sus archivos de configuración y datos en un directorio específico del usuario para evitar problemas de permisos y mantener los datos del usuario separados de la instalación de la aplicación.

* **En Windows**: Los archivos se guardan típicamente en `C:\Users\TuUsuario\AppData\Roaming\MirrorClip\config\`.
* **En Linux**: Los archivos se guardan típicamente en `~/.config/MirrorClip/config/`.

Los archivos principales son:
* `mirror_clip.conf`: Configuración general de la aplicación (nombre de usuario, puerto, etc.).
* `trusted_users.json`: Lista de direcciones IP de los dispositivos confiables.
* `banned_users.json`: Lista de direcciones IP de los dispositivos bloqueados.
* `known_peer_details.json`: Información recordada sobre otros peers (nombre de usuario, hostname).
* `mirrorclip.log`: Archivo de registro de la aplicación (ubicado en `.../MirrorClip/logs/`).

Puedes editar estos archivos manualmente si es necesario, pero la mayoría de las configuraciones relevantes se pueden gestionar a través de la interfaz de la aplicación.

## Uso

1.  Inicia MirrorClip. El icono aparecerá en la bandeja del sistema.
2.  Haz clic derecho en el icono para acceder al menú:
    * **Estado**: Muestra información local y peers descubiertos.
    * **Gestionar Usuarios**: Abre la ventana para editar las listas de usuarios confiables y bloqueados.
    * **Editar Puerto**: Cambia el puerto TCP para las conexiones.
    * **Abrir trusted_users.json**: Abre directamente el archivo de usuarios confiables con tu editor de texto predeterminado.
    * **Salir**: Cierra la aplicación.
3.  Cuando copies texto en tu portapapeles, aparecerá un menú contextual cerca de tu cursor (esta es una característica que podría evolucionar) permitiéndote enviarlo a peers específicos o a todos los confiables.
4.  El contenido de texto recibido de peers confiables actualizará automáticamente tu portapapeles.

## Desarrollo

### Empaquetado con PyInstaller (para crear el .exe en Windows)
Desde la raíz del proyecto, puedes usar un comando similar a este (asegúrate de tener PyInstaller instalado `pip install pyinstaller`):
```bash
pyinstaller --onefile --noconsole --icon=assets\systray_icon.ico src\mirror_clip.py
