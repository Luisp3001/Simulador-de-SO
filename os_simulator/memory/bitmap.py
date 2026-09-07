"""Asignación paginada mediante un mapa de bits."""

from __future__ import annotations

from math import ceil

from os_simulator.memory.base import GestorMemoriaBase


class MemoriaBitmap(GestorMemoriaBase):
    clave = "bitmap"
    nombre = "Mapa de bits"
    tipo_vista = "celdas"

    def __init__(self, capacidad_total: int, tamaño_marco: int = 64) -> None:
        super().__init__(capacidad_total)
        if tamaño_marco <= 0 or capacidad_total % tamaño_marco != 0:
            raise ValueError("La RAM debe ser divisible entre el tamaño de marco.")
        self.tamaño_marco = tamaño_marco
        self._mapa: list[int | None] = [None] * (capacidad_total // tamaño_marco)
        self._asignaciones: dict[int, dict] = {}

    @property
    def memoria_usada(self) -> int:
        return sum(1 for pid in self._mapa if pid is not None) * self.tamaño_marco

    @property
    def asignaciones(self) -> dict[int, dict]:
        return {pid: {**datos, "marcos": list(datos["marcos"])} for pid, datos in self._asignaciones.items()}

    def asignar(self, pid: int, cantidad_mb: int) -> bool:
        self._validar_solicitud(pid, cantidad_mb)
        necesarios = ceil(cantidad_mb / self.tamaño_marco)
        libres = [i for i, dueño in enumerate(self._mapa) if dueño is None]
        if len(libres) < necesarios:
            return False
        marcos = libres[:necesarios]
        for indice in marcos:
            self._mapa[indice] = pid
        self._asignaciones[pid] = {
            "solicitada_mb": cantidad_mb,
            "reservada_mb": necesarios * self.tamaño_marco,
            "marcos": marcos,
        }
        return True

    def liberar(self, pid: int) -> int:
        datos = self._asignaciones.pop(pid, None)
        if datos is None:
            return 0
        for indice in datos["marcos"]:
            self._mapa[indice] = None
        return datos["solicitada_mb"]

    def resetear(self) -> None:
        self._mapa = [None] * len(self._mapa)
        self._asignaciones.clear()

    def bloques(self) -> list[dict]:
        return [
            {"inicio": i * self.tamaño_marco, "tamaño": self.tamaño_marco,
             "libre": pid is None, "pid": pid}
            for i, pid in enumerate(self._mapa)
        ]

    def mayor_hueco_libre(self) -> int:
        # La paginación puede satisfacer una petición usando marcos no contiguos.
        return sum(1 for pid in self._mapa if pid is None) * self.tamaño_marco
