"""
processes/schedulers.py
========================
Módulo que implementa los algoritmos de planificación de CPU como
clases Strategy intercambiables dentro del Kernel.

Cada clase hereda de SchedulerBase y define:
    - seleccionar_siguiente(): elige qué proceso despachar desde la cola.
    - es_preemptivo: indica si puede interrumpir al proceso actual.
    - quantum: ciclos máximos antes de preempción (0 = sin límite).
    - nombre: nombre descriptivo para logs y UI.

Algoritmos implementados:
    1. FCFS           — First Come, First Served
    2. SJF            — Shortest Job First (no preemptivo)
    3. RoundRobin     — Turno Circular (preemptivo, quantum configurable)
    4. Prioridad      — Por prioridad nice_value (preemptivo)
    5. ColasMultiples — Colas múltiples con retroalimentación
    6. Garantizado    — Planificación Garantizada (fair share)
    7. DosNiveles     — Planificación a dos niveles (grupo activo / suspendido)

Principios OOP:
    - Strategy: interfaz común, implementaciones intercambiables.
    - Factory: función crear_scheduler() centraliza la creación.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from os_simulator.processes.process import Proceso


# ══════════════════════════════════════════════════════════════════════
# Clase base (Strategy interface)
# ══════════════════════════════════════════════════════════════════════

class SchedulerBase(ABC):
    """Interfaz común para todos los algoritmos de planificación."""

    @property
    @abstractmethod
    def nombre(self) -> str:
        """Nombre legible del algoritmo."""

    @property
    def es_preemptivo(self) -> bool:
        """
        True si el scheduler puede interrumpir un proceso antes de que termine.
        El Kernel usa esta propiedad para decidir si comprobar el quantum.
        """
        return False

    @property
    def quantum(self) -> int:
        """
        Ciclos máximos que un proceso puede ejecutar continuamente.
        0 = sin límite (no preemptivo o preemptivo solo por prioridad).
        """
        return 0

    @abstractmethod
    def seleccionar_siguiente(self, cola: list[Proceso]) -> Optional[Proceso]:
        """
        Escoge el siguiente proceso a ejecutar de la cola de listos.

        Args:
            cola: Lista de procesos en estado LISTO.

        Returns:
            El proceso seleccionado, o None si la cola está vacía.
        """

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(nombre='{self.nombre}')"


# ══════════════════════════════════════════════════════════════════════
# 1. FCFS — First Come, First Served
# ══════════════════════════════════════════════════════════════════════

class SchedulerFCFS(SchedulerBase):
    """
    First Come, First Served (FCFS).

    No preemptivo. Selecciona el proceso que llegó primero al sistema
    (menor arrival_time). En caso de empate, menor PID.
    """

    @property
    def nombre(self) -> str:
        return "FCFS — First Come, First Served"

    def seleccionar_siguiente(self, cola: list[Proceso]) -> Optional[Proceso]:
        if not cola:
            return None
        return min(cola, key=lambda p: (p.arrival_time, p.pid))


# ══════════════════════════════════════════════════════════════════════
# 2. SJF — Shortest Job First
# ══════════════════════════════════════════════════════════════════════

class SchedulerSJF(SchedulerBase):
    """
    Shortest Job First (SJF) — no preemptivo.

    Selecciona el proceso con menor burst_time (ráfaga total).
    En caso de empate, menor arrival_time y luego menor PID.
    """

    @property
    def nombre(self) -> str:
        return "SJF — Shortest Job First"

    def seleccionar_siguiente(self, cola: list[Proceso]) -> Optional[Proceso]:
        if not cola:
            return None
        return min(cola, key=lambda p: (p.burst_time, p.arrival_time, p.pid))


# ══════════════════════════════════════════════════════════════════════
# 3. Round Robin — Turno Circular
# ══════════════════════════════════════════════════════════════════════

class SchedulerRoundRobin(SchedulerBase):
    """
    Round Robin (RR) — preemptivo.

    Selecciona el proceso que lleva más tiempo esperando en cola
    (orden FIFO dentro del quantum). El Kernel lo interrumpe al
    consumir el quantum y lo re-encola al final.
    """

    def __init__(self, quantum: int = 2) -> None:
        self._quantum: int = max(1, quantum)

    @property
    def nombre(self) -> str:
        return f"Round Robin (quantum={self._quantum})"

    @property
    def es_preemptivo(self) -> bool:
        return True

    @property
    def quantum(self) -> int:
        return self._quantum

    def seleccionar_siguiente(self, cola: list[Proceso]) -> Optional[Proceso]:
        """Selecciona el proceso que lleva más tiempo en la cola (FIFO)."""
        if not cola:
            return None
        return min(cola, key=lambda p: (p.arrival_time, p.pid))


# ══════════════════════════════════════════════════════════════════════
# 4. Por Prioridad — Preemptivo
# ══════════════════════════════════════════════════════════════════════

class SchedulerPrioridad(SchedulerBase):
    """
    Planificación por prioridad — preemptivo.

    Selecciona el proceso con el menor nice_value (más urgente).
    El Kernel interrumpe al proceso actual si llega uno con mayor
    prioridad (menor nice_value).
    Desempate por arrival_time y luego por PID.
    """

    @property
    def nombre(self) -> str:
        return "Por Prioridad (preemptivo)"

    @property
    def es_preemptivo(self) -> bool:
        return True

    @property
    def quantum(self) -> int:
        # 0 = sin quantum fijo; la preempción ocurre cuando llega uno más urgente
        return 0

    def seleccionar_siguiente(self, cola: list[Proceso]) -> Optional[Proceso]:
        if not cola:
            return None
        return min(cola, key=lambda p: (p.nice_value, p.arrival_time, p.pid))


# ══════════════════════════════════════════════════════════════════════
# 5. Colas Múltiples con Retroalimentación
# ══════════════════════════════════════════════════════════════════════

class SchedulerColasMultiples(SchedulerBase):
    """
    Colas Múltiples con Retroalimentación (Multilevel Feedback Queue).

    Tres niveles de cola:
        Nivel 0 (Alta):  quantum=2  — recién creados o alta prioridad
        Nivel 1 (Media): quantum=4  — degradados del nivel 0
        Nivel 2 (Baja):  quantum=8  — degradados del nivel 1

    El Kernel aplica el quantum según el queue_level del proceso.
    Si un proceso agota su quantum sin terminar, el Kernel lo degrada
    (incrementa queue_level) antes de re-encolarlo.
    """

    # Quantums por nivel
    QUANTUMS: list[int] = [2, 4, 8]

    def __init__(self) -> None:
        self._quantums: list[int] = self.QUANTUMS[:]

    @property
    def nombre(self) -> str:
        return "Colas Múltiples (q=2/4/8)"

    @property
    def es_preemptivo(self) -> bool:
        return True

    @property
    def quantum(self) -> int:
        # El Kernel obtiene el quantum efectivo llamando a quantum_para_proceso()
        # Este valor es el quantum máximo (nivel 2) como fallback
        return self._quantums[-1]

    def quantum_para_nivel(self, nivel: int) -> int:
        """Devuelve el quantum correspondiente al nivel de cola dado."""
        nivel = max(0, min(nivel, len(self._quantums) - 1))
        return self._quantums[nivel]

    def seleccionar_siguiente(self, cola: list[Proceso]) -> Optional[Proceso]:
        """
        Selecciona el proceso de mayor prioridad (menor queue_level).
        Dentro del mismo nivel, desempata por arrival_time y PID.
        """
        if not cola:
            return None
        return min(cola, key=lambda p: (p.queue_level, p.arrival_time, p.pid))


# ══════════════════════════════════════════════════════════════════════
# 6. Planificación Garantizada
# ══════════════════════════════════════════════════════════════════════

class SchedulerGarantizado(SchedulerBase):
    """
    Planificación Garantizada (Fair Share).

    Garantiza que cada uno de los N procesos activos reciba 1/N del tiempo
    de CPU. Selecciona el proceso cuyo ratio de consumo real vs cuota
    esperada sea el más bajo (el más "hambriento").

    ratio = cpu_time_used / cuota_equitativa
    cuota_equitativa = ciclo_actual / N_procesos   (calculada externamente)

    Si los ratios son iguales, desempata por arrival_time y PID.
    """

    @property
    def nombre(self) -> str:
        return "Planificación Garantizada (Fair Share)"

    @property
    def es_preemptivo(self) -> bool:
        return True

    @property
    def quantum(self) -> int:
        return 0  # Preemptivo solo por comparación de cuotas, no por quantum fijo

    def seleccionar_siguiente(
        self,
        cola: list[Proceso],
        ciclo_actual: int = 0,
        n_total: int = 0,
    ) -> Optional[Proceso]:
        """
        Selecciona el proceso con menor ratio (cpu_usado / cuota_esperada).

        Args:
            cola: Lista de procesos en estado LISTO.
            ciclo_actual: Ciclo actual del kernel (para calcular cuota).
            n_total: Total de procesos activos (en cola + en CPU).
        """
        if not cola:
            return None

        # Número total de competidores (al menos 1 para evitar división por 0)
        n = max(1, n_total if n_total > 0 else len(cola))
        cuota = ciclo_actual / n if ciclo_actual > 0 else 1

        def ratio(p: Proceso) -> float:
            if cuota == 0:
                return 0.0
            return p.cpu_time_used / cuota

        return min(cola, key=lambda p: (ratio(p), p.arrival_time, p.pid))


# ══════════════════════════════════════════════════════════════════════
# 7. Planificación a Dos Niveles
# ══════════════════════════════════════════════════════════════════════

class SchedulerDosNiveles(SchedulerBase):
    """
    Planificación a Dos Niveles.

    Simula la distinción entre procesos en memoria principal (grupo activo)
    y procesos en almacenamiento secundario/disco (grupo suspendido).

    - El grupo ACTIVO (queue_level == 0) se planifica con Round Robin interno.
    - El grupo SUSPENDIDO (queue_level == 1) espera ser promovido.
    - Cuando el grupo activo se vacía, el Kernel promueve los siguientes
      procesos del grupo suspendido (el Kernel llama a promover_suspendidos()).
    - El tamaño máximo del grupo activo es configurable (default=3 procesos).
    """

    def __init__(self, quantum_interno: int = 2, max_activos: int = 3) -> None:
        self._quantum_interno: int = max(1, quantum_interno)
        self._max_activos: int = max(1, max_activos)

    @property
    def nombre(self) -> str:
        return f"Dos Niveles (activos≤{self._max_activos}, q={self._quantum_interno})"

    @property
    def es_preemptivo(self) -> bool:
        return True

    @property
    def quantum(self) -> int:
        return self._quantum_interno

    @property
    def max_activos(self) -> int:
        return self._max_activos

    def seleccionar_siguiente(self, cola: list[Proceso]) -> Optional[Proceso]:
        """
        Selecciona del grupo activo (queue_level==0) usando FIFO.
        Si no hay activos, selecciona del suspendido y lo marca como activo.
        """
        if not cola:
            return None

        activos    = [p for p in cola if p.queue_level == 0]
        suspendidos = [p for p in cola if p.queue_level == 1]

        if activos:
            return min(activos, key=lambda p: (p.arrival_time, p.pid))

        # No hay activos: promover el primer suspendido
        if suspendidos:
            candidato = min(suspendidos, key=lambda p: (p.arrival_time, p.pid))
            candidato.queue_level = 0
            return candidato

        return None

    def inicializar_cola(self, cola: list[Proceso]) -> None:
        """
        Clasifica los procesos recién admitidos: los primeros max_activos
        van al grupo activo (queue_level=0), el resto al suspendido (queue_level=1).
        Llamado por el Kernel al arrancar o al encolar nuevos procesos.
        """
        activos_actuales = sum(1 for p in cola if p.queue_level == 0)
        for p in sorted(cola, key=lambda p: (p.arrival_time, p.pid)):
            if p.queue_level == 1:
                continue  # ya clasificado como suspendido
            if activos_actuales < self._max_activos:
                p.queue_level = 0
                activos_actuales += 1
            else:
                p.queue_level = 1


# ══════════════════════════════════════════════════════════════════════
# Factory — crear_scheduler()
# ══════════════════════════════════════════════════════════════════════

_REGISTRO: dict[str, type] = {
    "fcfs":            SchedulerFCFS,
    "sjf":             SchedulerSJF,
    "round_robin":     SchedulerRoundRobin,
    "prioridad":       SchedulerPrioridad,
    "colas_multiples": SchedulerColasMultiples,
    "garantizado":     SchedulerGarantizado,
    "dos_niveles":     SchedulerDosNiveles,
}

SCHEDULERS_DISPONIBLES: list[str] = list(_REGISTRO.keys())


def crear_scheduler(tipo: str = "fcfs", **kwargs) -> SchedulerBase:
    """
    Factory: crea una instancia del scheduler solicitado.

    Args:
        tipo: Clave del algoritmo. Opciones:
              "fcfs" | "sjf" | "round_robin" | "prioridad" |
              "colas_multiples" | "garantizado" | "dos_niveles"
        **kwargs: Parámetros opcionales pasados al constructor:
                  - quantum (int): Para round_robin (default 2).
                  - quantum_interno (int): Para dos_niveles (default 2).
                  - max_activos (int): Para dos_niveles (default 3).

    Returns:
        Instancia del SchedulerBase correspondiente.

    Raises:
        ValueError: Si el tipo no es reconocido.
    """
    tipo = tipo.lower().strip()
    cls = _REGISTRO.get(tipo)
    if cls is None:
        validos = ", ".join(_REGISTRO.keys())
        raise ValueError(
            f"Scheduler desconocido: '{tipo}'. Válidos: {validos}"
        )
    return cls(**kwargs)
