# broadcast.py
import socket
import json
import time
import select
import random
from config_paths import TRUSTED_USERS_FILE, BANNED_USERS_FILE # KNOWN_PEER_DETAILS_FILE se usa a través de peer_utils
from config import PORT # USERNAME no se usa aquí directamente, se recibe de los peers
from discovery import obtener_broadcast # Asegúrate que esta función esté disponible
from peer_utils import update_peer_details, load_known_peer_details # Nuevas importaciones
import logging

logger = logging.getLogger(__name__)
BROADCAST_MESSAGE = b"MirrorClip-Discovery"

def cargar_lista(archivo):
    try:
        with open(archivo, 'r', encoding='utf-8') as f: # Especificar encoding
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Si es un archivo de usuarios, devolver dict con lista users, sino lista vacía.
        return {"users": []} if "users.json" in str(archivo) else []


def guardar_lista(archivo, lista_data): # Cambiado nombre de 'lista' a 'lista_data'
    try:
        with open(archivo, 'w', encoding='utf-8') as f: # Especificar encoding
            json.dump(lista_data, f, indent=4)
    except IOError as e:
        logger.error(f"No se pudo guardar la lista en {archivo}: {e}")


def descubrir_peers():
    logger.info(">>> [PEER DISCOVERY] Iniciando búsqueda de peers...")
    peers_discovered_ips = set()
    # Cargar detalles existentes para acceso rápido y evitar I/O repetida en get_peer_display_name si se usara aquí
    # known_details = load_known_peer_details() # No es necesario aquí si solo actualizamos

    try:
        trusted_users_data = cargar_lista(TRUSTED_USERS_FILE)
        banned_users_ips = cargar_lista(BANNED_USERS_FILE) # Asumiendo que BANNED_USERS_FILE solo contiene IPs directamente o {"users": []}
        
        # Asegurarse de que banned_users_ips es una lista de IPs
        if isinstance(banned_users_ips, dict):
            banned_users_list = banned_users_ips.get("users", [])
        elif isinstance(banned_users_ips, list): # Para compatibilidad si el formato es solo una lista de IPs
            banned_users_list = banned_users_ips
        else:
            banned_users_list = []


        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        s.bind(("0.0.0.0", 0)) # Puerto efímero para enviar y recibir respuestas de descubrimiento
        my_port = s.getsockname()[1]
        logger.info(f">>> [PEER DISCOVERY] Escuchando respuestas de descubrimiento en puerto efímero: {my_port}")
        
        s.setblocking(False)

        broadcast_addr = obtener_broadcast()
        logger.info(f">>> [PEER DISCOVERY] Dirección de broadcast calculada: {broadcast_addr}")
        logger.info(f">>> [PEER DISCOVERY] Enviando mensaje de descubrimiento a {broadcast_addr}:{PORT}")

        for i in range(3):  # Reducido a 3 intentos para acelerar un poco
            try:
                s.sendto(BROADCAST_MESSAGE, (broadcast_addr, PORT))
                logger.debug(f">>> [PEER DISCOVERY] Intento {i+1}/3: Mensaje enviado.")
                time.sleep(0.3 + random.random() * 0.5) 
            except Exception as e_send:
                logger.error(f">>> [PEER DISCOVERY] Error en envío de broadcast: {str(e_send)}")

        start_time = time.time()
        discovery_timeout = 6  # 6 segundos para esperar respuestas
        
        logger.info(">>> [PEER DISCOVERY] Esperando respuestas...")
        
        while time.time() - start_time < discovery_timeout:
            ready_to_read, _, _ = select.select([s], [], [], 0.5) # Timeout de select para no bloquear mucho
            if ready_to_read:
                try:
                    data, addr = s.recvfrom(1024)
                    ip_address = addr[0]
                    # port_num = addr[1] # No se usa el puerto de respuesta aquí

                    # Ignorar nuestros propios mensajes si el sistema los devuelve
                    try:
                        # Obtener IPs locales para comparar
                        # Esto puede ser costoso de llamar repetidamente en un bucle
                        # Se podría obtener una vez fuera del bucle si es necesario
                        hostname_local = socket.gethostname()
                        local_ips = socket.gethostbyname_ex(hostname_local)[2]
                        if ip_address in local_ips or ip_address == "127.0.0.1":
                            logger.debug(f">>> [PEER DISCOVERY] Respuesta ignorada de IP local: {ip_address}")
                            continue
                    except socket.gaierror: # Error al obtener IP local, continuar de todas formas
                        pass


                    logger.debug(f">>> [PEER DISCOVERY] Respuesta recibida de {ip_address}: {data[:60]}...") # Loguear solo parte del mensaje
                    
                    if data.startswith(b"HELLO:"):
                        try:
                            parts = data.decode('utf-8').split(":", 3) # Dividir max 3 veces: HELLO, user, host, ip_anunciada
                            if len(parts) >= 4: # HELLO, username, hostname, announced_ip
                                announced_username = parts[1]
                                announced_hostname = parts[2]
                                # La IP anunciada en el mensaje HELLO es la que el peer *cree* que tiene.
                                # Usamos la IP de origen del paquete (ip_address) como la IP autoritativa del peer.
                                peer_ip_authoritative = ip_address 
                                # announced_peer_ip = parts[3] # Podríamos loguearlo o compararlo

                                logger.info(f">>> [PEER DISCOVERY] Peer válido detectado: {peer_ip_authoritative} (Usuario: {announced_username}, Host: {announced_hostname})")
                                
                                # Actualizar detalles del peer (nombre, host)
                                update_peer_details(peer_ip_authoritative, announced_username, announced_hostname)

                                # Lógica de confianza y baneo (sin cambios funcionales, solo usa la lista correcta de baneados)
                                if peer_ip_authoritative not in banned_users_list:
                                    peers_discovered_ips.add(peer_ip_authoritative)
                                    # Añadir a confiables automáticamente si no está ya y no está baneado.
                                    # Esto puede ser agresivo; podrías querer que el usuario confirme.
                                    # Por ahora, se mantiene la lógica original de auto-confianza.
                                    if peer_ip_authoritative not in trusted_users_data.get("users", []):
                                        trusted_users_data.setdefault("users", []).append(peer_ip_authoritative)
                                        logger.info(f">>> [PEER DISCOVERY] Peer {peer_ip_authoritative} añadido automáticamente a confiables.")
                                else:
                                    logger.info(f">>> [PEER DISCOVERY] Peer {peer_ip_authoritative} está en la lista de baneados, ignorando.")
                            else:
                                logger.warning(">>> [PEER DISCOVERY] Mensaje HELLO incompleto recibido.")
                        except UnicodeDecodeError:
                            logger.warning(f">>> [PEER DISCOVERY] Error decodificando mensaje HELLO de {ip_address}.")
                        except Exception as e_parse:
                            logger.error(f">>> [PEER DISCOVERY] Error procesando mensaje HELLO: {str(e_parse)}")
                except socket.error as e_sock: # Errores de socket al recibir
                     # En Windows, un ICMP port unreachable puede generar WSAECONNRESET (10054)
                     # Esto puede ocurrir si enviamos broadcast y un host responde que el puerto no está abierto
                     if e_sock.winerror == 10054 if hasattr(e_sock, 'winerror') else False:
                         logger.debug(f">>> [PEER DISCOVERY] Ignorando error de conexión reseteada (WSAECONNRESET) de {addr[0]}.")
                     else:
                         logger.error(f">>> [PEER DISCOVERY] Error de socket recibiendo respuesta: {str(e_sock)}")
                except Exception as e_recv:
                    logger.error(f">>> [PEER DISCOVERY] Error general recibiendo respuesta: {str(e_recv)}")
            # else: # No data ready to read
                # logger.debug(f">>> [PEER DISCOVERY] No hay respuestas en este ciclo de select. Esperando... ({int(time.time() - start_time)}s)")
                # pass # No es necesario loguear esto tan frecuentemente
        
        guardar_lista(TRUSTED_USERS_FILE, trusted_users_data) # Guardar lista de confiables actualizada
        
    except socket.error as e:
        logger.error(f">>> [PEER DISCOVERY] Error de socket general en descubrir_peers: {str(e)}")
    except Exception as e_general:
        logger.error(f">>> [PEER DISCOVERY] Error inesperado en descubrir_peers: {str(e_general)}", exc_info=True)
    finally:
        if 's' in locals() and s:
            s.close()

    final_peer_list = list(peers_discovered_ips)
    logger.info(f">>> [PEER DISCOVERY] Peers finales encontrados en esta búsqueda: {final_peer_list}")
    return final_peer_list if final_peer_list else []