import json
import datetime
import socket 
from config_paths import KNOWN_PEER_DETAILS_FILE, CONFIG_DIR
import logging

logger = logging.getLogger(__name__)

try:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
except Exception as e:
    logger.error(f"[PEER_UTILS] No se pudo crear el directorio de configuración {CONFIG_DIR}: {e}")

def load_known_peer_details():
    try:
        with open(KNOWN_PEER_DETAILS_FILE, 'r', encoding='utf-8') as f:
            details = json.load(f)
            logger.debug(f"[PEER_UTILS] Detalles de peers cargados desde JSON: {details}")
            return details
    except FileNotFoundError:
        logger.info(f"[PEER_UTILS] Archivo {KNOWN_PEER_DETAILS_FILE} no encontrado. Creando y/o retornando dict vacío.")
        save_known_peer_details({}) # Crear el archivo si no existe con un dict vacío
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"[PEER_UTILS] Error decodificando JSON de {KNOWN_PEER_DETAILS_FILE}: {e}. Retornando dict vacío.")
        return {}
    except Exception as e_load:
        logger.error(f"[PEER_UTILS] Error inesperado cargando {KNOWN_PEER_DETAILS_FILE}: {e_load}. Retornando dict vacío.")
        return {}

def save_known_peer_details(details):
    try:
        with open(KNOWN_PEER_DETAILS_FILE, 'w', encoding='utf-8') as f:
            json.dump(details, f, indent=4)
        # Cambiado a DEBUG para no ser tan verboso en INFO
        logger.debug(f"[PEER_UTILS] Detalles de peers guardados en JSON: {KNOWN_PEER_DETAILS_FILE} con contenido: {details}")
    except IOError as e:
        logger.error(f"[PEER_UTILS] No se pudo guardar los detalles de los peers en {KNOWN_PEER_DETAILS_FILE}: {e}")
    except Exception as e_save:
        logger.error(f"[PEER_UTILS] Error inesperado guardando {KNOWN_PEER_DETAILS_FILE}: {e_save}")

def update_peer_details(ip_address, username, hostname):
    if not ip_address or not isinstance(ip_address, str):
        logger.warning(f"[PEER_UTILS] Intento de actualizar detalles con IP inválida: {ip_address}")
        return

    # Validar y limpiar username y hostname
    username = str(username).strip() if username is not None and str(username).strip() else "Desconocido"
    hostname = str(hostname).strip() if hostname is not None and str(hostname).strip() else "Desconocido"


    logger.debug(f"[PEER_UTILS] Actualizando/Añadiendo detalles para IP: {ip_address} -> Usuario: '{username}', Hostname: '{hostname}'")
    details = load_known_peer_details()
    
    # Actualizar solo si hay nueva información o la entrada no existe
    # o si la información existente es genérica y la nueva es más específica.
    current_info = details.get(ip_address)
    should_update = True
    if current_info:
        is_current_username_generic = not current_info.get("username") or current_info.get("username").lower() in ["usuariox", "desconocido"]
        is_new_username_specific = username and username.lower() not in ["usuariox", "desconocido"]
        
        is_current_hostname_generic = not current_info.get("hostname") or current_info.get("hostname").lower() == "desconocido"
        is_new_hostname_specific = hostname and hostname.lower() != "desconocido"

        # Solo actualizar si la nueva información es mejor o diferente
        if (current_info.get("username") == username or (is_current_username_generic and not is_new_username_specific)) and \
           (current_info.get("hostname") == hostname or (is_current_hostname_generic and not is_new_hostname_specific)):
            # Si la información es la misma, o si la actual es genérica y la nueva también es genérica/vacía,
            # solo actualizamos 'last_seen' a menos que la nueva info sea más específica.
            if not (is_new_username_specific and current_info.get("username") != username) and \
               not (is_new_hostname_specific and current_info.get("hostname") != hostname):
                should_update = False # No hay cambios significativos en nombre/host

    if should_update or not current_info:
        details[ip_address] = {
            "username": username if username and username.lower() != "desconocido" else (current_info.get("username") if current_info else username),
            "hostname": hostname if hostname and hostname.lower() != "desconocido" else (current_info.get("hostname") if current_info else hostname),
            "last_seen": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        # Asegurar que no guardamos "Desconocido" si ya teníamos un nombre mejor
        if details[ip_address]["username"].lower() == "desconocido" and current_info and current_info.get("username", "").lower() not in ["", "desconocido", "usuariox"]:
            details[ip_address]["username"] = current_info.get("username")
        if details[ip_address]["hostname"].lower() == "desconocido" and current_info and current_info.get("hostname", "").lower() not in ["", "desconocido"]:
            details[ip_address]["hostname"] = current_info.get("hostname")

        logger.info(f"[PEER_UTILS] Detalles para IP {ip_address} actualizados a: Usuario='{details[ip_address]['username']}', Hostname='{details[ip_address]['hostname']}'")
    else:
        # Solo actualizar 'last_seen' si no hay otros cambios
        details[ip_address]["last_seen"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        logger.debug(f"[PEER_UTILS] Solo 'last_seen' actualizado para IP: {ip_address}")

    save_known_peer_details(details)


def get_peer_display_name(ip_address, details=None):
    if not ip_address: 
        logger.warning("[PEER_UTILS] get_peer_display_name llamado con ip_address vacío/nulo.")
        return "IP Desconocida"

    # Asegurar que ip_address es una cadena para la búsqueda en el diccionario
    ip_address_str = str(ip_address)

    if details is None:
        logger.debug(f"[PEER_UTILS] get_peer_display_name({ip_address_str}): Cargando detalles desde archivo...")
        details = load_known_peer_details()
    # else:
        # logger.debug(f"[PEER_UTILS] get_peer_display_name({ip_address_str}): Usando detalles pre-cargados.")

    peer_info = details.get(ip_address_str) 
    display_name_to_return = ip_address_str # Por defecto, mostrar la IP

    if peer_info:
        username = peer_info.get("username", "").strip() 
        hostname = peer_info.get("hostname", "").strip() 
        # logger.debug(f"[PEER_UTILS] Info encontrada para {ip_address_str}: User='{username}', Host='{hostname}'")
        
        # Priorizar nombre de usuario si no es genérico, luego hostname si no es genérico, sino IP.
        is_username_valid = username and username.lower() not in ["usuariox", "desconocido", ""]
        is_hostname_valid = hostname and hostname.lower() not in ["desconocido", ""]
        
        if is_username_valid:
            display_name_to_return = username
        elif is_hostname_valid:
            display_name_to_return = hostname
        # Si ambos son genéricos o vacíos, se mantiene la IP como display_name_to_return.
        
    # else:
        # logger.info(f"[PEER_UTILS] No se encontraron detalles para la IP {ip_address_str} en known_peer_details.json. Se usará la IP.")
    
    logger.debug(f"[PEER_UTILS] get_peer_display_name para IP {ip_address_str} retorna: '{display_name_to_return}'")
    return display_name_to_return