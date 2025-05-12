import socket
import threading
import json
from port_editor import cargar_puerto, PortEditor

PUERTO = cargar_puerto()
print(f"Usando puerto: {PUERTO}")

# Cuando necesites cambiar el puerto (ej: desde un menú)
def cambiar_puerto():
    PortEditor()  # Abre la GUI y guarda automáticamente
    global PUERTO
    PUERTO = cargar_puerto()  # Recarga el valor actualizado
    print(f"Nuevo puerto: {PUERTO}")
    
known_peers = ["192.168.1.42", "192.168.1.43"]  # IPs conocidas de otros peers (añade más)

def handle_connection(conn, addr):
    print(f"[RECIBIDO de {addr}]")
    while True:
        try:
            data = conn.recv(1024)
            if not data:
                break
            print(f"[{addr}] {data.decode()}")
        except:
            break
    conn.close()

def listen_for_peers():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("", PORT))  # escucha en cualquier IP local
    listener.listen()
    print(f"[LISTENING] Esperando conexiones en el puerto {PORT}...")
    while True:
        conn, addr = listener.accept()
        threading.Thread(target=handle_connection, args=(conn, addr), daemon=True).start()

def connect_to_peer(ip):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((ip, PORT))
        print(f"[CONECTADO a {ip}]")
        while True:
            msg = input(f"[A {ip}] > ")
            s.send(msg.encode())
    except:
        print(f"[ERROR] No se pudo conectar a {ip}")

def main():
    threading.Thread(target=listen_for_peers, daemon=True).start()

    for peer_ip in known_peers:
        threading.Thread(target=connect_to_peer, args=(peer_ip,), daemon=True).start()

    # Mantiene el programa corriendo
    while True:
        pass

if __name__ == "__main__":
    main()

