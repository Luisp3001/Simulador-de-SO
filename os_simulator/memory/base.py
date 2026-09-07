"""Contratos y utilidades compartidas por los gestores de memoria."""

from __future__ import annotations

from abc import ABC, abstractmethod


class GestorMemoriaBase(ABC):
    """Interfaz común para los algoritmos de asignación de RAM."""

    clave = "base"
    nombre = "Gestor base"
    tipo_vista = "segmentos"

    def __init__(self, capacidad_total: int) -> None:
        if capacidad_total <= 0:
            raise ValueError("La capacidad de memoria debe ser positiva.")
        self._capacidad_total = capacidad_total

    @property
    def capacidad_total(self) -> int:
        return self._capacidad_total

    @property
    @abstractmethod
    def memoria_usada(self) -> int:
        """Memoria realmente reservada, incluida la fragmentación interna."""

    @property
    def memoria_disponible(self) -> int:
        return self.capacidad_total - self.memoria_usada

    @property
    def uso_porcentaje(self) -> float:
        return (self.memoria_usada / self.capacidad_total) * 100

    @property
    @abstractmethod
    def asignaciones(self) -> dict[int, dict]:
        """Copia de las asignaciones indexadas por PID."""

    @abstractmethod
    def asignar(self, pid: int, cantidad_mb: int) -> bool:
        pass

    @abstractmethod
    def liberar(self, pid: int) -> int:
        """Libera un PID y devuelve los MB solicitados por él."""

    @abstractmethod
    def resetear(self) -> None:
        pass

    @abstractmethod
    def bloques(self) -> list[dict]:
        """Representación física serializable de la memoria."""

    @abstractmethod
    def mayor_hueco_libre(self) -> int:
        pass

    def _validar_solicitud(self, pid: int, cantidad_mb: int) -> None:
        if cantidad_mb <= 0:
            raise ValueError("La cantidad de memoria debe ser positiva.")
        if pid in self.asignaciones:
            raise RuntimeError(f"El PID {pid} ya tiene memoria asignada.")

    def estado(self) -> dict:
        asignaciones = self.asignaciones
        solicitada = sum(a["solicitada_mb"] for a in asignaciones.values())
        reservada = self.memoria_usada
        mayor_hueco = self.mayor_hueco_libre()
        return {
            "algoritmo": self.clave,
            "algoritmo_nombre": self.nombre,
            "tipo_vista": self.tipo_vista,
            "total_mb": self.capacidad_total,
            "solicitada_mb": solicitada,
            "reservada_mb": reservada,
            "usada_mb": reservada,
            "disponible_mb": self.memoria_disponible,
            "uso_pct": round(self.uso_porcentaje, 2),
            "fragmentacion_interna_mb": reservada - solicitada,
            "fragmentacion_externa_mb": max(0, self.memoria_disponible - mayor_hueco),
            "mayor_hueco_libre_mb": mayor_hueco,
            "bloques": self.bloques(),
            "asignaciones": asignaciones,
        }
