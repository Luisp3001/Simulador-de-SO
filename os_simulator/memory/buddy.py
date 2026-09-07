"""Asignador de memoria mediante el sistema de asociados (Buddy System)."""

from __future__ import annotations

from math import ceil, log2

from os_simulator.memory.base import GestorMemoriaBase


class MemoriaBuddy(GestorMemoriaBase):
    clave = "buddy"
    nombre = "Sistema de asociados (Buddy)"

    def __init__(self, capacidad_total: int, bloque_minimo: int = 64) -> None:
        super().__init__(capacidad_total)
        if capacidad_total & (capacidad_total - 1):
            raise ValueError("Buddy System requiere una capacidad potencia de dos.")
        if bloque_minimo <= 0 or bloque_minimo & (bloque_minimo - 1):
            raise ValueError("El bloque mínimo debe ser una potencia de dos.")
        if bloque_minimo > capacidad_total:
            raise ValueError("El bloque mínimo no puede superar la capacidad.")
        self.bloque_minimo = bloque_minimo
        self._tamaños = [
            2**orden
            for orden in range(
                int(log2(bloque_minimo)), int(log2(capacidad_total)) + 1
            )
        ]
        self._libres: dict[int, set[int]] = {tamaño: set() for tamaño in self._tamaños}
        self._libres[capacidad_total].add(0)
        self._asignaciones: dict[int, dict] = {}

    @property
    def memoria_usada(self) -> int:
        return sum(datos["reservada_mb"] for datos in self._asignaciones.values())

    @property
    def asignaciones(self) -> dict[int, dict]:
        return {pid: dict(datos) for pid, datos in self._asignaciones.items()}

    def _tamaño_requerido(self, cantidad_mb: int) -> int:
        return max(self.bloque_minimo, 2 ** ceil(log2(cantidad_mb)))

    def asignar(self, pid: int, cantidad_mb: int) -> bool:
        self._validar_solicitud(pid, cantidad_mb)
        requerido = self._tamaño_requerido(cantidad_mb)
        if requerido > self.capacidad_total:
            return False
        disponible = next(
            (t for t in self._tamaños if t >= requerido and self._libres[t]),
            None,
        )
        if disponible is None:
            return False
        inicio = min(self._libres[disponible])
        self._libres[disponible].remove(inicio)
        while disponible > requerido:
            disponible //= 2
            self._libres[disponible].add(inicio + disponible)
        self._asignaciones[pid] = {
            "solicitada_mb": cantidad_mb,
            "reservada_mb": requerido,
            "inicio": inicio,
        }
        return True

    def liberar(self, pid: int) -> int:
        datos = self._asignaciones.pop(pid, None)
        if datos is None:
            return 0
        inicio = datos["inicio"]
        tamaño = datos["reservada_mb"]
        while tamaño < self.capacidad_total:
            asociado = inicio ^ tamaño
            if asociado not in self._libres[tamaño]:
                break
            self._libres[tamaño].remove(asociado)
            inicio = min(inicio, asociado)
            tamaño *= 2
        self._libres[tamaño].add(inicio)
        return datos["solicitada_mb"]

    def resetear(self) -> None:
        self._libres = {tamaño: set() for tamaño in self._tamaños}
        self._libres[self.capacidad_total].add(0)
        self._asignaciones.clear()

    def bloques(self) -> list[dict]:
        resultado = []
        for tamaño, inicios in self._libres.items():
            for inicio in inicios:
                resultado.append(
                    {"inicio": inicio, "tamaño": tamaño, "libre": True, "pid": None}
                )
        for pid, datos in self._asignaciones.items():
            resultado.append({
                "inicio": datos["inicio"],
                "tamaño": datos["reservada_mb"],
                "libre": False,
                "pid": pid,
            })
        return sorted(resultado, key=lambda bloque: bloque["inicio"])

    def mayor_hueco_libre(self) -> int:
        return max((tamaño for tamaño, inicios in self._libres.items() if inicios), default=0)
