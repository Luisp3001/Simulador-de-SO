"""
filesystem/continua.py
=======================
Algoritmo 1 — Asignación continua (contigua).

Cada archivo debe ocupar una secuencia de bloques físicamente consecutivos
en el disco. Para crear un archivo se recorre el disco de izquierda a
derecha buscando la primera racha de bloques libres consecutivos que
alcance el tamaño solicitado (equivalente a un First Fit sobre el arreglo
de bloques, igual que ``memory/bitmap.py`` busca ceros consecutivos en el
mapa de bits).

Si no existe un hueco contiguo suficientemente grande la asignación se
RECHAZA, aunque la suma de bloques libres sueltos alcance el tamaño
pedido: la asignación continua exige contigüidad, no solo cantidad.

Por archivo solo se guardan dos números —bloque inicial y longitud—: con
ellos basta para reconstruir qué bloques ocupa
(bloque_inicio .. bloque_inicio + longitud - 1).
"""

from __future__ import annotations

from typing import Optional

from os_simulator.filesystem.base import GestorArchivosBase


class DiscoAsignacionContinua(GestorArchivosBase):
    clave = "continua"
    nombre = "Asignación continua"

    def __init__(self, total_bloques: int) -> None:
        super().__init__(total_bloques)
        # Dueño de cada bloque: None si está libre, o el nombre del archivo.
        self._bloques: list[Optional[str]] = [None] * total_bloques
        self._archivos: dict[str, dict] = {}

    # ── Propiedades ──────────────────────────────────────────────────────
    @property
    def bloques_usados(self) -> int:
        return sum(1 for dueño in self._bloques if dueño is not None)

    @property
    def archivos(self) -> dict[str, dict]:
        return {
            nombre: {**datos, "bloques": list(datos["bloques"])}
            for nombre, datos in self._archivos.items()
        }

    # ── Búsqueda de espacio contiguo ─────────────────────────────────────
    def _buscar_hueco_contiguo(self, necesarios: int) -> Optional[int]:
        """Índice de inicio de la primera racha de ``necesarios`` bloques libres."""
        racha = 0
        for i, dueño in enumerate(self._bloques):
            racha = racha + 1 if dueño is None else 0
            if racha == necesarios:
                return i - necesarios + 1
        return None

    # ── Operaciones del menú ─────────────────────────────────────────────
    def crear_archivo(self, nombre: str, tamaño_bloques: int) -> dict:
        if tamaño_bloques <= 0:
            raise ValueError("El tamaño debe ser mayor a 0 bloques.")
        self._validar_nombre_nuevo(nombre)
        if tamaño_bloques > self.total_bloques:
            raise RuntimeError(
                f"'{nombre}' necesita {tamaño_bloques} bloques; "
                f"el disco solo tiene {self.total_bloques}."
            )

        inicio = self._buscar_hueco_contiguo(tamaño_bloques)
        if inicio is None:
            raise RuntimeError(
                f"No hay espacio contiguo suficiente para '{nombre}' "
                f"({tamaño_bloques} bloques). Bloques libres: "
                f"{self.bloques_disponibles}, pero el hueco contiguo más "
                f"grande es de {self.mayor_hueco_libre()} bloques."
            )

        bloques = list(range(inicio, inicio + tamaño_bloques))
        for i in bloques:
            self._bloques[i] = nombre
        self._archivos[nombre] = {
            "bloque_inicio": inicio,
            "longitud": tamaño_bloques,
            "bloques": bloques,
        }
        return self.consultar_archivo(nombre)

    def consultar_archivo(self, nombre: str) -> dict:
        datos = self._obtener_o_fallar(nombre)
        inicio = datos["bloque_inicio"]
        longitud = datos["longitud"]
        return {
            **datos,
            "estructura": {
                "metodo": "asignacion_continua",
                "descripcion": (
                    "Se registra el bloque inicial y la longitud; "
                    "el archivo ocupa esa secuencia consecutiva."
                ),
                "bloque_inicial": inicio,
                "longitud": longitud,
                "bloque_final": inicio + longitud - 1,
                "bloques": list(datos["bloques"]),
            },
        }

    def eliminar_archivo(self, nombre: str) -> dict:
        datos = self._obtener_o_fallar(nombre)
        for i in datos["bloques"]:
            self._bloques[i] = None
        del self._archivos[nombre]
        return datos

    def resetear(self) -> None:
        self._bloques = [None] * self.total_bloques
        self._archivos.clear()

    def bloques(self) -> list[dict]:
        return [
            {"indice": i, "libre": dueño is None, "archivo": dueño}
            for i, dueño in enumerate(self._bloques)
        ]
