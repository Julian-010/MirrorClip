# discovery.py
import socket
import threading
import time
import json
# El import de subprocess, re, platform ya no son necesarios para obtener_broadcast
# import subprocess
# import re
# import platform
import netifaces # Importar la nueva biblioteca

from config import PORT, USERNAME, BROADCAST_INTERVAL
# from config_paths import TRUSTED_USERS_FILE, BANNED_USERS_FILE # No se usan directamente aquí
import logging

logger = logging.getLogger(__name__)

_discovery_active = True
_listener_socket = None


def obtener_broadcast_con_netifaces():
    """
    Obtiene la dirección de broadcast de la red utilizando la biblioteca netifaces.
    Intenta priorizar la interfaz de la puerta de enlace predeterminada.
    """
    try:
        # 1. Intentar con la interfaz de la puerta de enlace predeterminada (IPv4)
        default_gateway_info = netifaces.gateways().get('default', {}).get(netifaces.AF_INET)
        if default_gateway_info:
            default_iface_name = default_gateway_info[1]
            if default_iface_name in netifaces.interfaces(): # Comprobar si la interfaz existe
                addrs = netifaces.ifaddresses(default_iface_name)
                if netifaces.AF_INET in addrs:
                    for addr_info in addrs[netifaces.AF_INET]:
                        if 'broadcast' in addr_info and 'addr' in addr_info:
                            # Asegurarse de que no sea una IP de loopback
                            if not addr_info.get('addr', '').startswith('127.'):
                                broadcast_ip = addr_info['broadcast']
                                logger.info(f"[DISCOVERY] Usando dirección de broadcast de la interfaz de gateway por defecto '{default_iface_name}': {broadcast_ip}")
                                return broadcast_ip
        
        logger.info("[DISCOVERY] No se encontró broadcast en la interfaz de gateway por defecto o no hay gateway IPv4. Escaneando otras interfaces...")
        # 2. Si no se encontró con la puerta de enlace, iterar todas las interfaces
        for iface_name in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface_name)
            if netifaces.AF_INET in addrs:
                for addr_info in addrs[netifaces.AF_INET]:
                    if 'broadcast' in addr_info and 'addr' in addr_info:
                        ip_addr = addr_info['addr']
                        # Evitar direcciones de loopback (127.x.x.x) y link-local (169.254.x.x)
                        if not ip_addr.startswith('127.') and not ip_addr.startswith('169.254.'):
                            broadcast_ip = addr_info['broadcast']
                            # Podría haber múltiples, devolvemos la primera válida no prioritaria encontrada
                            logger.info(f"[DISCOVERY] Usando dirección de broadcast de la interfaz '{iface_name}': {broadcast_ip} (IP local: {ip_addr})")
                            return broadcast_ip
                            
    except ImportError:
        logger.error("[DISCOVERY] La biblioteca 'netifaces' no está instalada. No se puede determinar la dirección de broadcast dinámicamente de forma avanzada.")
        logger.error("[DISCOVERY] Por favor, instala 'netifaces' ejecutando: pip install netifaces")
    except Exception as e:
        logger.error(f"[DISCOVERY] Error utilizando 'netifaces' para obtener la dirección de broadcast: {e}", exc_info=True)

    # 3. Fallback final si todo lo demás falla
    logger.warning("[DISCOVERY] No se pudo determinar la dirección de broadcast específica usando netifaces. Usando dirección de broadcast global: 255.255.255.255.")
    return "255.255.255.255"

# Reasignar la función global
obtener_broadcast = obtener_broadcast_con_netifaces


def cargar_lista(archivo):
    try:
        with open(archivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        if "users.json" in str(archivo).lower():
            return {"users": []}
        return []


def listen_for_discovery():
    global _discovery_active, _listener_socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    _listener_socket = s
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        s.bind(("", PORT))
        s.settimeout(1.0)
        logger.info(f"[DISCOVERY] Escuchando solicitudes de descubrimiento en el puerto UDP {PORT}...")
    except socket.error as e_bind:
        logger.error(f"[DISCOVERY] Error al hacer bind en el puerto {PORT}: {e_bind}. El hilo de escucha no puede iniciar.")
        _discovery_active = False
        if s: s.close()
        _listener_socket = None
        return

    while _discovery_active:
        try:
            data, addr = s.recvfrom(1024)
            ip_addr = addr[0]
            source_port = addr[1]

            if data == b"MirrorClip-Discovery":
                logger.info(f"[DISCOVERY] Solicitud de descubrimiento recibida de {ip_addr}:{source_port}")
                
                try:
                    my_hostname = socket.gethostname()
                    announced_ip = "127.0.0.1"
                    try:
                        # Intenta obtener la IP local "principal" para anunciar
                        # Esto puede ser mejorado aún más si es necesario, por ejemplo, usando netifaces para encontrar la IP de la interfaz
                        # que probablemente se usará para la comunicación con addr[0]
                        temp_sock_ip = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        temp_sock_ip.connect(("8.8.8.8", 80)) # Conexión de prueba
                        announced_ip = temp_sock_ip.getsockname()[0]
                        temp_sock_ip.close()
                    except socket.error:
                        logger.warning("[DISCOVERY] No se pudo obtener la IP preferida para el mensaje HELLO, usando 127.0.0.1.")

                    response_message = f"HELLO:{USERNAME}:{my_hostname}:{announced_ip}"
                    s.sendto(response_message.encode('utf-8'), addr)
                    logger.info(f"[DISCOVERY] Respuesta HELLO enviada a {ip_addr}:{source_port}")

                except socket.error as e_send_response:
                    logger.error(f"[DISCOVERY] Error de socket al enviar respuesta HELLO a {ip_addr}:{source_port}: {e_send_response}")
                except Exception as e_response_prepare:
                    logger.error(f"[DISCOVERY] Error preparando/enviando respuesta HELLO: {e_response_prepare}", exc_info=True)

        except socket.timeout:
            continue
        except socket.error as e_sock_recv:
            if not _discovery_active and (isinstance(e_sock_recv, socket.error) or (hasattr(e_sock_recv, 'errno') and e_sock_recv.errno == 9)):
                 logger.info(f"[DISCOVERY] Error de socket en recvfrom (esperado durante el cierre): {e_sock_recv}")
            else:
                logger.error(f"[DISCOVERY] Error de socket en la escucha de descubrimiento: {e_sock_recv}")
            if _discovery_active and not isinstance(e_sock_recv, socket.timeout):
                _discovery_active = False
                logger.error("[DISCOVERY] Deteniendo el hilo de escucha debido a un error de socket.")
        except Exception as e_recv_general:
            logger.error(f"[DISCOVERY] Error inesperado en la escucha de descubrimiento: {e_recv_general}", exc_info=True)
            if _discovery_active:
                time.sleep(1)
    
    if s:
        try:
            s.close()
            logger.info("[DISCOVERY] Socket de escucha de descubrimiento cerrado.")
        except socket.error as e_close_final:
            logger.warning(f"[DISCOVERY] Error al cerrar el socket de escucha (posiblemente ya cerrado): {e_close_final}")
    
    _listener_socket = None
    logger.info("[DISCOVERY] Hilo listen_for_discovery terminado.")


def broadcast_discovery():
    global _discovery_active
    logger.info("[DISCOVERY] Iniciando hilo de transmisión de descubrimiento...")
    
    # Espera inicial aleatoria para evitar "tormentas" de broadcast si varias instancias se inician al mismo tiempo
    time.sleep(time.time() % 2.0 + 0.5) # Entre 0.5 y 2.5 segundos

    while _discovery_active:
        try:
            broadcast_ip_addr = obtener_broadcast() # Ahora usa la versión con netifaces
            logger.info(f"[DISCOVERY] Usando dirección de broadcast: {broadcast_ip_addr} en puerto {PORT}")

            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s_broadcast:
                s_broadcast.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                # Para SO_REUSEADDR en UDP broadcast sender, puede ser útil en algunos sistemas para evitar "Address already in use"
                # si otro socket está usando la misma tupla (IP local efímera, puerto 0) pero es menos común ser un problema aquí.
                # s_broadcast.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Opcional

                discovery_message = b"MirrorClip-Discovery"
                s_broadcast.sendto(discovery_message, (broadcast_ip_addr, PORT))
                logger.info(f"[DISCOVERY] Mensaje 'MirrorClip-Discovery' enviado a {broadcast_ip_addr}:{PORT}")

            # Esperar el intervalo configurado antes de la siguiente transmisión
            for _ in range(int(BROADCAST_INTERVAL)):
                if not _discovery_active:
                    break
                time.sleep(1)
            
            if not _discovery_active:
                break
        
        except socket.gaierror as e_gaierror:
            logger.error(f"[DISCOVERY] Error de dirección (getaddrinfo) en broadcast: {e_gaierror}. ¿Problemas de red/DNS?")
            if _discovery_active: time.sleep(min(BROADCAST_INTERVAL, 30))
        except socket.error as e_sock_bcast:
            logger.error(f"[DISCOVERY] Error de socket en broadcast: {e_sock_bcast} (IP broadcast usada: {broadcast_ip_addr if 'broadcast_ip_addr' in locals() else 'Desconocida'})")
            if _discovery_active: time.sleep(min(BROADCAST_INTERVAL, 30))
        except Exception as e_bcast_general:
            logger.error(f"[DISCOVERY] Error inesperado en broadcast_discovery: {e_bcast_general}", exc_info=True)
            if _discovery_active:
                time.sleep(10)
    
    logger.info("[DISCOVERY] Hilo broadcast_discovery terminado.")


def start_discovery():
    global _discovery_active
    _discovery_active = True
    logger.info("[DISCOVERY] Solicitando inicio de servicios de descubrimiento (hilos de escucha y broadcast)...")
    
    listener_thread = threading.Thread(target=listen_for_discovery, daemon=True, name="DiscoveryListenerThread")
    listener_thread.start()
    
    broadcaster_thread = threading.Thread(target=broadcast_discovery, daemon=True, name="DiscoveryBroadcasterThread")
    broadcaster_thread.start()
    
    logger.info("[DISCOVERY] Hilos de descubrimiento iniciados.")

def stop_discovery():
    global _discovery_active, _listener_socket
    logger.info("[DISCOVERY] Solicitando parada de servicios de descubrimiento...")
    _discovery_active = False

    if _listener_socket:
        try:
            _listener_socket.close() 
            logger.info("[DISCOVERY] Socket del listener de descubrimiento cerrado explícitamente para forzar la salida del hilo.")
        except socket.error as e_stop_close:
            logger.warning(f"[DISCOVERY] Error al cerrar el socket del listener en stop_discovery (puede que ya estuviera cerrado): {e_stop_close}")
        except Exception as e_generic_close:
            logger.error(f"[DISCOVERY] Excepción genérica al cerrar el socket del listener en stop_discovery: {e_generic_close}", exc_info=True)
    
    logger.info("[DISCOVERY] Servicios de descubrimiento señalados para detenerse. Los hilos deberían terminar en breve.")