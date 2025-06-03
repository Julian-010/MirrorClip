# mirror_clip.py
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk # Pillow para imágenes
from pystray import Icon, Menu, MenuItem # pystray para el icono de la bandeja

# Importar rutas de config_paths.py
# ASSETS_DIR y ICON_PATH apuntarán a la carpeta de instalación (para assets de solo lectura)
# LOG_DIR y LOG_FILE_PATH apuntarán a la carpeta de datos del usuario (para logs escribibles)
# CONFIG_DIR también apuntará a la carpeta de datos del usuario
from config_paths import (
    ICON_PATH, TRUSTED_USERS_FILE, # Usados en este archivo
    LOG_DIR, LOG_FILE_PATH,         # Para la nueva configuración de logging
    CONFIG_DIR                      # Usado en main() para el lock_file_path
)

from port_editor import PortEditor, cargar_puerto
from status import EstadoVentana
import discovery
from connection import ConnectionManager
import os # Para os.startfile (Windows) y os.remove/os.getpid, os.path.join, os.getenv
import sys # Para sys.stderr y sys.exit (o os._exit)
import threading
import pyperclip # Para el portapapeles
import time
from pathlib import Path
from user_manager import GestionUsuarios
import logging # Módulo de logging
from peer_utils import get_peer_display_name
import json

# Módulos adicionales para abrir el archivo trusted_users.json
import platform # Para detectar el SO
import subprocess # Para abrir archivos en macOS/Linux

APP_NAME = "MirrorClip" # Definido globalmente para ser usado por el logger y otros
run_app = True
systray = None
ventana = None
last_clipboard_content = ""
conn_manager = None
share_menu = None
lock_file = None

_main_thread_id = None # Para identificar el hilo principal de Tkinter

# --- Configuración del Logging ---
# Esta sección reemplaza la configuración de logging anterior.
# Ahora usa LOG_DIR y LOG_FILE_PATH de config_paths.py, que apuntan a directorios de usuario.
final_log_path_for_handler = None
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True) # Asegurar que el directorio de logs exista
    # Se podría añadir una comprobación de escritura aquí si se desea,
    # pero FileHandler también fallará si no puede escribir.
    final_log_path_for_handler = LOG_FILE_PATH
    # Intento de verificar escritura (opcional, pero puede dar un aviso temprano)
    with open(final_log_path_for_handler, "a", encoding='utf-8') as f_test:
        pass
except Exception as e_log_setup:
    print(f"ADVERTENCIA: No se pudo crear/acceder al directorio/archivo de logs en {LOG_DIR} o {LOG_FILE_PATH}. Error: {e_log_setup}")
    print("Los logs podrían mostrarse solo en la consola.")

log_handlers = [logging.StreamHandler()] # Siempre loguear a la consola (stdout/stderr)
if final_log_path_for_handler:
    try:
        file_handler = logging.FileHandler(final_log_path_for_handler, encoding='utf-8')
        log_handlers.append(file_handler)
    except Exception as e_file_handler:
        print(f"ADVERTENCIA: No se pudo crear el FileHandler para el archivo de log en {final_log_path_for_handler}. Error: {e_file_handler}")
        print("Los logs para archivo podrían no funcionar. Se usará solo consola.")

logging.basicConfig(
    level=logging.INFO, # Cambiar a logging.DEBUG para más detalle si es necesario
    format='%(asctime)s - %(name)s - %(levelname)s - %(threadName)s - %(message)s', # Incluir nombre del hilo
    handlers=log_handlers
)
logger = logging.getLogger(APP_NAME) # Usar la constante global APP_NAME
# --- Fin de la Configuración del Logging ---


def inicializar_estructura():
    """Inicializa estructuras básicas como el icono por defecto si no existe."""
    # ICON_PATH y ASSETS_DIR ahora vienen de config_paths.py y apuntan
    # al directorio de instalación para assets de solo lectura.
    if not ICON_PATH.exists():
        try:
            from config_paths import ASSETS_DIR # Importar ASSETS_DIR si es necesario aquí
            ASSETS_DIR.mkdir(parents=True, exist_ok=True) # Asegurar que exista el dir de assets
            img = Image.new('RGB', (64, 64), color='blue')
            img.save(ICON_PATH)
            logger.info(f"Icono por defecto creado en: {ICON_PATH}")
        except Exception as e:
            logger.error(f"No se pudo crear el icono por defecto en {ICON_PATH}: {e}")

class ShareMenu:
    def __init__(self, master, connection_manager_instance):
        self.master = master
        self.conn_manager = connection_manager_instance
        self.menu = tk.Menu(master, tearoff=0)

    def show_menu(self, x, y, content_to_share):
        if not (self.master and hasattr(self.master, 'winfo_exists') and self.master.winfo_exists()):
            logger.warning("Intento de mostrar ShareMenu con ventana master (widget) destruida.")
            return

        self.menu.delete(0, tk.END)
        self.menu.add_command(label="Enviar a todos los confiables",
                              command=lambda: self.share_with_all_trusted(content_to_share))
        self.menu.add_separator()
        
        trusted_peer_ips = []
        if self.conn_manager:
            trusted_peer_ips = self.conn_manager.get_trusted_peers() # Esta función lee TRUSTED_USERS_FILE
        
        if trusted_peer_ips:
            for peer_ip in trusted_peer_ips:
                display_name = get_peer_display_name(peer_ip)
                label_text = f"Enviar a {display_name}"
                if display_name != peer_ip:
                    label_text += f" ({peer_ip})"
                self.menu.add_command(label=label_text,
                                      command=lambda ip=peer_ip, content=content_to_share: self.share_with_peer(ip, content))
        else:
            self.menu.add_command(label="No hay peers confiables", state="disabled")
        
        try:
            self.menu.tk_popup(x, y)
        except tk.TclError as e_tcl:
            if "application has been destroyed" in str(e_tcl).lower() or "bad window path name" in str(e_tcl).lower() :
                logger.warning(f"No se pudo mostrar el menú contextual (tk_popup) porque la aplicación Tk ha sido destruida o la ventana no es válida: {e_tcl}")
            else:
                logger.error(f"Error TclError inesperado al mostrar el menú contextual (tk_popup): {e_tcl}", exc_info=True)
        except Exception as e_generic:
            logger.error(f"Error genérico al mostrar el menú contextual: {e_generic}", exc_info=True)

    def share_with_all_trusted(self, content):
        logger.info(f"Preparando para enviar contenido a todos los peers confiables: {content[:30]}...")
        if self.conn_manager:
            self.conn_manager.send_to_trusted_peers(content)
        else:
            logger.warning("ConnectionManager no disponible para share_with_all_trusted.")

    def share_with_peer(self, peer_ip, content):
        logger.info(f"Preparando para enviar contenido a {peer_ip}: {content[:30]}...")
        if self.conn_manager:
            self.conn_manager.send_to_peer(peer_ip, content)
        else:
            logger.warning(f"ConnectionManager no disponible para share_with_peer ({peer_ip}).")

def abrir_ventana_estado():
    global ventana
    if ventana and ventana.winfo_exists():
        EstadoVentana(ventana)
    else:
        logger.warning("La ventana principal no está inicializada o ya fue destruida para abrir EstadoVentana.")

def abrir_gestion_usuarios():
    global ventana
    if ventana and ventana.winfo_exists():
        GestionUsuarios(ventana)
    else:
        logger.warning("La ventana principal no está inicializada o ya fue destruida para abrir GestionUsuarios.")

def editar_puerto():
    global ventana
    if ventana and ventana.winfo_exists():
        current_port = cargar_puerto() # cargar_puerto usa CONFIG_FILE de config_paths
        PortEditor(current_port)
    else:
        logger.warning("La ventana principal no está inicializada o ya fue destruida para abrir PortEditor.")

def abrir_archivo_trusted_users():
    filepath = TRUSTED_USERS_FILE # TRUSTED_USERS_FILE ahora apunta a la carpeta de datos del usuario
    logger.info(f"Intentando abrir el archivo: {filepath}")
    try:
        if not filepath.exists():
            logger.warning(f"El archivo {filepath} no existe. No se puede abrir.")
            # Crear el archivo con contenido por defecto si no existe, para que el usuario no vea un error al abrirlo.
            # Esta lógica también está en config.py/crear_estructura_completa, pero una doble verificación aquí es segura.
            try:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump({"users": []}, f, indent=4)
                logger.info(f"Archivo {filepath} creado con contenido por defecto.")
            except Exception as e_create:
                logger.error(f"No se pudo crear el archivo por defecto {filepath}: {e_create}")
                if ventana and ventana.winfo_exists():
                    messagebox.showerror("Error de archivo", f"No se pudo crear el archivo {filepath.name} necesario.", parent=ventana)
                return

            if ventana and ventana.winfo_exists(): # Aún mostrar advertencia si se acaba de crear
                 messagebox.showinfo("Archivo Creado", f"El archivo {filepath.name} no existía y ha sido creado.", parent=ventana)
        
        current_os = platform.system()
        if current_os == "Windows":
            os.startfile(filepath)
        elif current_os == "Darwin": # macOS
            subprocess.run(['open', str(filepath)], check=False) # Usar subprocess.run
        elif current_os == "Linux":
            subprocess.run(['xdg-open', str(filepath)], check=False) # Usar subprocess.run
        else:
            logger.warning(f"Sistema operativo '{current_os}' no soportado para abrir archivos automáticamente.")
            if ventana and ventana.winfo_exists():
                messagebox.showinfo("Función no soportada",
                                    f"No se puede abrir el archivo automáticamente en '{current_os}'.\n"
                                    f"Puedes encontrarlo en: {filepath}", parent=ventana)
    except FileNotFoundError: 
        logger.error(f"Comando para abrir archivo no encontrado en el sistema ('{current_os}').")
        if ventana and ventana.winfo_exists():
             messagebox.showerror("Error al abrir", f"No se encontró el comando necesario para abrir el archivo en tu sistema.", parent=ventana)
    except Exception as e:
        logger.error(f"Error al intentar abrir el archivo {filepath}: {e}", exc_info=True)
        if ventana and ventana.winfo_exists():
            messagebox.showerror("Error", f"No se pudo abrir el archivo {filepath.name}:\n{e}", parent=ventana)

def _perform_tk_destroy():
    global ventana
    logger.info("Función _perform_tk_destroy llamada.")
    if ventana:
        try:
            if ventana.winfo_exists():
                logger.info("Llamando a ventana.destroy() desde _perform_tk_destroy...")
                ventana.destroy()
                logger.info("Llamada a ventana.destroy() completada.")
            else:
                logger.info("Ventana Tkinter no existía cuando se intentó destruir en _perform_tk_destroy.")
        except Exception as e:
            logger.error(f"Excepción durante la destrucción de la ventana Tkinter en _perform_tk_destroy: {e}", exc_info=True)
    else:
        logger.info("No hay objeto 'ventana' global para destruir en _perform_tk_destroy.")

def salir(icon=None, item=None):
    global run_app, systray, ventana, conn_manager, _main_thread_id

    calling_thread = threading.current_thread()
    logger.info(f"Función salir() llamada por hilo: {calling_thread.name} (ID: {calling_thread.ident})")
    print(f"DEBUG: SALIR - Función salir() llamada por hilo: {calling_thread.name}", file=sys.stderr)

    if not run_app:
        logger.info("Función salir() - Salida ya en progreso o aplicación detenida.")
        print("DEBUG: SALIR - Salida ya en progreso.", file=sys.stderr)
        return

    logger.info("Función salir() - Iniciando proceso de salida...")
    print("DEBUG: SALIR - Iniciando. run_app será False.", file=sys.stderr)
    run_app = False

    if conn_manager:
        logger.info("Función salir() - Deteniendo ConnectionManager...")
        print("DEBUG: SALIR - Deteniendo ConnectionManager...", file=sys.stderr)
        conn_manager.stop()
    if discovery:
        logger.info("Función salir() - Deteniendo hilos de descubrimiento...")
        print("DEBUG: SALIR - Deteniendo hilos de descubrimiento...", file=sys.stderr)
        discovery.stop_discovery()

    if systray:
        logger.info("Función salir() - Señalando a pystray que se detenga (systray.stop())...")
        print("DEBUG: SALIR - Antes de systray.stop()", file=sys.stderr)
        systray.stop()
        logger.info("Función salir() - Llamada a systray.stop() realizada.")
        print("DEBUG: SALIR - Después de systray.stop()", file=sys.stderr)

    if ventana:
        print(f"DEBUG: SALIR - Manejando destrucción de ventana. Hilo actual ID: {calling_thread.ident}, Hilo principal Tk ID: {_main_thread_id}", file=sys.stderr)
        if _main_thread_id is None: # Fallback si _main_thread_id no se estableció
             logger.warning("Función salir() - _main_thread_id no está establecido. Asumiendo que se puede llamar a _perform_tk_destroy() directamente si la ventana existe.")
             if ventana.winfo_exists(): _perform_tk_destroy()
        elif calling_thread.ident == _main_thread_id:
            logger.info("Función salir() - Ejecutada por el hilo principal de Tkinter. Destruyendo ventana directamente.")
            print("DEBUG: SALIR - En hilo principal Tk, llamando a _perform_tk_destroy()", file=sys.stderr)
            _perform_tk_destroy()
        else:
            logger.info("Función salir() - Ejecutada por un hilo secundario. Programando destrucción de ventana para el hilo principal de Tkinter.")
            print("DEBUG: SALIR - En hilo secundario, programando _perform_tk_destroy() con after(0)", file=sys.stderr)
            if ventana.winfo_exists():
                 ventana.after(0, _perform_tk_destroy)
            else:
                 logger.info("Función salir() - Ventana Tkinter no existe, no se programa 'after'.")
                 print("DEBUG: SALIR - Ventana no existe, no se usa after(0).", file=sys.stderr)
    else:
        logger.info("Función salir() - No hay objeto 'ventana' global.")
        print("DEBUG: SALIR - No hay objeto 'ventana'.", file=sys.stderr)

    logger.info(f"Función salir() - Finalizadas tareas de señalización en hilo {calling_thread.name}.")
    print(f"DEBUG: SALIR - Fin de la función salir() en hilo {calling_thread.name}.", file=sys.stderr)

def iniciar_systray():
    global systray, APP_NAME # APP_NAME es global
    try:
        image = Image.open(ICON_PATH) # ICON_PATH viene de config_paths
    except FileNotFoundError:
        logger.error(f"Icono no encontrado en {ICON_PATH}. Usando icono por defecto.")
        image = Image.new('RGB', (64, 64), color='red')
    except Exception as e:
        logger.error(f"Error cargando imagen para systray: {e}")
        image = Image.new('RGB', (64, 64), color='red')

    menu_items = [
        MenuItem('Estado', abrir_ventana_estado, default=True),
        MenuItem('Gestionar Usuarios', abrir_gestion_usuarios),
        MenuItem('Editar Puerto', editar_puerto),
        MenuItem('Usuarios de Confianza', abrir_archivo_trusted_users),
        MenuItem('Salir', salir)
    ]
    menu = Menu(*menu_items)
    systray = Icon(APP_NAME, image, APP_NAME, menu) # Usar APP_NAME global
    logger.info("Iniciando icono en la bandeja del sistema...")
    try:
        systray.run_detached()
    except Exception as e:
        logger.error(f"No se pudo iniciar el icono de la bandeja del sistema: {e}", exc_info=True)
        if ventana and hasattr(ventana, 'winfo_exists') and ventana.winfo_exists():
             messagebox.showerror("Error de Systray", f"No se pudo iniciar el icono de la bandeja: {e}\nLa aplicación podría no ser completamente funcional.")
        else:
            print(f"ERROR CRITICO DE SYSTRAY (sin ventana Tk): No se pudo iniciar el icono de la bandeja del sistema: {e}")

def monitor_clipboard():
    global last_clipboard_content, ventana, share_menu, run_app
    
    while run_app and not (ventana and hasattr(ventana, 'winfo_exists') and ventana.winfo_exists() and share_menu):
        if not run_app: return
        time.sleep(0.2)

    if not run_app :
        logger.info("Monitor de portapapeles: run_app es False antes de iniciar el bucle principal. Saliendo.")
        return

    logger.info("Monitor de portapapeles iniciado.")
    while run_app:
        try:
            if not (ventana and ventana.winfo_exists()):
                if run_app: logger.warning("Ventana no disponible en monitor_clipboard, pausando temporalmente.")
                time.sleep(1)
                continue

            current_content = pyperclip.paste()
            if isinstance(current_content, str) and current_content != last_clipboard_content:
                logger.info(f"Contenido del portapapeles cambiado: {current_content[:50]}...")
                last_clipboard_content = current_content
                
                if share_menu and ventana and ventana.winfo_exists():
                    try:
                        x_root, y_root = ventana.winfo_pointerxy()
                        ventana.after(0, share_menu.show_menu, x_root, y_root, current_content)
                    except tk.TclError as e_winfo:
                        if "bad window path name" not in str(e_winfo).lower() and run_app:
                            logger.warning(f"Error de Tkinter al obtener info del puntero u operar con ventana (monitor_clipboard): {e_winfo}")
                    except Exception as e_after:
                         if run_app: logger.error(f"Error inesperado en ventana.after en monitor_clipboard: {e_after}", exc_info=True)
                elif run_app:
                    logger.warning("ShareMenu o ventana no disponible para mostrar menú contextual en monitor_clipboard.")

        except pyperclip.PyperclipException as e_pyperclip:
            if run_app: logger.error(f"Error al acceder al portapapeles (PyperclipException): {e_pyperclip}. El monitoreo puede no funcionar.")
            time.sleep(5)
        except tk.TclError as e_tcl_main:
            if "application has been destroyed" not in str(e_tcl_main).lower() and run_app:
                 logger.warning(f"Error de Tkinter en bucle principal de monitor_clipboard: {e_tcl_main}")
        except Exception as e_general:
            if run_app: logger.error(f"Error inesperado en monitor_clipboard: {e_general}", exc_info=True)
            time.sleep(1)
        
        for _ in range(10):
            if not run_app: break
            time.sleep(0.1)
            
    logger.info("Monitor de portapapeles detenido.")

def main():
    global ventana, conn_manager, share_menu, run_app, lock_file, _main_thread_id
    _main_thread_id = threading.current_thread().ident # Asegurar que se establece aquí
    logger.info(f"Hilo principal de la aplicación iniciado. ID: {_main_thread_id}")

    # CONFIG_DIR ahora viene de config_paths.py y apunta a la carpeta de datos del usuario
    safe_app_name = APP_NAME.lower().replace(' ', '_')
    lock_file_path = CONFIG_DIR / f".{safe_app_name}.lock" # Usar CONFIG_DIR para el lock file

    try:
        # La creación de CONFIG_DIR ahora la hace config.py -> crear_estructura_completa
        # Pero para el lock file, necesitamos asegurarnos de que exista antes.
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        if lock_file_path.exists():
            logger.warning(f"Archivo lock ya existe en: {lock_file_path}. {APP_NAME} podría estar ya ejecutándose.")
            print(f"ADVERTENCIA: {APP_NAME} parece estar ya ejecutándose (lock file: {lock_file_path}).")
            sys.exit(1)

        lock_file = open(lock_file_path, 'w')
        lock_file.write(str(os.getpid()))
        lock_file.flush()
    except IOError as e_lock:
        logger.error(f"No se pudo crear o escribir en el archivo lock: {lock_file_path}. Error: {e_lock}", exc_info=True)
        print(f"ERROR: No se pudo gestionar el archivo lock: {e_lock}. Verifique permisos o elimine {lock_file_path} manualmente.")
        sys.exit(1)
    except Exception as e_lock_general:
        logger.error(f"Error inesperado con el archivo lock: {lock_file_path}. Error: {e_lock_general}", exc_info=True)
        print(f"ERROR: Inesperado con archivo lock: {e_lock_general}.")
        sys.exit(1)

    logger.info(f"Iniciando {APP_NAME}...")
    # inicializar_estructura() crea el icono por defecto si es necesario.
    # La creación de directorios de config/keys/logs ahora se espera que la maneje config.py/crear_estructura_completa
    # y la configuración de logging para el directorio de logs.
    inicializar_estructura() 

    # Importar config solo después de que el logging básico y el lock file estén configurados,
    # y después de que config_paths.py haya establecido las rutas.
    # Esto es para que config.py pueda usar las rutas correctas y su propio logging no interfiera.
    try:
        import config # Importar aquí para que use el logger ya configurado y las rutas de config_paths
        # config.py llama a crear_estructura_completa() en su importación,
        # lo que creará CONFIG_DIR, KEYS_DIR, LOG_DIR y los JSONs si no existen.
    except Exception as e_import_config:
        logger.critical(f"Error crítico al importar o inicializar el módulo de configuración: {e_import_config}", exc_info=True)
        # Limpieza del lock file
        if lock_file: lock_file.close(); os.remove(lock_file_path)
        sys.exit(1)


    ventana = tk.Tk()
    ventana.title(APP_NAME)
    ventana.withdraw()

    try:
        conn_manager = ConnectionManager() # Usa el puerto de config.py, que ya se cargó
        logger.info("ConnectionManager inicializado globalmente.")
        share_menu = ShareMenu(ventana, conn_manager)
        logger.info("ShareMenu inicializado.")
    except Exception as e_init_conn:
        logger.critical(f"Error crítico inicializando ConnectionManager o ShareMenu: {e_init_conn}", exc_info=True)
        print(f"ERROR CRITICO: No se pudo inicializar componentes de red: {e_init_conn}")
        if lock_file: lock_file.close(); os.remove(lock_file_path) # No olvidar remover lock_file_path
        sys.exit(1)

    try:
        threading.Thread(target=conn_manager.listen_for_peers, daemon=True, name="ConnMgrListener").start()
        logger.info("Hilo listen_for_peers (ConnectionManager) iniciado.")
        threading.Thread(target=discovery.start_discovery, daemon=True, name="DiscoveryStarter").start()
        logger.info("Hilo start_discovery (que inicia los hilos de descubrimiento) iniciado.")
        threading.Thread(target=monitor_clipboard, daemon=True, name="ClipboardMonitor").start()
        logger.info("Hilo monitor_clipboard iniciado.")
    except Exception as e_threads:
        logger.critical(f"Error crítico al iniciar hilos principales: {e_threads}", exc_info=True)
        print(f"ERROR CRITICO: No se pudieron iniciar los servicios de red o portapapeles: {e_threads}")
        if lock_file: lock_file.close(); os.remove(lock_file_path) # No olvidar remover lock_file_path
        sys.exit(1)

    ventana.protocol("WM_DELETE_WINDOW", salir)
    iniciar_systray()
    
    logger.info(f"{APP_NAME} está corriendo. Ventana principal (oculta) iniciada. Entrando en Tkinter mainloop.")
    
    try:
        ventana.mainloop()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt recibido. Saliendo...")
        if run_app:
            salir()
    finally:
        logger.info(f"{APP_NAME} ha salido de Tkinter mainloop (o KeyboardInterrupt).")
        if run_app:
            logger.warning("run_app seguía True después de mainloop/KeyboardInterrupt. Forzando ejecución de 'salir' para limpieza.")
            if 'salir' in globals() and callable(salir):
                 print("DEBUG: MAIN FINALLY - run_app True, llamando a salir()", file=sys.stderr)
                 salir()
        
        if lock_file:
            try:
                lock_file.close()
                logger.info(f"Archivo lock {lock_file_path} cerrado.")
                if lock_file_path.exists():
                    os.remove(lock_file_path)
                    logger.info(f"Archivo lock {lock_file_path} eliminado.")
            except OSError as e_remove_lock:
                logger.error(f"No se pudo eliminar el archivo lock {lock_file_path}: {e_remove_lock}")
            except Exception as e_lock_close:
                logger.error(f"Error al cerrar/eliminar archivo lock {lock_file_path}: {e_lock_close}")
        else:
            if lock_file_path.exists(): # lock_file_path es una Path object
                 logger.info(f"Intentando eliminar archivo lock existente en {lock_file_path} al salir (lock_file no definido).")
                 try:
                     os.remove(lock_file_path)
                     logger.info(f"Archivo lock existente {lock_file_path} eliminado.")
                 except OSError as e_remove_existing_lock:
                     logger.error(f"No se pudo eliminar el archivo lock existente {lock_file_path}: {e_remove_existing_lock}")
        
        logger.info("Comprobando hilos activos antes de finalizar el programa...")
        time.sleep(1.0)

        active_threads = threading.enumerate()
        non_daemon_threads_alive = [
            t for t in active_threads if
            not t.daemon and t.is_alive() and t.ident != _main_thread_id
        ]

        if non_daemon_threads_alive:
            thread_details = []
            for t in non_daemon_threads_alive:
                detail = f"Nombre: {t.name}, ID: {t.ident}, Es Daemon: {t.daemon}, Está Vivo: {t.is_alive()}"
                thread_details.append(detail)
            logger.warning(f"Hilos NO-DAEMON (aparte del principal) aún activos: {thread_details}")
            logger.critical("Uno o más hilos no-daemon están impidiendo el cierre limpio de la aplicación.")
            logger.critical("Aplicando salida forzada del proceso (os._exit(1)) para asegurar el cierre.")
            print("ERROR: Cierre forzado debido a hilos no-daemon activos.", file=sys.stderr)
            os._exit(1)
        else:
            logger.info("No hay otros hilos no-daemon activos (aparte del principal que está terminando). El programa debería cerrarse limpiamente.")

if __name__ == "__main__":
    main()