import tkinter as tk
from tkinter import ttk, messagebox
import json
from config_paths import TRUSTED_USERS_FILE, BANNED_USERS_FILE
from peer_utils import get_peer_display_name, load_known_peer_details # Para mostrar nombres amigables

class GestionUsuarios:
    def __init__(self, master):
        self.root = tk.Toplevel(master)
        self.root.title("Gestión de Contactos")
        self.root.geometry("600x450") # Un poco más de alto para los botones
        self.root.minsize(500, 350)

        self.notebook = ttk.Notebook(self.root)

        # Pestaña Confiables
        self.trusted_frame = ttk.Frame(self.notebook)
        self.trusted_listbox = self._build_list_frame(
            self.trusted_frame,
            "Confiables",
            self._move_selected_to_banned, # Acción para el botón secundario
            "Bloquear Seleccionado(s)"
        )
        self._load_users_into_listbox(TRUSTED_USERS_FILE, self.trusted_listbox)

        # Pestaña Bloqueados
        self.banned_frame = ttk.Frame(self.notebook)
        self.banned_listbox = self._build_list_frame(
            self.banned_frame,
            "Bloqueados",
            self._move_selected_to_trusted, # Acción para el botón secundario
            "Desbloquear y Confiar"
        )
        self._load_users_into_listbox(BANNED_USERS_FILE, self.banned_listbox)

        self.notebook.add(self.trusted_frame, text=" Contactos Confiables ")
        self.notebook.add(self.banned_frame, text=" Usuarios Bloqueados ")
        self.notebook.pack(expand=True, fill=tk.BOTH, padx=10, pady=(10,0))

        # Botón para refrescar ambas listas manualmente
        # ttk.Button(self.root, text="Actualizar Listas", command=self._refresh_all_lists).pack(pady=10) # Eliminado, refresh es implicito
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        self.root.destroy()

    def _build_list_frame(self, parent_frame, list_type_name, secondary_action_command, secondary_action_text):
        """Construye un frame con lista y controles, y devuelve la instancia de la listbox."""
        top_frame = ttk.Frame(parent_frame)
        top_frame.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)

        scroll = ttk.Scrollbar(top_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(top_frame, selectmode=tk.EXTENDED, yscrollcommand=scroll.set, exportselection=False)
        listbox.pack(expand=True, fill=tk.BOTH)
        scroll.config(command=listbox.yview)

        btn_frame = ttk.Frame(parent_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=(0,5))

        primary_action_text = f"Eliminar de {list_type_name}"
        file_to_modify = TRUSTED_USERS_FILE if list_type_name == "Confiables" else BANNED_USERS_FILE

        ttk.Button(btn_frame, text=primary_action_text,
                   command=lambda lb=listbox, f=file_to_modify: self._remove_selected_from_file(lb, f)).pack(side=tk.LEFT, padx=(0,5))
        
        if secondary_action_command:
            ttk.Button(btn_frame, text=secondary_action_text,
                       command=lambda lb=listbox: secondary_action_command(lb)).pack(side=tk.LEFT)
        
        return listbox

    def _load_users_into_listbox(self, file_path, listbox_widget):
        """Carga IPs desde un archivo JSON en la ListBox especificada y muestra nombres amigables."""
        listbox_widget.delete(0, tk.END)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            ips = data.get("users", [])
            
            if not ips:
                listbox_widget.insert(tk.END, "No hay usuarios en esta lista.")
                listbox_widget.config(state=tk.DISABLED) # Deshabilitar si está vacía
                return

            listbox_widget.config(state=tk.NORMAL) # Habilitar si tiene contenido
            known_details = load_known_peer_details() # Cargar una vez para eficiencia
            
            # Guardar el mapeo de texto de la listbox a IP original
            listbox_widget.ip_map = {}

            for ip_address in ips:
                display_name = get_peer_display_name(ip_address, details=known_details)
                list_entry_text = f"{display_name}"
                if display_name != ip_address: # Si el nombre es diferente a la IP, añadir IP para claridad
                    list_entry_text += f" ({ip_address})"
                
                listbox_widget.insert(tk.END, list_entry_text)
                listbox_widget.ip_map[list_entry_text] = ip_address

        except FileNotFoundError:
            listbox_widget.insert(tk.END, "Archivo no encontrado. No hay usuarios para mostrar.")
            listbox_widget.config(state=tk.DISABLED)
        except json.JSONDecodeError:
            listbox_widget.insert(tk.END, "Error al leer el archivo de usuarios (formato incorrecto).")
            listbox_widget.config(state=tk.DISABLED)
            messagebox.showerror("Error de Archivo", f"No se pudo leer {file_path} debido a un error de formato JSON.", parent=self.root)
        except Exception as e:
            listbox_widget.insert(tk.END, f"Error al cargar usuarios: {type(e).__name__}")
            listbox_widget.config(state=tk.DISABLED)
            messagebox.showerror("Error", f"Ocurrió un error inesperado al cargar {file_path}: {e}", parent=self.root)

    def _get_selected_ips(self, listbox_widget):
        selected_indices = listbox_widget.curselection()
        if not selected_indices:
            messagebox.showwarning("Advertencia", "Selecciona al menos un usuario de la lista.", parent=self.root)
            return []
        
        selected_ips = []
        for i in selected_indices:
            list_entry_text = listbox_widget.get(i)
            # Obtener la IP original del mapeo
            ip = listbox_widget.ip_map.get(list_entry_text)
            if ip:
                selected_ips.append(ip)
            else:
                # Esto no debería pasar si el mapeo está bien, pero como fallback, intentar extraer de la cadena
                # Asumiendo formato "Nombre (IP)" o solo "IP"
                if '(' in list_entry_text and ')' in list_entry_text:
                    try:
                        ip_from_text = list_entry_text.split('(')[1].split(')')[0]
                        selected_ips.append(ip_from_text) # Potencialmente usar una validación de IP aquí
                    except IndexError: # Si el parseo falla
                        selected_ips.append(list_entry_text) # Asumir que el texto es la IP
                else:
                     selected_ips.append(list_entry_text)


        if not any(selected_ips): # Si después del mapeo no hay IPs válidas
            messagebox.showerror("Error Interno", "No se pudieron obtener las IPs de los usuarios seleccionados.", parent=self.root)
            return []
        return selected_ips

    def _remove_selected_from_file(self, listbox_widget, file_path):
        selected_ips = self._get_selected_ips(listbox_widget)
        if not selected_ips:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            current_ips = data.get("users", [])
            users_to_keep = [ip for ip in current_ips if ip not in selected_ips]
            
            if len(users_to_keep) == len(current_ips):
                messagebox.showinfo("Información", "Ninguno de los usuarios seleccionados se encontró en el archivo.", parent=self.root)
                return

            data["users"] = users_to_keep
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            
            messagebox.showinfo("Éxito", f"{len(selected_ips)} usuario(s) eliminado(s) de la lista.", parent=self.root)
            self._refresh_all_lists() # Actualizar ambas listas
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo modificar el archivo {file_path}: {e}", parent=self.root)

    def _move_selected_to_banned(self, listbox_widget): # Mover de Confiables a Bloqueados
        selected_ips = self._get_selected_ips(listbox_widget)
        if not selected_ips:
            return

        try:
            # Cargar lista de confiables
            with open(TRUSTED_USERS_FILE, 'r', encoding='utf-8') as f:
                trusted_data = json.load(f)
            trusted_ips = trusted_data.get("users", [])

            # Cargar lista de bloqueados
            with open(BANNED_USERS_FILE, 'r', encoding='utf-8') as f:
                banned_data = json.load(f)
            banned_ips = banned_data.get("users", [])

            ips_moved = 0
            for ip_to_move in selected_ips:
                if ip_to_move in trusted_ips:
                    trusted_ips.remove(ip_to_move)
                if ip_to_move not in banned_ips:
                    banned_ips.append(ip_to_move)
                ips_moved +=1
            
            trusted_data["users"] = trusted_ips
            banned_data["users"] = banned_ips

            with open(TRUSTED_USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(trusted_data, f, indent=4)
            with open(BANNED_USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(banned_data, f, indent=4)
            
            if ips_moved > 0:
                messagebox.showinfo("Éxito", f"{ips_moved} usuario(s) movido(s) a la lista de bloqueados.", parent=self.root)
            else:
                messagebox.showinfo("Información", "No se movieron usuarios. Puede que ya estuvieran en el estado deseado o no se encontraran.", parent=self.root)
            self._refresh_all_lists()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo mover usuarios a bloqueados: {e}", parent=self.root)

    def _move_selected_to_trusted(self, listbox_widget): # Mover de Bloqueados a Confiables
        selected_ips = self._get_selected_ips(listbox_widget)
        if not selected_ips:
            return

        try:
            # Cargar lista de bloqueados
            with open(BANNED_USERS_FILE, 'r', encoding='utf-8') as f:
                banned_data = json.load(f)
            banned_ips = banned_data.get("users", [])

            # Cargar lista de confiables
            with open(TRUSTED_USERS_FILE, 'r', encoding='utf-8') as f:
                trusted_data = json.load(f)
            trusted_ips = trusted_data.get("users", [])

            ips_moved = 0
            for ip_to_move in selected_ips:
                if ip_to_move in banned_ips:
                    banned_ips.remove(ip_to_move)
                if ip_to_move not in trusted_ips:
                    trusted_ips.append(ip_to_move)
                ips_moved +=1

            banned_data["users"] = banned_ips
            trusted_data["users"] = trusted_ips

            with open(BANNED_USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(banned_data, f, indent=4)
            with open(TRUSTED_USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(trusted_data, f, indent=4)

            if ips_moved > 0:
                messagebox.showinfo("Éxito", f"{ips_moved} usuario(s) desbloqueado(s) y añadido(s) a confiables.", parent=self.root)
            else:
                messagebox.showinfo("Información", "No se movieron usuarios.", parent=self.root)

            self._refresh_all_lists()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo mover usuarios a confiables: {e}", parent=self.root)

    def _refresh_all_lists(self):
        """Actualiza el contenido de ambas listboxes."""
        self._load_users_into_listbox(TRUSTED_USERS_FILE, self.trusted_listbox)
        self._load_users_into_listbox(BANNED_USERS_FILE, self.banned_listbox)