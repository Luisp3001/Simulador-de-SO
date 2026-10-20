"""Submódulo filesystem: árbol de archivos/directorios y asignación de disco."""
from os_simulator.filesystem.filesystem import SistemaArchivos, Archivo, Directorio
from os_simulator.filesystem.base import GestorArchivosBase
from os_simulator.filesystem.continua import DiscoAsignacionContinua
from os_simulator.filesystem.almacenamiento import (
    ALGORITMOS_ARCHIVOS,
    ALGORITMOS_DISPONIBLES,
    crear_gestor,
)

__all__ = [
    "SistemaArchivos", "Archivo", "Directorio",
    "GestorArchivosBase", "DiscoAsignacionContinua",
    "ALGORITMOS_ARCHIVOS", "ALGORITMOS_DISPONIBLES", "crear_gestor",
]
