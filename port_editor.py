"""
GUI to edit the current port the application is running on
"""

import tkinter
from tkinter import ttk
from tkinter import messagebox
import json

CONFIG_FILE = "config_port.json"

def guardar_puerto(port):
    """Guarda el puerto en config_port.json"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"puerto": port}, f)

def cargar_puerto():
    """Carga el puerto desde config.json o retorna 1234 por defecto"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f).get("puerto", 1234)
    except (FileNotFoundError, json.JSONDecodeError):
        return 1234
    
class PortEditor:
    def __init__(self, current_port):
        self.applied = False
        self.port_number = current_port  # Guardamos el valor directamente (sin tk.IntVar)

        self.root = tkinter.Tk()
        self.root.title('Editar Puerto')
        
        # Manejo seguro del icono (si no existe, no falla)
        try:
            self.root.iconbitmap('systray_icon.ico')
        except:
            pass
        
        self.root.geometry('250x75')
        self.root.resizable(False, False)
        self.root.bind('<Return>', lambda _: self.apply_port_number())
        
        # Evitar que el usuario cierre la ventana sin aplicar
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.port_label = ttk.Label(self.root, text='Introduce el Puerto (1024-6535):', font=('Arial', 11))
        self.port_label.pack(side=tkinter.TOP, padx=5, pady=5, fill=tkinter.X)

        self.entry_frame = ttk.Frame(self.root)

        self.port_number = tkinter.IntVar(value=current_port)
        self.validate_command = self.root.register(lambda text: text.isdigit() or not text)
        self.port_input = ttk.Entry(self.root, textvariable=self.port_number, font=('Arial', 11), validate='all',
                                    validatecommand=(self.validate_command, '%P'))
        self.port_input.pack(side=tkinter.LEFT, padx=(5, 2), fill=tkinter.X, expand=True)

        self.apply_button = ttk.Button(self.root, text='Aceptar', command=self.apply_port_number)
        self.apply_button.pack(side=tkinter.RIGHT, padx=(2, 5))

        self.entry_frame.pack(side=tkinter.BOTTOM)

        self.root.mainloop()

    def apply_port_number(self):
        min_port = 1024
        max_port = 65535

        if min_port <= self.port_number.get() <= max_port:
            guardar_puerto(self.port_number.get())  # ¡AÑADIDO! Guarda en JSON
            self.applied = True
            self.root.destroy()
        else:
            messagebox.showwarning(title='Puerto invalido',
                                 message=f'Debe ser un numero entre {min_port} y {max_port}')

    def on_close(self):
        """Maneja el cierre de la ventana sin aplicar cambios"""
        self.applied = False
        self.root.destroy()

    def get_port(self):
        """Devuelve el puerto modificado si se aplicó, None en caso contrario"""
        return self.port_number.get() if self.applied else None

def _guardar(self):
        try:
            nuevo_puerto = int(self.entry.get())
            if 1024 <= nuevo_puerto <= 65535:
                guardar_puerto(nuevo_puerto)
                messagebox.showinfo("Éxito", f"Puerto {nuevo_puerto} guardado")
                self.root.destroy()
            else:
                messagebox.showwarning("Error", "El puerto debe estar entre 1024 y 65535")
        except ValueError:
            messagebox.showerror("Error", "Ingrese solo números")

"""           
if __name__ == "__main__":
    # Ejemplo de uso para probar
    print("Iniciando editor de puerto...")
    editor = PortEditor(1234)  # Puerto por defecto: 1234
    
    if editor.applied:
        new_port = editor.get_port()
        print(f"¡Puerto cambiado a: {new_port}!")
    else:
        print("No se aplicaron cambios al puerto.")
"""