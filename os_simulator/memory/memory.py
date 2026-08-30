"""
memory/memory.py
================
Módulo que modela el subsistema de Memoria del sistema operativo.

Gestiona la asignación y liberación de bloques de memoria RAM
para los procesos del sistema.

Principios OOP aplicados:
    - Encapsulamiento: estado interno protegido.
    - Responsabilidad única: solo gestiona la memoria.
"""

from __future__ import annotations
from typing import Optional


class BloqueMemoria:
    """
    Representa un bloque contiguo de memoria RAM.

    Attributes:
        inicio (int): Dirección de inicio del bloque en MB.
        tamaño (int): Tamaño del bloque en MB.
        pid_propietario (Optional[int]): PID del proceso dueño, o None si libre.
    """

    def __init__(self, inicio: int, tamaño: int) -> None:
        self.inicio: int = inicio
        self.tamaño: int = tamaño
        self.pid_propietario: Optional[int] = None

    @property
    def libre(self) -> bool:
        """Indica si el bloque está disponible."""
        return self.pid_propietario is None

    def __repr__(self) -> str:
        estado = "libre" if self.libre else f"PID={self.pid_propietario}"
        return f"BloqueMemoria(inicio={self.inicio}MB, tamaño={self.tamaño}MB, {estado})"


class Memoria:
    """
    Subsistema de Memoria RAM del sistema operativo.

    Implementa un gestor de memoria por bloques simples (First-Fit).
    En futuras iteraciones se puede extender a paginación o segmentación.

    Attributes:
        capacidad_total (int): Capacidad total de RAM en MB.
    """

    def __init__(self, capacidad_total: int = 4096) -> None:
        self._capacidad_total: int = capacidad_total
        self._memoria_usada: int = 0
        # Registro de asignaciones: pid → MB asignados
        self._asignaciones: dict[int, int] = {}

    # ── Propiedades ──────────────────────────────────────────────────────

    @property
    def capacidad_total(self) -> int:
        """Capacidad total de RAM en MB."""
        return self._capacidad_total

    @property
    def memoria_usada(self) -> int:
        """Memoria actualmente en uso en MB."""
        return self._memoria_usada

    @property
    def memoria_disponible(self) -> int:
        """Memoria libre disponible en MB."""
        return self._capacidad_total - self._memoria_usada

    @property
    def uso_porcentaje(self) -> float:
        """Porcentaje de uso de memoria (0.0 – 100.0)."""
        if self._capacidad_total == 0:
            return 0.0
        return (self._memoria_usada / self._capacidad_total) * 100.0

    @property
    def asignaciones(self) -> dict[int, int]:
        """Mapa de PID → MB asignados (solo lectura)."""
        return dict(self._asignaciones)

    # ── Operaciones ──────────────────────────────────────────────────────

    def asignar(self, pid: int, cantidad_mb: int) -> bool:
        """
        Asigna memoria a un proceso.

        Args:
            pid: Identificador del proceso solicitante.
            cantidad_mb: Cantidad de memoria requerida en MB.

        Returns:
            True si la asignación fue exitosa, False si no hay suficiente memoria.
        """
        if cantidad_mb <= 0:
            raise ValueError("La cantidad de memoria debe ser positiva.")
        if pid in self._asignaciones:
            raise RuntimeError(f"El PID {pid} ya tiene memoria asignada.")
        if cantidad_mb > self.memoria_disponible:
            return False   # Memoria insuficiente

        self._asignaciones[pid] = cantidad_mb
        self._memoria_usada += cantidad_mb
        return True

    def liberar(self, pid: int) -> int:
        """
        Libera la memoria asignada a un proceso.

        Args:
            pid: Identificador del proceso cuya memoria se libera.

        Returns:
            La cantidad de MB liberados (0 si el PID no tenía asignación).
        """
        if pid not in self._asignaciones:
            return 0
        mb_liberados = self._asignaciones.pop(pid)
        self._memoria_usada -= mb_liberados
        return mb_liberados

    def resetear(self) -> None:
        """Libera toda la memoria (equivale a un reinicio del sistema)."""
        self._asignaciones.clear()
        self._memoria_usada = 0

    # ── Representación ───────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"Memoria(total={self._capacidad_total}MB, "
            f"usada={self._memoria_usada}MB, "
            f"disponible={self.memoria_disponible}MB, "
            f"uso={self.uso_porcentaje:.1f}%)"
        )
