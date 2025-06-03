import tkinter as tk
from tkinter import ttk, messagebox
import json
import os # Para os.path.exists
import threading
import socket # Para socket.gethostname y obtener_ip_local
import time
from config_paths import TRUSTED_USERS_FILE, BANNED_USERS_FILE
from peer_utils import get_peer_display_name, load_known_peer_details
from broadcast import descubrir_peers, cargar_lista, guardar_lista # Importar funciones de broadcast.py
import logging

logger = logging.getLogger(__name__)

class EstadoVentana:
    def __init__(self, master):
        self.root = tk.Toplevel(master)
        self.root.title("Estado de MirrorClip")
        self.root.minsize(450, 350)
        self.root.resizable(True, True)
        
        self.local_ip = self.obtener_ip_local()
        logger.debug(f"[EstadoVentana] IP local detectada: {self.local_ip}")
        
        self.listbox_text_to_ip_map = {} 

        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        info_frame = ttk.LabelFrame(main_frame, text="Información del Dispositivo")
        info_frame.pack(fill=tk.X, pady=(0,10), padx=5)
        
        ttk.Label(info_frame, text=f"Nombre del equipo: {socket.gethostname()}").pack(anchor="w", padx=5, pady=2)
        ttk.Label(info_frame, text=f"IP local principal: {self.local_ip}").pack(anchor="w", padx=5, pady=2)
        
        try:
            from config import PORT as APP_PORT
            ttk.Label(info_frame, text=f"Puerto TCP: {APP_PORT}").pack(anchor="w", padx=5, pady=2)
        except ImportError:
             logger.warning("[EstadoVentana] No se pudo importar APP_PORT desde config para mostrar en UI.")
             ttk.Label(info_frame, text="Puerto TCP: (no disponible)").pack(anchor="w", padx=5, pady=2)

        peers_frame = ttk.LabelFrame(main_frame, text="Dispositivos Detectados en la Red")
        peers_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)
        
        scrollbar = ttk.Scrollbar(peers_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(5,0), padx=(0,5))
        
        self.peers_listbox = tk.Listbox(
            peers_frame, 
            yscrollcommand=scrollbar.set,
            selectmode=tk.SINGLE,
            height=8,
            exportselection=False # Para evitar que la selección se borre al perder el foco
        )
        self.peers_listbox.pack(fill=tk.BOTH, expand=True, padx=(5,0), pady=(5,0))
        scrollbar.config(command=self.peers_listbox.yview)
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="Confiar", command=self.confiar_seleccionado).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Bloquear", command=self.bloquear_seleccionado).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Actualizar Lista", command=self.actualizar_peers).pack(side=tk.RIGHT, padx=5)

        self.status_label = ttk.Label(main_frame, text="Actualizando lista de peers...")
        self.status_label.pack(pady=(5,0), anchor="w", padx=5)
        
        self.actualizar_peers()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        # Aquí podrías añadir lógica si necesitas hacer algo específico al cerrar esta ventana
        self.root.destroy()

    def obtener_ip_local(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.1)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception as e:
            logger.warning(f"No se pudo determinar la IP local principal: {e}")
            return "Desconocida"

    def actualizar_peers(self):
        self.peers_listbox.delete(0, tk.END)
        self.listbox_text_to_ip_map.clear()
        self.peers_listbox.insert(tk.END, "Buscando dispositivos en la red...")
        self.peers_listbox.config(state=tk.DISABLED) # Deshabilitar mientras busca
        self.status_label.config(text="Actualizando...")
        threading.Thread(target=self._worker_descubrir_peers, daemon=True).start()

    def _worker_descubrir_peers(self):
        try:
            start_time = time.time()
            # descubrir_peers() se importa desde broadcast.py y ya está disponible
            discovered_ips = descubrir_peers() 
            elapsed_time = time.time() - start_time
            
            if self.root.winfo_exists(): # Comprobar si la ventana aún existe
                self.root.after(0, self.mostrar_peers_en_listbox, discovered_ips, elapsed_time)
        except Exception as e:
            logger.error(f"Error durante el descubrimiento de peers en el worker: {e}", exc_info=True)
            if self.root.winfo_exists():
                self.root.after(0, self.mostrar_error_en_listbox, f"Error en descubrimiento: {e}")

    def mostrar_peers_en_listbox(self, peer_ips, elapsed_time):
        if not self.root.winfo_exists(): return # No hacer nada si la ventana ya no existe

        self.peers_listbox.config(state=tk.NORMAL) # Habilitar antes de modificar
        self.peers_listbox.delete(0, tk.END)
        self.listbox_text_to_ip_map.clear()

        if not peer_ips:
            self.peers_listbox.insert(tk.END, "No se encontraron otros dispositivos.")
            self.peers_listbox.config(state=tk.DISABLED)
        else:
            known_details = load_known_peer_details()
            found_other_peers = False
            for peer_ip in peer_ips:
                if peer_ip == self.local_ip:
                    continue 
                found_other_peers = True
                display_name = get_peer_display_name(peer_ip, details=known_details)
                
                list_entry_text = f"{display_name}"
                if display_name != peer_ip:
                    list_entry_text += f" ({peer_ip})"
                
                self.peers_listbox.insert(tk.END, list_entry_text)
                self.listbox_text_to_ip_map[list_entry_text] = peer_ip
            
            if not found_other_peers:
                self.peers_listbox.insert(tk.END, "No se encontraron *otros* dispositivos.")
                self.peers_listbox.config(state=tk.DISABLED)


        timestamp = time.strftime("%H:%M:%S")
        self.status_label.config(text=f"Actualizado: {timestamp} | Búsqueda: {elapsed_time:.2f}s | Encontrados (otros): {len(self.listbox_text_to_ip_map)}")

    def mostrar_error_en_listbox(self, mensaje_error):
        if not self.root.winfo_exists(): return

        self.peers_listbox.config(state=tk.NORMAL)
        self.peers_listbox.delete(0, tk.END)
        self.peers_listbox.insert(tk.END, mensaje_error)
        self.status_label.config(text="Error durante la búsqueda.")
        self.peers_listbox.config(state=tk.DISABLED)


    def _get_selected_ip_and_display_text(self):
        selection_indices = self.peers_listbox.curselection()
        if not selection_indices:
            messagebox.showwarning("Ninguna Selección", "Por favor, selecciona un dispositivo de la lista.", parent=self.root)
            return None, None
        
        selected_display_text = self.peers_listbox.get(selection_indices[0])
        selected_ip = self.listbox_text_to_ip_map.get(selected_display_text)
        
        if not selected_ip:
            messagebox.showerror("Error Interno", "No se pudo encontrar la IP para el dispositivo seleccionado.", parent=self.root)
            logger.error(f"Error: IP no encontrada en el mapeo para el texto: '{selected_display_text}'")
            return None, None
        return selected_ip, selected_display_text

    def confiar_seleccionado(self):
        peer_ip, display_text = self._get_selected_ip_and_display_text()
        if not peer_ip:
            return

        try:
            # Usar cargar_lista de broadcast.py
            trusted_users_data = cargar_lista(TRUSTED_USERS_FILE) 
            # cargar_lista devuelve {"users": []} para archivos de usuarios por defecto o si hay error/no existe
            
            if peer_ip not in trusted_users_data.get("users", []):
                trusted_users_data.setdefault("users", []).append(peer_ip) # setdefault es robusto
                guardar_lista(TRUSTED_USERS_FILE, trusted_users_data) # Usar guardar_lista de broadcast.py
                messagebox.showinfo("Dispositivo Confiable", f"'{display_text}' ha sido añadido a la lista de dispositivos confiables.", parent=self.root)
                self._remove_from_list_file(BANNED_USERS_FILE, peer_ip, "baneados")
            else:
                messagebox.showinfo("Información", f"'{display_text}' ya está en la lista de confiables.", parent=self.root)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo añadir '{display_text}' a confiables: {e}", parent=self.root)
            logger.error(f"Error al confiar en {peer_ip}: {e}", exc_info=True)

    def bloquear_seleccionado(self):
        peer_ip, display_text = self._get_selected_ip_and_display_text()
        if not peer_ip:
            return

        try:
            banned_users_data = cargar_lista(BANNED_USERS_FILE)

            if peer_ip not in banned_users_data.get("users", []):
                banned_users_data.setdefault("users", []).append(peer_ip)
                guardar_lista(BANNED_USERS_FILE, banned_users_data)
                messagebox.showinfo("Dispositivo Bloqueado", f"'{display_text}' ha sido añadido a la lista de dispositivos bloqueados.", parent=self.root)
                self._remove_from_list_file(TRUSTED_USERS_FILE, peer_ip, "confiables")
            else:
                messagebox.showinfo("Información", f"'{display_text}' ya está en la lista de bloqueados.", parent=self.root)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo bloquear a '{display_text}': {e}", parent=self.root)
            logger.error(f"Error al bloquear a {peer_ip}: {e}", exc_info=True)

    def _remove_from_list_file(self, filepath, ip_to_remove, list_name_for_log):
        """Quita una IP de un archivo de lista (confiables o baneados)."""
        try:
            data = cargar_lista(filepath) # Esto debería devolver {"users": []}
            if ip_to_remove in data.get("users", []):
                data["users"].remove(ip_to_remove)
                guardar_lista(filepath, data)
                logger.info(f"IP {ip_to_remove} eliminada de la lista de {list_name_for_log} ({filepath})")
            else:
                logger.debug(f"IP {ip_to_remove} no encontrada en la lista de {list_name_for_log} ({filepath}), no se eliminó nada.")
        except Exception as e:
            logger.error(f"Error eliminando IP {ip_to_remove} de {filepath}: {e}", exc_info=True)
            # No mostrar messagebox aquí para no interrumpir el flujo si es una operación secundaria.