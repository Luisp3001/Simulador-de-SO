"""
core/cpu.py
===========
Módulo que modela la Unidad de Procesamiento Central (CPU).

La CPU es responsable de ejecutar los procesos que le asigna
el Kernel. Mantiene el registro del proceso en ejecución y
simula ciclos de reloj.

Principios OOP aplicados:
    - Encapsulamiento: solo el Kernel puede despachar/detener procesos.
    - Abstracción: oculta los detalles de ejecución de ciclos.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    # Importación de tipo para evitar ciclos en runtime
    from os_simulator.processes.process import Proceso


class CPU:
    """
    Unidad Central de Procesamiento del sistema operativo simulado.

    Ejecuta procesos de uno en uno (monoprocesador).
    En futuras versiones puede extenderse a múltiples núcleos.

    Attributes:
        velocidad_mhz (int): Velocidad del procesador en MHz (informativo).
    """

    def __init__(self, velocidad_mhz: int = 3200) -> None:
        self._velocidad_mhz: int = velocidad_mhz
        self._proceso_actual: Optional[Proceso] = None
        self._ciclos_totales: int = 0
        self._uso_porcentaje: float = 0.0

    # ── Propiedades ──────────────────────────────────────────────────────

    @property
    def velocidad_mhz(self) -> int:
        return self._velocidad_mhz

    @property
    def proceso_actual(self) -> Optional[Proceso]:
        """El proceso que se está ejecutando actualmente, o None si está libre."""
        return self._proceso_actual

    @property
    def esta_libre(self) -> bool:
        """Indica si la CPU no tiene ningún proceso en ejecución."""
        return self._proceso_actual is None

    @property
    def ciclos_totales(self) -> int:
        """Total de ciclos de reloj ejecutados desde el arranque."""
        return self._ciclos_totales

    @property
    def uso_porcentaje(self) -> float:
        """Porcentaje de uso de CPU para el proceso actual (0.0 – 100.0)."""
        return self._uso_porcentaje

    # ── Operaciones ──────────────────────────────────────────────────────

    def despachar(self, proceso: Proceso, uso: float = 50.0) -> None:
        """
        Asigna un proceso a la CPU para su ejecución.

        Args:
            proceso: El proceso que tomará control de la CPU.
            uso: Porcentaje de uso de CPU simulado (0.0 – 100.0).

        Raises:
            RuntimeError: Si la CPU ya está ocupada.
        """
        if not self.esta_libre:
            raise RuntimeError(
                f"La CPU está ocupada ejecutando '{self._proceso_actual.nombre}'."
            )
        self._proceso_actual = proceso
        self._uso_porcentaje = max(0.0, min(100.0, uso))
        proceso.despachar()

    def ejecutar_ciclo(self) -> bool:
        """
        Avanza un ciclo de reloj en el proceso actual.

        Returns:
            True si el proceso completó su ejecución en este ciclo.
            False si el proceso continúa o la CPU estaba libre.
        """
        if self.esta_libre:
            return False

        self._ciclos_totales += 1
        self._proceso_actual.ejecutar_ciclo()

        if self._proceso_actual.completado:
            self._liberar()
            return True
        return False

    def interrumpir(self) -> None:
        """
        Retira el proceso actual de la CPU sin terminarlo (preempción).
        El proceso vuelve al estado LISTO.
        """
        if self.esta_libre:
            return
        from os_simulator.processes.process import EstadoProceso
        self._proceso_actual._estado = EstadoProceso.LISTO
        self._liberar()

    def _liberar(self) -> None:
        """Limpia el estado interno de la CPU (privado)."""
        self._proceso_actual = None
        self._uso_porcentaje = 0.0

    def resetear(self) -> None:
        """Reinicia completamente la CPU."""
        self._proceso_actual = None
        self._ciclos_totales = 0
        self._uso_porcentaje = 0.0

    # ── Representación ───────────────────────────────────────────────────

    def __repr__(self) -> str:
        estado = (
            f"ejecutando '{self._proceso_actual.nombre}'"
            if not self.esta_libre
            else "libre"
        )
        return (
            f"CPU({self._velocidad_mhz}MHz, {estado}, "
            f"ciclos={self._ciclos_totales}, uso={self._uso_porcentaje:.1f}%)"
        )
