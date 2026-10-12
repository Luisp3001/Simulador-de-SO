"""Administración de memoria mediante un mapa de bits.

La RAM (constante) se divide en *unidades de asignación* de tamaño fijo.
Cada unidad se representa con un bit del mapa:

    0 → unidad libre
    1 → unidad ocupada por algún proceso

Fórmulas:
    tamaño de la malla   = RAM / unidad de asignación         (nº de bits)
    unidades por proceso = ⌈tamaño del proceso / unidad⌉      (nº de bits en 1)

Para asignar un proceso se busca la primera secuencia de ``k`` bits en 0
consecutivos (First Fit sobre el mapa) y se ponen en 1.
"""

from __future__ import annotations

from math import ceil

from os_simulator.memory.base import GestorMemoriaBase

UNIDAD_POR_DEFECTO = 64


class MemoriaBitmap(GestorMemoriaBase):
    clave = "bitmap"
    nombre = "Mapa de bits"
    tipo_vista = "celdas"

    def __init__(self, capacidad_total: int, unidad: int = UNIDAD_POR_DEFECTO) -> None:
        super().__init__(capacidad_total)
        if unidad <= 0 or capacidad_total % unidad != 0:
            raise ValueError("La RAM debe ser divisible entre la unidad de asignación.")
        self.unidad = unidad
        # Se guarda el dueño de cada unidad; el mapa de bits (0/1) se deriva de él.
        self._mapa: list[int | None] = [None] * (capacidad_total // unidad)
        self._asignaciones: dict[int, dict] = {}

    # Alias por compatibilidad con la versión anterior (tamaño de marco).
    @property
    def tamaño_marco(self) -> int:
        return self.unidad

    @property
    def total_unidades(self) -> int:
        return len(self._mapa)

    @property
    def mapa_bits(self) -> list[int]:
        return [0 if dueño is None else 1 for dueño in self._mapa]

    @property
    def memoria_usada(self) -> int:
        return sum(1 for pid in self._mapa if pid is not None) * self.unidad

    @property
    def asignaciones(self) -> dict[int, dict]:
        return {pid: {**datos, "marcos": list(datos["marcos"])} for pid, datos in self._asignaciones.items()}

    def unidades_necesarias(self, cantidad_mb: int) -> int:
        return ceil(cantidad_mb / self.unidad)

    def _buscar_hueco(self, necesarias: int) -> int | None:
        """Índice de la primera secuencia de ``necesarias`` ceros consecutivos."""
        racha = 0
        for i, dueño in enumerate(self._mapa):
            racha = racha + 1 if dueño is None else 0
            if racha == necesarias:
                return i - necesarias + 1
        return None

    def asignar(self, pid: int, cantidad_mb: int) -> bool:
        self._validar_solicitud(pid, cantidad_mb)
        necesarias = self.unidades_necesarias(cantidad_mb)
        inicio = self._buscar_hueco(necesarias)
        if inicio is None:
            return False
        marcos = list(range(inicio, inicio + necesarias))
        for indice in marcos:
            self._mapa[indice] = pid
        self._asignaciones[pid] = {
            "solicitada_mb": cantidad_mb,
            "reservada_mb": necesarias * self.unidad,
            "unidades": necesarias,
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
            {"inicio": i * self.unidad, "tamaño": self.unidad,
             "libre": pid is None, "pid": pid, "bit": 0 if pid is None else 1}
            for i, pid in enumerate(self._mapa)
        ]

    def mayor_hueco_libre(self) -> int:
        """Racha más larga de ceros consecutivos (en MB)."""
        mejor = racha = 0
        for dueño in self._mapa:
            racha = racha + 1 if dueño is None else 0
            mejor = max(mejor, racha)
        return mejor * self.unidad

    def estado(self) -> dict:
        datos = super().estado()
        datos.update({
            "unidad_mb": self.unidad,
            "total_unidades": self.total_unidades,
            "mapa_bits": self.mapa_bits,
        })
        return datos
