"""
processes/process.py
====================
Módulo que modela un Proceso del sistema operativo.

Un proceso representa un programa en ejecución con su propio
estado, prioridad, y recursos asignados (memoria, CPU).

Principios OOP aplicados:
    - Encapsulamiento: atributos privados con propiedades públicas.
    - Abstracción: expone solo la interfaz necesaria al exterior.
"""

from enum import Enum, auto


class EstadoProceso(Enum):
    """Enumeración de los posibles estados de un proceso (ciclo de vida)."""
    NUEVO      = auto()   # Proceso recién creado, aún no admitido por el SO.
    LISTO      = auto()   # En cola, esperando tiempo de CPU.
    EJECUTANDO = auto()   # Actualmente usando la CPU.
    BLOQUEADO  = auto()   # Esperando un evento de E/S u otro recurso.
    TERMINADO  = auto()   # Ha completado su ejecución.


class PrioridadProceso(Enum):
    """Niveles de prioridad de planificación."""
    ALTA  = 1
    MEDIA = 2
    BAJA  = 3


class Proceso:
    """
    Representa un proceso del sistema operativo.

    Attributes:
        pid (int): Identificador único del proceso.
        nombre (str): Nombre descriptivo del proceso.
        prioridad (PrioridadProceso): Prioridad de planificación.
        memoria_requerida (int): Memoria en MB que necesita el proceso.
    """

    # Contador de clase para asignar PIDs únicos
    _contador_pid: int = 1

    def __init__(
        self,
        nombre: str,
        memoria_requerida: int = 128,
        prioridad: PrioridadProceso = PrioridadProceso.MEDIA,
    ) -> None:
        self._pid: int = Proceso._contador_pid
        Proceso._contador_pid += 1

        self._nombre: str = nombre
        self._estado: EstadoProceso = EstadoProceso.NUEVO
        self._prioridad: PrioridadProceso = prioridad
        self._memoria_requerida: int = memoria_requerida

        # Contadores de ciclos de CPU
        self._ciclos_ejecutados: int = 0
        self._ciclos_requeridos: int = 5   # Simplificación: 5 ciclos para completar

    # ── Propiedades de solo lectura ──────────────────────────────────────

    @property
    def pid(self) -> int:
        """Identificador único del proceso."""
        return self._pid

    @property
    def nombre(self) -> str:
        return self._nombre

    @property
    def estado(self) -> EstadoProceso:
        return self._estado

    @property
    def prioridad(self) -> PrioridadProceso:
        return self._prioridad

    @property
    def memoria_requerida(self) -> int:
        """Memoria requerida en MB."""
        return self._memoria_requerida

    @property
    def ciclos_ejecutados(self) -> int:
        return self._ciclos_ejecutados

    @property
    def completado(self) -> bool:
        """Indica si el proceso ha terminado su trabajo."""
        return self._ciclos_ejecutados >= self._ciclos_requeridos

    # ── Transiciones de estado ───────────────────────────────────────────

    def admitir(self) -> None:
        """Transición: NUEVO → LISTO. El SO admite el proceso."""
        if self._estado == EstadoProceso.NUEVO:
            self._estado = EstadoProceso.LISTO

    def despachar(self) -> None:
        """Transición: LISTO → EJECUTANDO. El planificador le asigna CPU."""
        if self._estado == EstadoProceso.LISTO:
            self._estado = EstadoProceso.EJECUTANDO

    def ejecutar_ciclo(self) -> None:
        """Avanza un ciclo de CPU. Si completa, pasa a TERMINADO."""
        if self._estado != EstadoProceso.EJECUTANDO:
            return
        self._ciclos_ejecutados += 1
        if self.completado:
            self._estado = EstadoProceso.TERMINADO

    def bloquear(self) -> None:
        """Transición: EJECUTANDO → BLOQUEADO. Espera E/S."""
        if self._estado == EstadoProceso.EJECUTANDO:
            self._estado = EstadoProceso.BLOQUEADO

    def desbloquear(self) -> None:
        """Transición: BLOQUEADO → LISTO. El evento esperado ocurrió."""
        if self._estado == EstadoProceso.BLOQUEADO:
            self._estado = EstadoProceso.LISTO

    def terminar(self) -> None:
        """Fuerza la terminación del proceso (ej. kill)."""
        self._estado = EstadoProceso.TERMINADO

    # ── Representación ───────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"Proceso(pid={self._pid}, nombre='{self._nombre}', "
            f"estado={self._estado.name}, prioridad={self._prioridad.name}, "
            f"mem={self._memoria_requerida}MB)"
        )
