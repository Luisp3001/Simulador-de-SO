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
    """Niveles de prioridad de planificación (compatibilidad con Kernel existente)."""
    ALTA  = 1
    MEDIA = 2
    BAJA  = 3


class Proceso:
    """
    Representa un proceso del sistema operativo.

    Attributes:
        pid (int): Identificador único del proceso.
        nombre (str): Nombre descriptivo del proceso.
        memoria_requerida (int): Memoria en MB que necesita el proceso.
        burst_time (int): Ráfaga total de CPU necesaria (en ciclos).
        nice_value (int): Prioridad numérica Unix-style (-20 a +19). Menor = más prioritario.
        arrival_time (int): Ciclo del kernel en que fue creado/admitido.
        queue_level (int): Nivel de cola para planificación de colas múltiples.
    """

    # Contador de clase para asignar PIDs únicos
    _contador_pid: int = 1

    def __init__(
        self,
        nombre: str,
        memoria_requerida: int = 128,
        burst_time: int = 5,
        nice_value: int = 0,
        arrival_time: int = 0,
        queue_level: int = 0,
    ) -> None:
        self._pid: int = Proceso._contador_pid
        Proceso._contador_pid += 1

        self._nombre: str = nombre
        self._estado: EstadoProceso = EstadoProceso.NUEVO
        self._memoria_requerida: int = memoria_requerida

        # ── Campos de planificación ───────────────────────────────────────
        self._burst_time: int = max(1, burst_time)       # ráfaga total en ciclos
        self._nice_value: int = nice_value               # prioridad numérica (-20 a +19)
        self._arrival_time: int = arrival_time           # ciclo de llegada al sistema
        self._queue_level: int = queue_level             # nivel de cola (colas múltiples)

        # Contadores de ejecución
        self._ciclos_ejecutados: int = 0
        self._remaining_time: int = self._burst_time     # ciclos restantes

        # ── Métricas calculadas (las escribe el Kernel al finalizar) ──────
        self._start_time: int = -1       # ciclo en que empezó a ejecutar (-1 = no iniciado)
        self._completion_time: int = 0   # ciclo en que terminó
        self._waiting_time: int = 0      # tiempo esperando en cola
        self._turnaround_time: int = 0   # completion_time - arrival_time

        # Para Planificación Garantizada
        self._cpu_time_used: int = 0     # ciclos totales de CPU consumidos (alias de ciclos_ejecutados)

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
    def memoria_requerida(self) -> int:
        """Memoria requerida en MB."""
        return self._memoria_requerida

    @property
    def burst_time(self) -> int:
        """Ráfaga total de CPU necesaria en ciclos."""
        return self._burst_time

    @property
    def nice_value(self) -> int:
        """Prioridad numérica Unix-style. Menor número = más urgente."""
        return self._nice_value

    @property
    def arrival_time(self) -> int:
        """Ciclo del kernel en que fue creado y admitido."""
        return self._arrival_time

    @property
    def queue_level(self) -> int:
        """Nivel de cola para planificación de colas múltiples (0=alta, 1=media, 2=baja)."""
        return self._queue_level

    @queue_level.setter
    def queue_level(self, value: int) -> None:
        self._queue_level = max(0, value)

    @property
    def ciclos_ejecutados(self) -> int:
        return self._ciclos_ejecutados

    @property
    def remaining_time(self) -> int:
        """Ciclos de CPU que le faltan al proceso para completarse."""
        return self._remaining_time

    @property
    def cpu_time_used(self) -> int:
        """Alias de ciclos_ejecutados. Útil para Planificación Garantizada."""
        return self._ciclos_ejecutados

    @property
    def start_time(self) -> int:
        """Ciclo en que el proceso empezó a ejecutar por primera vez (-1 si aún no)."""
        return self._start_time

    @property
    def completion_time(self) -> int:
        """Ciclo en que el proceso terminó su ejecución."""
        return self._completion_time

    @property
    def waiting_time(self) -> int:
        """Tiempo total esperando en cola (turnaround - burst_time)."""
        return self._waiting_time

    @property
    def turnaround_time(self) -> int:
        """Tiempo total desde llegada hasta finalización (completion - arrival)."""
        return self._turnaround_time

    @property
    def completado(self) -> bool:
        """Indica si el proceso ha terminado su trabajo."""
        return self._ciclos_ejecutados >= self._burst_time

    # ── Transiciones de estado ───────────────────────────────────────────

    def admitir(self) -> None:
        """Transición: NUEVO → LISTO. El SO admite el proceso."""
        if self._estado == EstadoProceso.NUEVO:
            self._estado = EstadoProceso.LISTO

    def despachar(self, ciclo_actual: int = -1) -> None:
        """
        Transición: LISTO → EJECUTANDO. El planificador le asigna CPU.

        Args:
            ciclo_actual: Ciclo del kernel al momento del despacho.
                          Si es -1 no se actualiza start_time.
        """
        if self._estado == EstadoProceso.LISTO:
            self._estado = EstadoProceso.EJECUTANDO
            if self._start_time == -1 and ciclo_actual >= 0:
                self._start_time = ciclo_actual

    def ejecutar_ciclo(self) -> None:
        """Avanza un ciclo de CPU. Si completa, pasa a TERMINADO."""
        if self._estado != EstadoProceso.EJECUTANDO:
            return
        self._ciclos_ejecutados += 1
        self._remaining_time = max(0, self._burst_time - self._ciclos_ejecutados)
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

    def registrar_metricas(self, ciclo_actual: int) -> None:
        """
        Calcula y persiste las métricas de finalización.
        Llamado por el Kernel cuando el proceso termina.

        Args:
            ciclo_actual: Ciclo del kernel en que terminó la ejecución.
        """
        self._completion_time = ciclo_actual
        self._turnaround_time = ciclo_actual - self._arrival_time
        self._waiting_time = max(0, self._turnaround_time - self._burst_time)

    # ── Representación ───────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"Proceso(pid={self._pid}, nombre='{self._nombre}', "
            f"estado={self._estado.name}, nice={self._nice_value}, "
            f"burst={self._burst_time}, remaining={self._remaining_time}, "
            f"mem={self._memoria_requerida}MB)"
        )
