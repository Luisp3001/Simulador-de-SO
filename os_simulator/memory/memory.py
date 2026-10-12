"""Fachada del subsistema de memoria con algoritmo intercambiable.

La capacidad total de la RAM es una constante del sistema. La *unidad de
asignación* (tamaño del bloque en que se divide la RAM; cada casilla del mapa
de bits representa una unidad) la define el usuario y solo existe para el
mapa de bits: la lista ligada y el sistema de asociados no la usan.
"""

from __future__ import annotations

from os_simulator.memory.base import GestorMemoriaBase
from os_simulator.memory.bitmap import MemoriaBitmap
from os_simulator.memory.buddy import MemoriaBuddy
from os_simulator.memory.linked_list import MemoriaListaEnlazada


ALGORITMOS_MEMORIA = {
    "bitmap": "Mapa de bits",
    "first_fit": "Lista ligada · First Fit",
    "next_fit": "Lista ligada · Next Fit",
    "best_fit": "Lista ligada · Best Fit",
    "worst_fit": "Lista ligada · Worst Fit",
    "buddy": "Sistema de asociados (Buddy)",
}
ALGORITMOS_LISTA = ("first_fit", "next_fit", "best_fit", "worst_fit")
_ALIAS = {"lista_enlazada": "first_fit"}  # nombre usado antes del avance 3


def unidades_validas(capacidad_total: int) -> list[int]:
    """Unidades de asignación posibles: los divisores exactos de la RAM."""
    return [u for u in range(1, capacidad_total + 1) if capacidad_total % u == 0]


def validar_unidad(unidad: int, capacidad_total: int) -> None:
    if unidad <= 0:
        raise ValueError("La unidad de asignación debe ser un entero positivo.")
    if capacidad_total % unidad != 0:
        opciones = ", ".join(str(u) for u in unidades_validas(capacidad_total))
        raise ValueError(
            f"La unidad de asignación debe dividir exactamente la RAM "
            f"({capacidad_total} MB). Valores válidos: {opciones}."
        )


def crear_gestor(tipo: str, capacidad_total: int, unidad: int | None = None) -> GestorMemoriaBase:
    clave = _ALIAS.get(tipo.lower().strip(), tipo.lower().strip())
    if clave not in ALGORITMOS_MEMORIA:
        opciones = ", ".join(ALGORITMOS_MEMORIA)
        raise ValueError(f"Algoritmo de memoria desconocido: '{tipo}'. Opciones: {opciones}.")
    if unidad is not None:
        if clave != "bitmap":
            raise ValueError("La unidad de asignación solo aplica al mapa de bits.")
        validar_unidad(unidad, capacidad_total)
    if clave == "bitmap":
        return MemoriaBitmap(capacidad_total, *(() if unidad is None else (unidad,)))
    if clave == "buddy":
        return MemoriaBuddy(capacidad_total)
    return MemoriaListaEnlazada(capacidad_total, estrategia=clave)


class Memoria:
    """Mantiene estable la API del Kernel y delega en el gestor seleccionado."""

    def __init__(self, capacidad_total: int = 2048, algoritmo: str = "bitmap") -> None:
        self._capacidad_total = capacidad_total
        self._unidad: int | None = None  # None → el usuario aún no la define
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
    def gestor(self) -> GestorMemoriaBase:
        return self._gestor

    @property
    def requiere_unidad(self) -> bool:
        """Solo el mapa de bits necesita que el usuario defina la unidad."""
        return self.algoritmo == "bitmap"

    @property
    def listo(self) -> bool:
        return (not self.requiere_unidad) or self._unidad is not None

    @property
    def unidad_definida(self) -> bool:
        return self._unidad is not None

    @property
    def unidad_asignacion(self) -> int | None:
        return self._unidad

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

    def configurar_unidad(self, unidad: int) -> None:
        """Define (o cambia) la unidad de asignación. Deja la memoria en ceros."""
        if not self.requiere_unidad:
            raise ValueError("La unidad de asignación solo aplica al mapa de bits.")
        if self._gestor.asignaciones:
            raise RuntimeError(
                "No se puede cambiar la unidad de asignación mientras haya procesos en memoria."
            )
        self._gestor = crear_gestor(self.algoritmo, self._capacidad_total, unidad)
        self._unidad = unidad

    def olvidar_unidad(self) -> None:
        """Vuelve al estado inicial: sin unidad definida y memoria vacía."""
        self._gestor = crear_gestor(self.algoritmo, self._capacidad_total)
        self._unidad = None

    def cambiar_algoritmo(self, tipo: str) -> None:
        if self._gestor.asignaciones:
            raise RuntimeError("No se puede cambiar el algoritmo mientras haya memoria asignada.")
        es_bitmap = _ALIAS.get(tipo.lower().strip(), tipo.lower().strip()) == "bitmap"
        self._gestor = crear_gestor(tipo, self._capacidad_total, self._unidad if es_bitmap else None)

    def estado(self) -> dict:
        datos = self._gestor.estado()
        datos["unidad_definida"] = self.unidad_definida
        return datos

    def __repr__(self) -> str:
        return (
            f"Memoria(algoritmo='{self.algoritmo}', total={self.capacidad_total}MB, "
            f"usada={self.memoria_usada}MB, disponible={self.memoria_disponible}MB)"
        )
