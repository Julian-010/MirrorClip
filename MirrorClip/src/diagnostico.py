import socket
import subprocess

def verificar_conectividad():
    print("\n[DIAGNÓSTICO DE RED]")
    
    # 1. Verificar configuración IP
    print("\n1. Configuración IP:")
    subprocess.run("ipconfig /all", shell=True)
    
    # 2. Verificar rutas
    print("\n2. Tabla de rutas:")
    subprocess.run("route print", shell=True)
    
    # 3. Verificar ARP
    print("\n3. Tabla ARP:")
    subprocess.run("arp -a", shell=True)
    
    # 4. Verificar firewall
    print("\n4. Estado de firewall:")
    subprocess.run("netsh advfirewall firewall show rule name=all", shell=True)
    
    # 5. Prueba de socket
    print("\n5. Prueba de socket UDP:")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("0.0.0.0", 0))
        port = s.getsockname()[1]
        print(f"  Socket creado en puerto {port}")
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.sendto(b"TEST", ("255.255.255.255", 12345))
        print("  Mensaje broadcast enviado")
        s.settimeout(3)
        try:
            data, addr = s.recvfrom(1024)
            print(f"  Respuesta recibida de {addr}: {data}")
        except socket.timeout:
            print("  No se recibieron respuestas (timeout)")
    except Exception as e:
        print(f"  Error: {str(e)}")

if __name__ == "__main__":
    verificar_conectividad()
    input("\nPresiona Enter para salir...")