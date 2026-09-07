"""Fachada del subsistema de memoria con algoritmo intercambiable."""

from __future__ import annotations

from os_simulator.memory.base import GestorMemoriaBase
from os_simulator.memory.bitmap import MemoriaBitmap
from os_simulator.memory.buddy import MemoriaBuddy
from os_simulator.memory.linked_list import MemoriaListaEnlazada


ALGORITMOS_MEMORIA = {
    "bitmap": "Mapa de bits (marcos de 64 MB)",
    "lista_enlazada": "Lista enlazada (First Fit)",
    "buddy": "Sistema de asociados (Buddy)",
}


def crear_gestor(tipo: str, capacidad_total: int) -> GestorMemoriaBase:
    gestores = {
        "bitmap": MemoriaBitmap,
        "lista_enlazada": MemoriaListaEnlazada,
        "buddy": MemoriaBuddy,
    }
    clave = tipo.lower().strip()
    if clave not in gestores:
        opciones = ", ".join(gestores)
        raise ValueError(f"Algoritmo de memoria desconocido: '{tipo}'. Opciones: {opciones}.")
    return gestores[clave](capacidad_total)


class Memoria:
    """Mantiene estable la API del Kernel y delega en el gestor seleccionado."""

    def __init__(self, capacidad_total: int = 4096, algoritmo: str = "bitmap") -> None:
        self._capacidad_total = capacidad_total
        self._gestor = crear_gestor(algoritmo, capacidad_total)

    @property
    def algoritmo(self) -> str:
        return self._gestor.clave

    @property
    def algoritmo_nombre(self) -> str:
        return self._gestor.nombre

    @property
    def capacidad_total(self) -> int:
        return self._capacidad_total

    @property
    def memoria_usada(self) -> int:
        return self._gestor.memoria_usada

    @property
    def memoria_disponible(self) -> int:
        return self._gestor.memoria_disponible

    @property
    def uso_porcentaje(self) -> float:
        return self._gestor.uso_porcentaje

    @property
    def asignaciones(self) -> dict[int, dict]:
        return self._gestor.asignaciones

    def asignar(self, pid: int, cantidad_mb: int) -> bool:
        return self._gestor.asignar(pid, cantidad_mb)

    def liberar(self, pid: int) -> int:
        return self._gestor.liberar(pid)

    def resetear(self) -> None:
        self._gestor.resetear()

    def cambiar_algoritmo(self, tipo: str) -> None:
        if self._gestor.asignaciones:
            raise RuntimeError("No se puede cambiar el algoritmo mientras haya memoria asignada.")
        self._gestor = crear_gestor(tipo, self._capacidad_total)

    def estado(self) -> dict:
        return self._gestor.estado()

    def __repr__(self) -> str:
        return (
            f"Memoria(algoritmo='{self.algoritmo}', total={self.capacidad_total}MB, "
            f"usada={self.memoria_usada}MB, disponible={self.memoria_disponible}MB)"
        )
