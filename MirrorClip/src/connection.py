# connection.py
import socket
import threading
import json
import time
from port_editor import cargar_puerto
from config import USERNAME # PORT se carga dinámicamente, USERNAME puede venir de config
import pyperclip
from config_paths import TRUSTED_USERS_FILE
import logging

# Obtener el logger. Se asume que logging.basicConfig() ya fue llamado en el script principal (mirror_clip.py)
logger = logging.getLogger(__name__) # Usar __name__ para que el logger tenga el nombre del módulo

class ConnectionManager:
    def __init__(self):
        self.PORT = cargar_puerto()
        self.last_clipboard_content = "" # Aunque no se usa aquí, se mantiene por si se expande
        self.connections = {}  # {ip: socket}
        self.listener = None
        self.running = True
        self.lock = threading.Lock() # Para proteger el acceso a self.connections si es necesario
        logger.info(f"Inicializando ConnectionManager en puerto {self.PORT}")

    def handle_connection(self, conn, addr):
        """Maneja una conexión entrante."""
        ip = addr[0]
        logger.info(f"Conexión entrante aceptada de {ip}")
        
        try:
            while self.running:
                data = conn.recv(65536)  # Buffer grande para contenido grande
                if not data:
                    logger.info(f"Conexión cerrada por {ip}")
                    break
                    
                # Ignorar mensajes de keep-alive si se implementan
                # if data == b"PING":
                #     conn.sendall(b"PONG") # Ejemplo de respuesta a keep-alive
                #     continue
                    
                content = data.decode()
                logger.info(f"Recibidos {len(data)} bytes de {ip}")
                
                # Actualizar el portapapeles si el contenido es diferente
                # Esta lógica podría ser más compleja (ej. evitar auto-actualización)
                if pyperclip.paste() != content:
                    pyperclip.copy(content)
                    logger.info(f"Portapapeles actualizado desde {ip}: {content[:50]}...")
                    
        except ConnectionResetError:
            logger.warning(f"Conexión reseteada por {ip}")
        except Exception as e:
            logger.error(f"Error en la conexión con {ip}: {e}", exc_info=True)
        finally:
            if ip in self.connections:
                with self.lock:
                    del self.connections[ip]
            conn.close()
            logger.info(f"Conexión con {ip} cerrada y eliminada.")

    def listen_for_peers(self):
        """Escucha conexiones TCP entrantes de otros peers."""
        try:
            self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.listener.bind(("0.0.0.0", self.PORT))
            self.listener.listen(5) # Aceptar hasta 5 conexiones en cola
            logger.info(f"Escuchando conexiones TCP en 0.0.0.0:{self.PORT}")

            while self.running:
                try:
                    conn, addr = self.listener.accept()
                    # Iniciar un nuevo hilo para manejar esta conexión
                    # Esto evita que el bucle de escucha se bloquee
                    thread = threading.Thread(target=self.handle_connection, args=(conn, addr), daemon=True)
                    thread.start()
                except OSError as e: # Puede ocurrir si el socket se cierra mientras se espera en accept()
                    if self.running: # Solo loguear el error si no estamos deteniendo el servicio
                        logger.error(f"Error en listener.accept(): {e}", exc_info=True)
                    break # Salir del bucle si el listener tiene problemas
                except Exception as e:
                    if self.running:
                         logger.error(f"Error inesperado al aceptar conexión: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Error crítico al iniciar el listener TCP: {e}", exc_info=True)
        finally:
            if self.listener:
                self.listener.close()
            logger.info("Listener TCP detenido.")

    def connect_to_peer(self, ip):
        """Establece una conexión TCP saliente con un peer."""
        if ip in self.connections:
            logger.info(f"Ya existe una conexión con {ip}, reutilizando.")
            return self.connections[ip]
        
        try:
            logger.info(f"Intentando conectar a {ip}:{self.PORT}")
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.settimeout(5) # Timeout de 5 segundos para la conexión
            conn.connect((ip, self.PORT))
            logger.info(f"Conexión establecida con {ip}")
            with self.lock:
                self.connections[ip] = conn
            
            # Podrías querer iniciar un hilo para manejar esta conexión saliente también,
            # si esperas recibir datos de vuelta de forma asíncrona por esta misma conexión.
            # Por ahora, se asume que es principalmente para enviar.
            return conn
        except socket.timeout:
            logger.error(f"Timeout conectando a {ip}:{self.PORT}")
        except Exception as e:
            logger.error(f"Error conectando a {ip}:{self.PORT}: {e}", exc_info=False) # exc_info=False para no ser tan verboso en fallos de conexión comunes
        return None

    def send_to_peer(self, ip, content):
        """Envía contenido a un peer específico."""
        conn = self.connections.get(ip)
        if not conn:
            conn = self.connect_to_peer(ip)

        if conn:
            try:
                conn.sendall(content.encode())
                logger.info(f"Contenido enviado a {ip}")
            except socket.error as e: # Captura errores específicos de socket
                logger.error(f"Error de socket enviando a {ip}: {e}. Intentando reconectar.")
                with self.lock:
                    if ip in self.connections: # Eliminar conexión rota
                        del self.connections[ip]
                # Reintento de conexión y envío una vez
                conn_new = self.connect_to_peer(ip)
                if conn_new:
                    try:
                        conn_new.sendall(content.encode())
                        logger.info(f"Contenido reenviado a {ip} después de reconexión.")
                    except Exception as e_retry:
                        logger.error(f"Error enviando a {ip} después de reconexión: {e_retry}")
                else:
                    logger.error(f"No se pudo reconectar con {ip} para enviar.")
            except Exception as e:
                logger.error(f"Error general enviando a {ip}: {e}", exc_info=True)
        else:
            logger.warning(f"No se pudo conectar a {ip} para enviar contenido.")

    def send_to_trusted_peers(self, content):
        """Envía contenido a todos los peers en la lista de confiables."""
        trusted_peers = self.get_trusted_peers()
        if not trusted_peers:
            logger.info("No hay peers confiables a los que enviar.")
            return

        logger.info(f"Enviando contenido a peers confiables: {trusted_peers}")
        for peer_ip in trusted_peers:
            # Aquí podrías añadir una lógica para no enviarte a ti mismo si tu IP local está en la lista,
            # aunque generalmente el descubrimiento y la lista de peers no deberían incluir la IP local.
            self.send_to_peer(peer_ip, content)

    def get_trusted_peers(self):
        """Carga la lista de IPs de peers confiables desde el archivo JSON."""
        try:
            with open(TRUSTED_USERS_FILE, 'r') as f:
                data = json.load(f)
                peers = data.get("users", [])
                logger.info(f"Peers confiables cargados: {peers}")
                return peers
        except FileNotFoundError:
            logger.warning(f"Archivo de peers confiables no encontrado en {TRUSTED_USERS_FILE}. Creando uno vacío.")
            try:
                with open(TRUSTED_USERS_FILE, 'w') as f:
                    json.dump({"users": []}, f, indent=4)
                return []
            except Exception as e_create:
                logger.error(f"No se pudo crear el archivo de peers confiables: {e_create}", exc_info=True)
                return []
        except Exception as e:
            logger.error(f"Error cargando peers confiables: {e}", exc_info=True)
            return []

    def stop(self):
        """Detiene el ConnectionManager y cierra todas las conexiones y listeners."""
        logger.info("Deteniendo ConnectionManager...")
        self.running = False
        
        # Cerrar el socket listener principal
        if self.listener:
            try:
                self.listener.close() # Esto debería hacer que listener.accept() falle y el hilo termine
                logger.info("Socket listener cerrado.")
            except Exception as e:
                logger.error(f"Error cerrando el socket listener: {e}", exc_info=True)
        
        # Cerrar todas las conexiones activas
        with self.lock:
            ips_to_close = list(self.connections.keys()) # Copiar claves para evitar problemas al modificar el dict durante la iteración
            for ip in ips_to_close:
                conn = self.connections.pop(ip, None) # Eliminar y obtener la conexión
                if conn:
                    try:
                        conn.shutdown(socket.SHUT_RDWR) # Indicar que no se enviarán/recibirán más datos
                        conn.close()
                        logger.info(f"Conexión con {ip} cerrada.")
                    except Exception as e:
                        logger.error(f"Error cerrando conexión con {ip}: {e}", exc_info=True)
        logger.info("Todas las conexiones activas han sido cerradas.")
