# discovery.py
import socket
import threading
import time
import json
import netifaces

from config import PORT, USERNAME, BROADCAST_INTERVAL
import logging

logger = logging.getLogger(__name__)

_discovery_active = True
_listener_socket = None


def obtener_broadcast_con_netifaces():
    """Obtiene la dirección de broadcast usando netifaces, priorizando la interfaz de gateway por defecto."""
    try:
        default_gateway_info = netifaces.gateways().get('default', {}).get(netifaces.AF_INET)
        if default_gateway_info:
            default_iface_name = default_gateway_info[1]
            if default_iface_name in netifaces.interfaces():
                addrs = netifaces.ifaddresses(default_iface_name)
                if netifaces.AF_INET in addrs:
                    for addr_info in addrs[netifaces.AF_INET]:
                        if 'broadcast' in addr_info and 'addr' in addr_info:
                            if not addr_info.get('addr', '').startswith('127.'):
                                broadcast_ip = addr_info['broadcast']
                                logger.info(f"[DISCOVERY] Usando dirección de broadcast de la interfaz de gateway por defecto '{default_iface_name}': {broadcast_ip}")
                                return broadcast_ip
        
        logger.info("[DISCOVERY] No se encontró broadcast en gateway por defecto. Escaneando otras interfaces...")
        for iface_name in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface_name)
            if netifaces.AF_INET in addrs:
                for addr_info in addrs[netifaces.AF_INET]:
                    if 'broadcast' in addr_info and 'addr' in addr_info:
                        ip_addr = addr_info['addr']
                        if not ip_addr.startswith('127.') and not ip_addr.startswith('169.254.'):
                            broadcast_ip = addr_info['broadcast']
                            logger.info(f"[DISCOVERY] Usando dirección de broadcast de la interfaz '{iface_name}': {broadcast_ip} (IP local: {ip_addr})")
                            return broadcast_ip
                            
    except ImportError:
        logger.error("[DISCOVERY] La biblioteca 'netifaces' no está instalada. Por favor, instálala con: pip install netifaces")
    except Exception as e:
        logger.error(f"[DISCOVERY] Error usando 'netifaces': {e}", exc_info=True)

    logger.warning("[DISCOVERY] No se pudo determinar la dirección de broadcast específica. Usando 255.255.255.255.")
    return "255.255.255.255"

obtener_broadcast = obtener_broadcast_con_netifaces


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
            if data == b"MirrorClip-Discovery":
                logger.info(f"[DISCOVERY] Solicitud de descubrimiento recibida de {addr[0]}:{addr[1]}")
                try:
                    my_hostname = socket.gethostname()
                    announced_ip = "127.0.0.1"
                    try:
                        temp_sock_ip = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        temp_sock_ip.connect(("8.8.8.8", 80))
                        announced_ip = temp_sock_ip.getsockname()[0]
                        temp_sock_ip.close()
                    except socket.error:
                        logger.warning("[DISCOVERY] No se pudo obtener la IP preferida para el mensaje HELLO.")
                    response_message = f"HELLO:{USERNAME}:{my_hostname}:{announced_ip}"
                    s.sendto(response_message.encode('utf-8'), addr)
                    logger.info(f"[DISCOVERY] Respuesta HELLO enviada a {addr[0]}:{addr[1]}")
                except Exception as e_response:
                    logger.error(f"[DISCOVERY] Error preparando/enviando respuesta HELLO: {e_response}", exc_info=True)
        except socket.timeout:
            continue
        except socket.error as e_sock_recv:
            # --- INICIO DE LA CORRECCIÓN ---
            # Comprobar si el error es el WinError 10054 (conexión reseteada)
            # Este error es esperado si el peer que buscaba ya cerró su socket de escucha.
            # Lo tratamos como una advertencia y continuamos, en lugar de cerrar el hilo.
            if hasattr(e_sock_recv, 'winerror') and e_sock_recv.winerror == 10054:
                logger.warning(f"[DISCOVERY] Se recibió un ICMP 'Port Unreachable' (WinError 10054). Esto es normal si el otro peer cerró su socket. Continuando la escucha.")
                continue # Continuar al siguiente ciclo del bucle
            # --- FIN DE LA CORRECCIÓN ---

            if not _discovery_active:
                 logger.info(f"[DISCOVERY] Error de socket en recvfrom (esperado durante el cierre): {e_sock_recv}")
            else:
                logger.error(f"[DISCOVERY] Error de socket en la escucha de descubrimiento: {e_sock_recv}")
                logger.error("[DISCOVERY] Deteniendo el hilo de escucha debido a un error de socket inesperado.")
                _discovery_active = False # Detener solo ante errores inesperados
        except Exception as e_recv_general:
            logger.error(f"[DISCOVERY] Error inesperado en la escucha de descubrimiento: {e_recv_general}", exc_info=True)
            if _discovery_active:
                time.sleep(1)
    
    if s:
        try:
            s.close()
            logger.info("[DISCOVERY] Socket de escucha de descubrimiento cerrado.")
        except socket.error:
            pass # El socket podría estar ya cerrado
    
    _listener_socket = None
    logger.info("[DISCOVERY] Hilo listen_for_discovery terminado.")

# El resto del archivo (broadcast_discovery, start_discovery, stop_discovery) permanece igual.
# Solo he añadido la corrección en listen_for_discovery.

def broadcast_discovery():
    global _discovery_active
    logger.info("[DISCOVERY] Iniciando hilo de transmisión de descubrimiento...")
    time.sleep(time.time() % 2.0 + 0.5)

    while _discovery_active:
        try:
            broadcast_ip_addr = obtener_broadcast()
            logger.info(f"[DISCOVERY] Usando dirección de broadcast: {broadcast_ip_addr} en puerto {PORT}")
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s_broadcast:
                s_broadcast.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                discovery_message = b"MirrorClip-Discovery"
                s_broadcast.sendto(discovery_message, (broadcast_ip_addr, PORT))
                logger.info(f"[DISCOVERY] Mensaje 'MirrorClip-Discovery' enviado a {broadcast_ip_addr}:{PORT}")
            for _ in range(int(BROADCAST_INTERVAL)):
                if not _discovery_active: break
                time.sleep(1)
            if not _discovery_active: break
        except Exception as e_bcast_general:
            logger.error(f"[DISCOVERY] Error inesperado en broadcast_discovery: {e_bcast_general}", exc_info=True)
            if _discovery_active: time.sleep(10)
    
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
        except Exception as e_stop_close:
            logger.warning(f"[DISCOVERY] Error al cerrar el socket del listener en stop_discovery: {e_stop_close}")
    
    logger.info("[DISCOVERY] Servicios de descubrimiento señalados para detenerse.")
