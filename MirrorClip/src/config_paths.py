# config_paths.py
from pathlib import Path
import sys
import os
import platform # Necesario para un fallback más robusto

APP_NAME = "MirrorClip" # Nombre de tu aplicación, para crear subdirectorios

# --- Rutas para ASSETS (recursos de solo lectura empaquetados con la aplicación) ---
if getattr(sys, 'frozen', False):
    # Estamos ejecutando como un ejecutable congelado (PyInstaller)
    # sys.executable es la ruta al .exe
    # Los assets estarán en un subdirectorio 'assets' junto al .exe
    INSTALL_BASE_DIR = Path(sys.executable).parent
else:
    # Estamos ejecutando como un script .py
    # Asume que config_paths.py está en src/ y los directorios están en el padre de src/
    INSTALL_BASE_DIR = Path(__file__).resolve().parent.parent

ASSETS_DIR = INSTALL_BASE_DIR / "assets"
ICON_PATH = ASSETS_DIR / "systray_icon.ico" # Usado por mirror_clip.py para el systray

# --- Rutas para DATOS DEL USUARIO (configuración, logs, claves - escribibles) ---
# Estos irán a directorios específicos del usuario para evitar problemas de permisos.

user_data_path_base = None
system = platform.system()

if system == "Windows":
    user_data_path_base = os.getenv('APPDATA') # Ej: C:\Users\TuUsuario\AppData\Roaming
    if user_data_path_base is None: # Muy improbable en Windows, pero por si acaso
        user_data_path_base = Path.home() / ".config" # Fallback
elif system == "Darwin": # macOS
    user_data_path_base = Path.home() / "Library" / "Application Support"
elif system == "Linux":
    user_data_path_base = os.getenv('XDG_CONFIG_HOME') # Estándar de XDG
    if user_data_path_base is None or not Path(user_data_path_base).is_dir():
        user_data_path_base = Path.home() / ".config" # Fallback común en Linux
else: # Otros sistemas operativos
    user_data_path_base = Path.home() # Fallback genérico

# Directorio raíz para todos los datos de usuario de MirrorClip
USER_DATA_ROOT_DIR = Path(user_data_path_base) / APP_NAME

# Subdirectorios dentro de USER_DATA_ROOT_DIR
CONFIG_DIR = USER_DATA_ROOT_DIR / "config"
KEYS_DIR = USER_DATA_ROOT_DIR / "keys" # Si se usan para claves generadas/modificables
LOG_DIR = USER_DATA_ROOT_DIR / "logs"

# Archivos específicos de configuración y datos
CONFIG_FILE = CONFIG_DIR / "mirror_clip.conf"
TRUSTED_USERS_FILE = CONFIG_DIR / "trusted_users.json"
BANNED_USERS_FILE = CONFIG_DIR / "banned_users.json"
KNOWN_PEER_DETAILS_FILE = CONFIG_DIR / "known_peer_details.json"
LOG_FILE_PATH = LOG_DIR / "mirrorclip.log" # Ruta explícita para el archivo de log

# Nota: Las funciones que crean estos directorios (ej. en config.py y mirror_clip.py para logs)
# necesitarán usar estas nuevas rutas y asegurarse de que los directorios existan
# (ej. CONFIG_DIR.mkdir(parents=True, exist_ok=True)).