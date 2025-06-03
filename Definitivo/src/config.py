import configparser
import os
import sys
from pathlib import Path
from config_paths import CONFIG_FILE
import tkinter as tk
from tkinter import ttk
from config_paths import (
    CONFIG_DIR, KEYS_DIR, LOG_DIR, # Nuevos directorios de datos de usuario
    ASSETS_DIR, # Directorio de assets (solo lectura, gestionado por el instalador)
    TRUSTED_USERS_FILE, BANNED_USERS_FILE, KNOWN_PEER_DETAILS_FILE # KNOWN_PEER_DETAILS_FILE no se crea aquí explícitamente
)
import json
import socket

def crear_estructura_completa():
    """Crea TODOS los directorios y archivos iniciales necesarios para los datos del USUARIO."""
    # Crear directorios de datos del usuario si no existen
    # Estos directorios estarán en la carpeta de perfil del usuario (ej. AppData)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True) # Nuevo directorio para logs

    # ASSETS_DIR es donde está el ejecutable y es manejado por el instalador,
    # no es necesario crearlo aquí si es solo para lectura.
    # Si tienes assets que se escriben, también deberían ir a USER_DATA_ROOT_DIR.
    # ASSETS_DIR.mkdir(parents=True, exist_ok=True) # Probablemente no necesario aquí

    # Crear archivos JSON de configuración inicial si no existen en CONFIG_DIR
    # KNOWN_PEER_DETAILS_FILE se crea/maneja en peer_utils.py
    # por lo que no es necesario crearlo aquí explícitamente.
    for json_file_path in [TRUSTED_USERS_FILE, BANNED_USERS_FILE]:
        if not json_file_path.exists():
            with open(json_file_path, "w", encoding='utf-8') as f:
                json.dump({"users": []}, f, indent=4)

# Ejecuta esta función al importar el módulo
crear_estructura_completa()

class VentanaNombreUsuario:
    def __init__(self, default_username="UsuarioX"):
        self.username = default_username
        self.applied = False

        self.root = tk.Toplevel()
        self.root.title("Nombre de Usuario")
        self.root.minsize(350, 200)
        self.root.resizable(False, False)

        ttk.Label(self.root, text="Selecciona una opción:").pack(pady=10)

        self.opcion_var = tk.StringVar(value="personalizado")

        frame_opciones = ttk.Frame(self.root)
        frame_opciones.pack(pady=5)

        ttk.Radiobutton(
            frame_opciones, text="Usar nombre del equipo",
            variable=self.opcion_var, value="equipo",
            command=self.actualizar_estado
        ).pack(anchor="w")

        ttk.Radiobutton(
            frame_opciones, text="Introducir un nombre personalizado",
            variable=self.opcion_var, value="personalizado",
            command=self.actualizar_estado
        ).pack(anchor="w")

        self.username_var = tk.StringVar()
        self.entry = ttk.Entry(self.root, textvariable=self.username_var, width=30)
        self.entry.pack(pady=10)

        ttk.Button(self.root, text="Guardar", command=self.guardar).pack(pady=10)
        self.root.bind('<Return>', lambda e: self.guardar())

        self.actualizar_estado()

        self.root.grab_set()
        self.root.wait_window()

    def actualizar_estado(self):
        if self.opcion_var.get() == "equipo":
            self.entry.configure(state="disabled")
        else:
            self.entry.configure(state="normal")
            self.entry.focus_set()

    def guardar(self):
        if self.opcion_var.get() == "equipo":
            self.username = socket.gethostname()
        else:
            nombre = self.username_var.get().strip()
            self.username = nombre if nombre else "UsuarioX"
        self.applied = True
        self.root.destroy()

def pedir_nombre_usuario_gui():
    root = tk.Tk()
    root.withdraw()
    ventana = VentanaNombreUsuario()
    root.destroy()
    return ventana.username

def crear_config_si_no_existe():
    """Crea el archivo de configuración si no existe."""
    if not CONFIG_FILE.exists():
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        config = configparser.ConfigParser()
        config["general"] = {
            "username": pedir_nombre_usuario_gui(),
            "port": "1234",
            "broadcast_interval": "30"
        }
        with open(CONFIG_FILE, "w") as f:
            config.write(f)

# Asegura que el archivo exista al importar el módulo
crear_config_si_no_existe()

# Carga la configuración
config = configparser.ConfigParser()
config.read(CONFIG_FILE)
USERNAME = config.get("general", "username")
PORT = config.getint("general", "port")
BROADCAST_INTERVAL = config.getint("general", "broadcast_interval")