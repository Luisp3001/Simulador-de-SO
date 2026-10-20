"""Contratos compartidos por los algoritmos de administración de archivos.

Modela un disco dividido en bloques de tamaño fijo, numerados de 0 a
``total_bloques - 1``. Cada algoritmo concreto (asignación continua, lista
ligada, i-nodos) decide *cómo* relacionar un archivo con los bloques que
ocupa, pero todos comparten la misma interfaz pública: crear, consultar,
eliminar y mostrar el estado del disco. Así el servidor y el frontend no
necesitan saber qué algoritmo está activo para dibujar la malla de bloques
o la tabla de archivos (patrón Strategy, igual que ``memory/base.py``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class GestorArchivosBase(ABC):
    """Interfaz común para los algoritmos de asignación de espacio en disco."""

    clave = "base"
    nombre = "Gestor base"

    def __init__(self, total_bloques: int) -> None:
        if total_bloques <= 0:
            raise ValueError("El disco debe tener al menos 1 bloque.")
        self._total_bloques = total_bloques

    # ── Propiedades comunes ──────────────────────────────────────────────
    @property
    def total_bloques(self) -> int:
        return self._total_bloques

    @property
    @abstractmethod
    def bloques_usados(self) -> int:
        """Cantidad de bloques actualmente ocupados por algún archivo."""

    @property
    def bloques_disponibles(self) -> int:
        return self.total_bloques - self.bloques_usados

    @property
    @abstractmethod
    def archivos(self) -> dict[str, dict]:
        """Copia de los archivos almacenados, indexados por nombre."""

    # ── Operaciones del menú (crear / consultar / eliminar) ─────────────
    @abstractmethod
    def crear_archivo(self, nombre: str, tamaño_bloques: int) -> dict:
        """Crea un archivo reservando ``tamaño_bloques`` bloques de disco.

        Raises:
            FileExistsError: Si ya existe un archivo con ese nombre.
            RuntimeError: Si no hay espacio suficiente para almacenarlo.
        """

    @abstractmethod
    def consultar_archivo(self, nombre: str) -> dict:
        """Devuelve la ubicación en disco de un archivo.

        Raises:
            FileNotFoundError: Si el archivo no existe.
        """

    @abstractmethod
    def eliminar_archivo(self, nombre: str) -> dict:
        """Elimina un archivo y libera sus bloques.

        Raises:
            FileNotFoundError: Si el archivo no existe.
        """

    @abstractmethod
    def resetear(self) -> None:
        """Vacía el disco por completo."""

    @abstractmethod
    def bloques(self) -> list[dict]:
        """Representación física serializable del disco, bloque por bloque."""

    # ── Helpers compartidos por las subclases ────────────────────────────
    def _validar_nombre_nuevo(self, nombre: str) -> None:
        if not nombre:
            raise ValueError("El nombre del archivo no puede estar vacío.")
        if nombre in self.archivos:
            raise FileExistsError(f"Ya existe un archivo llamado '{nombre}'.")

    def _obtener_o_fallar(self, nombre: str) -> dict:
        datos = self.archivos.get(nombre)
        if datos is None:
            raise FileNotFoundError(f"El archivo '{nombre}' no existe.")
        return datos

    def bloques_libres(self) -> list[int]:
        """Índices de los bloques que todavía no tienen dueño."""
        return [b["indice"] for b in self.bloques() if b["libre"]]

    def huecos_libres(self) -> list[dict]:
        """Secuencias consecutivas de bloques libres (inicio + longitud)."""
        huecos: list[dict] = []
        inicio: int | None = None
        longitud = 0
        for b in self.bloques():
            if b["libre"]:
                if inicio is None:
                    inicio = b["indice"]
                    longitud = 1
                else:
                    longitud += 1
            elif inicio is not None:
                huecos.append({"inicio": inicio, "longitud": longitud})
                inicio = None
                longitud = 0
        if inicio is not None:
            huecos.append({"inicio": inicio, "longitud": longitud})
        return huecos

    def mayor_hueco_libre(self) -> int:
        """Racha más larga de bloques libres consecutivos (en bloques)."""
        huecos = self.huecos_libres()
        return max((h["longitud"] for h in huecos), default=0)

    # ── Estado para la API / frontend ────────────────────────────────────
    def estado(self) -> dict:
        return {
            "algoritmo": self.clave,
            "algoritmo_nombre": self.nombre,
            "total_bloques": self.total_bloques,
            "bloques_usados": self.bloques_usados,
            "bloques_disponibles": self.bloques_disponibles,
            "bloques_libres": self.bloques_libres(),
            "huecos_libres": self.huecos_libres(),
            "mayor_hueco_libre": self.mayor_hueco_libre(),
            "bloques": self.bloques(),
            "archivos": self.archivos,
        }

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(total={self.total_bloques}, "
            f"usados={self.bloques_usados}, archivos={len(self.archivos)})"
        )
