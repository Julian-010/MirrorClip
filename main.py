"""
Main file for application
"""

import requests # type: ignore #Permite hacer peticiones HTTP de forma sencilla (GET, POST, etc.).
import time #Proporciona funciones para trabajar con el tiempo
import win32clipboard as clipboard # type: ignore #Permite interactuar con el portapapeles de Windows
import sys #Proporciona acceso a variables y funciones del intérprete de Python
import os #Permite interactuar con el sistema operativo
import pickle #Sirve para serializar y deserializar objetos de Python (guardar o cargar estructuras en archivos, por ejemplo).
from socket import gethostbyname, gethostname, gaierror #Funciones para obtener información de red como el nombre o IP del host
from threading import Thread # Permite ejecutar tareas en paralelo usando hilos.
from multiprocessing import freeze_support, Value, Process #Se usan para paralelizar tareas
from multiprocessing.managers import BaseManager #Permite compartir objetos complejos entre procesos a través de proxies.
from enum import Enum #Permite definir enumeraciones
from pystray import Icon, Menu, MenuItem # type: ignore #Permite crear iconos de bandeja del sistema con menús contextuales
from PIL import Image #Parte de la biblioteca Pillow, se usa para manipular imágenes
from io import BytesIO #Crea un buffer en memoria que actúa como archivo para leer/escribir bytes.
# from server import run_server
# from device_list import DeviceList
# from port_editor import PortEditor