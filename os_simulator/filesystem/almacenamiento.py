"""Fábrica de los algoritmos de administración de archivos (disco).

Mismo patrón que ``memory/memory.py``: un diccionario con los algoritmos
del informe y una función ``crear_gestor`` que instancia el gestor
correspondiente. Avance 5 solo implementa el Algoritmo 1 (asignación
continua); los Algoritmos 2 y 3 ya están anunciados en ``ALGORITMOS_ARCHIVOS``
para que el frontend los liste, pero ``crear_gestor`` lanza
``NotImplementedError`` hasta que se desarrollen en un avance posterior.
"""

from __future__ import annotations

from os_simulator.filesystem.base import GestorArchivosBase
from os_simulator.filesystem.continua import DiscoAsignacionContinua

ALGORITMOS_ARCHIVOS = {
    "continua": "Algoritmo 1 · Asignación continua",
    "enlazada": "Algoritmo 2 · Asignación mediante lista ligada",
    "inodos":   "Algoritmo 3 · Asignación mediante i-nodos",
}

# Claves que ya tienen un gestor implementado. Las demás existen en el menú
# (para reflejar el enunciado completo) pero aún no se pueden seleccionar.
ALGORITMOS_DISPONIBLES = ("continua",)


def crear_gestor(tipo: str, total_bloques: int) -> GestorArchivosBase:
    clave = tipo.lower().strip()
    if clave not in ALGORITMOS_ARCHIVOS:
        opciones = ", ".join(ALGORITMOS_ARCHIVOS)
        raise ValueError(f"Algoritmo de archivos desconocido: '{tipo}'. Opciones: {opciones}.")
    if clave == "continua":
        return DiscoAsignacionContinua(total_bloques)
    raise NotImplementedError(
        f"'{ALGORITMOS_ARCHIVOS[clave]}' todavía no está implementado — próximo avance."
    )
