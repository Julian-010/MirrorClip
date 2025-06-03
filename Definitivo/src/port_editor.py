import tkinter as tk
from tkinter import ttk, messagebox
import configparser
from pathlib import Path
from config_paths import CONFIG_FILE

def cargar_puerto():
    """Carga el puerto desde el archivo de configuración"""
    config = configparser.ConfigParser()
    try:
        config.read(CONFIG_FILE)
        return config.getint("general", "port", fallback=1234)
    except (FileNotFoundError, configparser.Error):
        return 1234

class PortEditor:
    def __init__(self, current_port):
        self.applied = False
        self.current_port = current_port

        self.root = tk.Toplevel()
        self.root.title("Editar Puerto")
        self.root.minsize(300, 150)
        self.root.resizable(True, True)

        ttk.Label(self.root, text="Introduce el nuevo puerto (1024-65535):").pack(pady=10)

        self.port_var = tk.StringVar(value=str(current_port))
        self.entry = ttk.Entry(self.root, textvariable=self.port_var, width=10)
        self.entry.pack(pady=5)
        self.entry.select_range(0, tk.END)
        self.entry.focus_set()

        ttk.Button(self.root, text="Guardar", command=self.guardar).pack(pady=10)
        self.root.bind('<Return>', lambda e: self.guardar())

    def guardar(self, event=None):
        """Guarda el nuevo puerto en la configuración"""
        try:
            new_port = int(self.port_var.get())
            if 1024 <= new_port <= 65535:
                self.save_to_config(new_port)
                self.applied = True
                messagebox.showinfo("Puerto guardado", f"Puerto actualizado a {new_port}")
                self.root.destroy()
                return new_port
            messagebox.showerror("Error", "El puerto debe estar entre 1024 y 65535")
        except ValueError:
            messagebox.showerror("Error", "Debe introducir un número válido")
        return None

    def save_to_config(self, port):
        """Guarda el puerto en el archivo de configuración"""
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)

        # Asegura que el directorio del archivo existe
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

        if 'general' not in config:
            config['general'] = {}

        config['general']['port'] = str(port)

        with open(CONFIG_FILE, 'w') as f:
            config.write(f)

    def get_port(self):
        """Obtiene el nuevo puerto si fue aplicado correctamente"""
        return int(self.port_var.get()) if self.applied else None
