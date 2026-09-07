"""Particiones variables administradas mediante una lista enlazada."""

from __future__ import annotations

from dataclasses import dataclass

from os_simulator.memory.base import GestorMemoriaBase


@dataclass
class NodoMemoria:
    inicio: int
    tamaño: int
    pid: int | None = None
    siguiente: "NodoMemoria | None" = None

    @property
    def libre(self) -> bool:
        return self.pid is None


class MemoriaListaEnlazada(GestorMemoriaBase):
    clave = "lista_enlazada"
    nombre = "Lista enlazada (First Fit)"

    def __init__(self, capacidad_total: int) -> None:
        super().__init__(capacidad_total)
        self._cabeza = NodoMemoria(0, capacidad_total)
        self._asignaciones: dict[int, dict] = {}

    def _iterar(self):
        actual = self._cabeza
        while actual is not None:
            yield actual
            actual = actual.siguiente

    @property
    def memoria_usada(self) -> int:
        return sum(nodo.tamaño for nodo in self._iterar() if not nodo.libre)

    @property
    def asignaciones(self) -> dict[int, dict]:
        return {pid: dict(datos) for pid, datos in self._asignaciones.items()}

    def asignar(self, pid: int, cantidad_mb: int) -> bool:
        self._validar_solicitud(pid, cantidad_mb)
        for nodo in self._iterar():
            if nodo.libre and nodo.tamaño >= cantidad_mb:
                if nodo.tamaño > cantidad_mb:
                    nodo.siguiente = NodoMemoria(
                        nodo.inicio + cantidad_mb,
                        nodo.tamaño - cantidad_mb,
                        siguiente=nodo.siguiente,
                    )
                nodo.tamaño = cantidad_mb
                nodo.pid = pid
                self._asignaciones[pid] = {
                    "solicitada_mb": cantidad_mb,
                    "reservada_mb": cantidad_mb,
                    "inicio": nodo.inicio,
                }
                return True
        return False

    def liberar(self, pid: int) -> int:
        datos = self._asignaciones.pop(pid, None)
        if datos is None:
            return 0
        for nodo in self._iterar():
            if nodo.pid == pid:
                nodo.pid = None
                break
        self._fusionar_libres()
        return datos["solicitada_mb"]

    def _fusionar_libres(self) -> None:
        actual = self._cabeza
        while actual.siguiente is not None:
            if actual.libre and actual.siguiente.libre:
                actual.tamaño += actual.siguiente.tamaño
                actual.siguiente = actual.siguiente.siguiente
            else:
                actual = actual.siguiente

    def resetear(self) -> None:
        self._cabeza = NodoMemoria(0, self.capacidad_total)
        self._asignaciones.clear()

    def bloques(self) -> list[dict]:
        return [
            {"inicio": n.inicio, "tamaño": n.tamaño, "libre": n.libre, "pid": n.pid}
            for n in self._iterar()
        ]

    def mayor_hueco_libre(self) -> int:
        return max((n.tamaño for n in self._iterar() if n.libre), default=0)
