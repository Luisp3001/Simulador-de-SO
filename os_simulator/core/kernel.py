"""
core/kernel.py
==============
Módulo que modela el Kernel del sistema operativo.

El Kernel es el corazón del simulador. Actúa como intermediario
entre los procesos y los recursos del hardware (CPU, Memoria,
Dispositivos, Sistema de Archivos).

Principios OOP aplicados:
    - Fachada (Facade): provee una interfaz unificada a todos los subsistemas.
    - Composición: el Kernel contiene instancias de CPU, Memoria, etc.
    - Encapsulamiento: los subsistemas no se acceden directamente desde fuera.
    - Strategy: el algoritmo de planificación es intercambiable en tiempo real.
"""

from __future__ import annotations
from collections import deque
from datetime import datetime
from typing import Optional

from os_simulator.core.cpu import CPU
from os_simulator.memory.memory import Memoria
from os_simulator.processes.process import Proceso, EstadoProceso
from os_simulator.processes.schedulers import (
    SchedulerBase,
    SchedulerFCFS,
    SchedulerColasMultiples,
    SchedulerDosNiveles,
    SchedulerGarantizado,
    SchedulerPrioridad,
    crear_scheduler,
    SCHEDULERS_DISPONIBLES,
)
from os_simulator.hardware.device import Dispositivo, Teclado, Disco, DispositivoRed
from os_simulator.filesystem.filesystem import SistemaArchivos


class EntradaLog:
    """Una entrada del registro de eventos del sistema."""

    def __init__(self, mensaje: str, nivel: str = "INFO") -> None:
        self.timestamp: datetime = datetime.now()
        self.nivel: str = nivel
        self.mensaje: str = mensaje

    def __str__(self) -> str:
        ts = self.timestamp.strftime("%H:%M:%S")
        return f"[{ts}] [{self.nivel}] {self.mensaje}"


class Kernel:
    """
    Núcleo del sistema operativo simulado.

    Orquesta todos los subsistemas: CPU, Memoria, Dispositivos y
    Sistema de Archivos. El algoritmo de planificación es intercambiable
    en tiempo real mediante el patrón Strategy.

    Attributes:
        nombre (str): Nombre del SO (por defecto 'BALJ OS').
        version (str): Versión del SO.
    """

    def __init__(
        self,
        nombre: str = "BALJ OS",
        version: str = "0.1.0",
        ram_mb: int = 2048,
    ) -> None:
        self._nombre: str = nombre
        self._version: str = version
        self._activo: bool = False
        self._ciclo_reloj: int = 0

        # ── Subsistemas ──────────────────────────────────────────────────
        self._cpu: CPU = CPU()
        self._memoria: Memoria = Memoria(capacidad_total=ram_mb)
        self._sistema_archivos: SistemaArchivos = SistemaArchivos()

        # Dispositivos de E/S registrados
        self._dispositivos: dict[str, Dispositivo] = {}
        self._registrar_dispositivos_base()

        # ── Planificación ────────────────────────────────────────────────
        self._scheduler: SchedulerBase = SchedulerFCFS()
        # Cola de procesos listos (deque; el orden real lo impone el scheduler)
        self._cola_procesos: deque[Proceso] = deque()
        self._procesos_terminados: list[Proceso] = []

        # Contador de ciclos que el proceso actual lleva en la CPU (para quantum)
        self._ciclos_en_cpu: int = 0

        # ── Log del sistema ───────────────────────────────────────────────
        self._log: list[EntradaLog] = []

    def _registrar_dispositivos_base(self) -> None:
        """Registra los dispositivos de hardware predeterminados."""
        self._dispositivos["teclado"]  = Teclado()
        self._dispositivos["disco1"]   = Disco("Disco Duro 1", capacidad_gb=500)
        self._dispositivos["red"]      = DispositivoRed()

    # ── Propiedades ──────────────────────────────────────────────────────

    @property
    def nombre(self) -> str:
        return self._nombre

    @property
    def version(self) -> str:
        return self._version

    @property
    def activo(self) -> bool:
        """Indica si el kernel está en ejecución."""
        return self._activo

    @property
    def ciclo_reloj(self) -> int:
        """Número de ciclos de reloj transcurridos desde el arranque."""
        return self._ciclo_reloj

    @property
    def cpu(self) -> CPU:
        return self._cpu

    @property
    def memoria(self) -> Memoria:
        return self._memoria

    @property
    def sistema_archivos(self) -> SistemaArchivos:
        return self._sistema_archivos

    @property
    def dispositivos(self) -> dict[str, Dispositivo]:
        return dict(self._dispositivos)

    @property
    def cola_procesos(self) -> list[Proceso]:
        """Lista de procesos en cola de ejecución (copia de solo lectura)."""
        return list(self._cola_procesos)

    @property
    def procesos_terminados(self) -> list[Proceso]:
        """Lista de procesos completados/finalizados (copia de solo lectura)."""
        return list(self._procesos_terminados)

    @property
    def scheduler(self) -> SchedulerBase:
        """Algoritmo de planificación actualmente activo."""
        return self._scheduler

    @property
    def log(self) -> list[EntradaLog]:
        """Historial completo del log del sistema."""
        return list(self._log)

    # ── Ciclo de vida del kernel ──────────────────────────────────────────

    def arrancar(self) -> None:
        """
        Inicia el kernel y todos sus subsistemas.

        Raises:
            RuntimeError: Si el kernel ya está activo.
        """
        if self._activo:
            raise RuntimeError("El kernel ya está en ejecución.")
        self._activo = True
        self._ciclo_reloj = 0
        self._registrar_log(f"{self._nombre} v{self._version} — Kernel iniciado.")
        self._registrar_log(f"RAM disponible: {self._memoria.memoria_disponible} MB.", "OK")
        self._registrar_log(f"CPU: {self._cpu.velocidad_mhz} MHz inicializada.", "OK")
        self._registrar_log("Sistema de archivos montado.", "OK")
        self._registrar_log(
            f"Planificador activo: {self._scheduler.nombre}.", "OK"
        )
        self._registrar_log("Sistema listo.", "OK")

    def detener(self) -> None:
        """Detiene el kernel de forma ordenada, liberando todos los recursos."""
        if not self._activo:
            return
        # Terminar procesos activos
        if not self._cpu.esta_libre:
            proceso = self._cpu.proceso_actual
            self._cpu.interrumpir()
            self._memoria.liberar(proceso.pid)
        for proceso in list(self._cola_procesos):
            proceso.terminar()
            self._memoria.liberar(proceso.pid)
        self._cola_procesos.clear()
        self._ciclos_en_cpu = 0
        self._activo = False
        self._registrar_log("Kernel detenido. Todos los recursos liberados.", "WARN")

    def reiniciar(self) -> None:
        """Detiene y vuelve a arrancar el kernel."""
        self._registrar_log("Reiniciando el sistema…", "WARN")
        self.detener()
        self._cpu.resetear()
        self._memoria.resetear()
        self._procesos_terminados.clear()
        self.arrancar()

    # ── Planificador ─────────────────────────────────────────────────────

    def cambiar_scheduler(self, tipo: str, **kwargs) -> None:
        """
        Intercambia el algoritmo de planificación en tiempo de ejecución.

        Args:
            tipo: Clave del algoritmo. Ver SCHEDULERS_DISPONIBLES.
            **kwargs: Parámetros opcionales (quantum, max_activos, etc.).

        Raises:
            ValueError: Si el tipo no es reconocido.
        """
        nuevo = crear_scheduler(tipo, **kwargs)
        self._scheduler = nuevo
        self._ciclos_en_cpu = 0  # reset del quantum counter
        self._registrar_log(
            f"Planificador cambiado a: {nuevo.nombre}.", "OK"
        )

    def cambiar_algoritmo_memoria(self, tipo: str) -> None:
        """Cambia el gestor de RAM únicamente cuando no hay procesos activos."""
        hay_procesos_activos = not self._cpu.esta_libre or bool(self._cola_procesos)
        if hay_procesos_activos:
            mensaje = (
                "No se puede cambiar el algoritmo de memoria mientras haya "
                "procesos en CPU o en la cola."
            )
            self._registrar_log(mensaje, "ERR")
            raise RuntimeError(mensaje)

        self._memoria.cambiar_algoritmo(tipo)
        self._registrar_log(
            f"Gestor de memoria cambiado a: {self._memoria.algoritmo_nombre}.", "OK"
        )

    # ── Gestión de procesos ───────────────────────────────────────────────

    def crear_proceso(
        self,
        nombre: str,
        memoria_mb: int = 128,
        burst_time: int = 5,
        nice_value: int = 0,
    ) -> Optional[Proceso]:
        """
        Crea un proceso, le asigna memoria y lo encola para ejecución.

        Args:
            nombre: Nombre del proceso.
            memoria_mb: Memoria requerida en MB.
            burst_time: Ráfaga de CPU necesaria en ciclos (default 5).
            nice_value: Prioridad numérica Unix-style (default 0, menor = más prioritario).

        Returns:
            El proceso creado, o None si no hay recursos suficientes.
        """
        if not self._activo:
            self._registrar_log("Error: kernel inactivo. No se puede crear proceso.", "ERR")
            return None

        proceso = Proceso(
            nombre,
            memoria_requerida=memoria_mb,
            burst_time=burst_time,
            nice_value=nice_value,
            arrival_time=self._ciclo_reloj,
        )

        if not self._memoria.asignar(proceso.pid, memoria_mb):
            self._registrar_log(
                f"Error: Memoria insuficiente para '{nombre}' ({memoria_mb} MB).", "ERR"
            )
            return None

        proceso.admitir()

        # Para planificación de dos niveles: clasificar al ingresar
        if isinstance(self._scheduler, SchedulerDosNiveles):
            cola_lista = list(self._cola_procesos)
            activos = sum(1 for p in cola_lista if p.queue_level == 0)
            if activos < self._scheduler.max_activos:
                proceso.queue_level = 0
            else:
                proceso.queue_level = 1

        self._cola_procesos.append(proceso)

        self._registrar_log(
            f"Proceso '{nombre}' [PID {proceso.pid}] encolado "
            f"({memoria_mb} MB, burst={burst_time}, nice={nice_value}).",
            "OK",
        )
        return proceso

    def terminar_proceso(self, pid: int) -> bool:
        """
        Termina un proceso dado su PID, liberando sus recursos.

        Returns:
            True si el proceso fue encontrado y terminado.
        """
        # ¿Está en la CPU?
        if not self._cpu.esta_libre and self._cpu.proceso_actual.pid == pid:
            proceso = self._cpu.proceso_actual
            self._cpu.interrumpir()
            proceso.terminar()
            self._memoria.liberar(pid)
            self._procesos_terminados.append(proceso)
            self._ciclos_en_cpu = 0
            self._registrar_log(f"Proceso [PID {pid}] terminado (forzado desde CPU).", "WARN")
            return True

        # ¿Está en la cola?
        for proceso in list(self._cola_procesos):
            if proceso.pid == pid:
                self._cola_procesos.remove(proceso)
                proceso.terminar()
                self._memoria.liberar(pid)
                self._procesos_terminados.append(proceso)
                self._registrar_log(f"Proceso [PID {pid}] eliminado de la cola.", "WARN")
                return True

        self._registrar_log(f"Error: PID {pid} no encontrado.", "ERR")
        return False

    # ── Ciclo de reloj ────────────────────────────────────────────────────

    def avanzar_ciclo(self) -> None:
        """
        Avanza un ciclo del reloj del sistema.

        Flujo para schedulers preemptivos:
          1. Si el proceso actual agotó su quantum → interrumpir y re-encolar.
          2. Si la CPU está libre y hay procesos → pedir al scheduler el siguiente.
          3. Ejecutar un ciclo de CPU.
          4. Si el proceso terminó → calcular métricas, liberar recursos.

        Flujo adicional para Colas Múltiples:
          - Al re-encolar por quantum: degradar el nivel de cola.

        Flujo adicional para Planificación por Prioridad:
          - Si hay en cola alguno con menor nice_value que el actual → interrumpir.
        """
        if not self._activo:
            self._registrar_log("Error: el kernel está inactivo.", "ERR")
            return

        self._ciclo_reloj += 1
        self._registrar_log(f"═══ Ciclo #{self._ciclo_reloj} ═══", "SYS")

        # ── 1. Verificar preempción ───────────────────────────────────────
        if not self._cpu.esta_libre and self._scheduler.es_preemptivo:
            self._verificar_preempcion()

        # ── 2. Despachar si CPU está libre ───────────────────────────────
        if self._cpu.esta_libre and self._cola_procesos:
            self._despachar_siguiente()

        # ── 3. Ejecutar ciclo de CPU ──────────────────────────────────────
        if not self._cpu.esta_libre:
            proceso_actual = self._cpu.proceso_actual
            self._ciclos_en_cpu += 1
            terminado = self._cpu.ejecutar_ciclo()

            if terminado:
                # Calcular métricas de finalización
                proceso_actual.registrar_metricas(self._ciclo_reloj)
                self._memoria.liberar(proceso_actual.pid)
                self._procesos_terminados.append(proceso_actual)
                self._ciclos_en_cpu = 0
                self._registrar_log(
                    f"Proceso '{proceso_actual.nombre}' [PID {proceso_actual.pid}] "
                    f"completado — wait={proceso_actual.waiting_time} "
                    f"TAT={proceso_actual.turnaround_time}.",
                    "OK",
                )
        else:
            self._registrar_log("CPU inactiva — sin procesos en cola.", "INFO")

    def _verificar_preempcion(self) -> None:
        """
        Comprueba si el proceso en CPU debe ser interrumpido
        según las reglas del scheduler activo.
        """
        proceso_actual = self._cpu.proceso_actual

        # ── Quantum agotado (Round Robin y Colas Múltiples) ───────────────
        quantum_efectivo = self._scheduler.quantum

        # Para Colas Múltiples, el quantum depende del nivel del proceso
        if isinstance(self._scheduler, SchedulerColasMultiples):
            quantum_efectivo = self._scheduler.quantum_para_nivel(proceso_actual.queue_level)

        if quantum_efectivo > 0 and self._ciclos_en_cpu >= quantum_efectivo:
            self._registrar_log(
                f"Quantum agotado — '{proceso_actual.nombre}' [PID {proceso_actual.pid}] "
                f"interrumpido tras {self._ciclos_en_cpu} ciclos.",
                "INFO",
            )
            # Degradar nivel en Colas Múltiples
            if isinstance(self._scheduler, SchedulerColasMultiples):
                nivel_anterior = proceso_actual.queue_level
                proceso_actual.queue_level = min(nivel_anterior + 1, 2)
                if proceso_actual.queue_level != nivel_anterior:
                    self._registrar_log(
                        f"'{proceso_actual.nombre}' degradado a cola nivel {proceso_actual.queue_level}.",
                        "INFO",
                    )
            self._cpu.interrumpir()
            self._cola_procesos.append(proceso_actual)
            self._ciclos_en_cpu = 0
            return

        # ── Preempción por prioridad ──────────────────────────────────────
        if isinstance(self._scheduler, SchedulerPrioridad) and self._cola_procesos:
            mejor_en_cola = min(self._cola_procesos, key=lambda p: p.nice_value)
            if mejor_en_cola.nice_value < proceso_actual.nice_value:
                self._registrar_log(
                    f"Preempción por prioridad: '{mejor_en_cola.nombre}' "
                    f"(nice={mejor_en_cola.nice_value}) desplaza a "
                    f"'{proceso_actual.nombre}' (nice={proceso_actual.nice_value}).",
                    "INFO",
                )
                self._cpu.interrumpir()
                self._cola_procesos.append(proceso_actual)
                self._ciclos_en_cpu = 0
                return

        # ── Preempción por cuota (Planificación Garantizada) ─────────────
        if isinstance(self._scheduler, SchedulerGarantizado) and self._cola_procesos:
            n_total = len(self._cola_procesos) + 1  # en cola + el que corre
            cuota = self._ciclo_reloj / n_total if self._ciclo_reloj > 0 else 1
            ratio_actual = proceso_actual.cpu_time_used / cuota if cuota > 0 else 0
            mejor = self._scheduler.seleccionar_siguiente(
                list(self._cola_procesos),
                ciclo_actual=self._ciclo_reloj,
                n_total=n_total,
            )
            if mejor is not None:
                ratio_mejor = mejor.cpu_time_used / cuota if cuota > 0 else 0
                if ratio_mejor < ratio_actual:
                    self._registrar_log(
                        f"Planif. Garantizada: cede CPU de "
                        f"'{proceso_actual.nombre}' a '{mejor.nombre}'.",
                        "INFO",
                    )
                    self._cpu.interrumpir()
                    self._cola_procesos.append(proceso_actual)
                    self._ciclos_en_cpu = 0

    def _despachar_siguiente(self) -> None:
        """Pide al scheduler el siguiente proceso y lo despacha en la CPU."""
        cola_lista = list(self._cola_procesos)

        # Planificación Garantizada necesita parámetros extra
        if isinstance(self._scheduler, SchedulerGarantizado):
            siguiente = self._scheduler.seleccionar_siguiente(
                cola_lista,
                ciclo_actual=self._ciclo_reloj,
                n_total=len(cola_lista),
            )
        else:
            siguiente = self._scheduler.seleccionar_siguiente(cola_lista)

        if siguiente is None:
            return

        self._cola_procesos.remove(siguiente)
        uso = 20.0 + len(self._cola_procesos) * 10.0
        self._cpu.despachar(siguiente, uso=uso)
        siguiente.despachar(ciclo_actual=self._ciclo_reloj)
        self._ciclos_en_cpu = 0

        self._registrar_log(
            f"CPU → '{siguiente.nombre}' [PID {siguiente.pid}] "
            f"(scheduler: {self._scheduler.nombre}).",
            "OK",
        )

    # ── Dispositivos ──────────────────────────────────────────────────────

    def registrar_dispositivo(self, clave: str, dispositivo: Dispositivo) -> None:
        """Registra un nuevo dispositivo de E/S en el kernel."""
        self._dispositivos[clave] = dispositivo
        self._registrar_log(f"Dispositivo '{dispositivo.nombre}' registrado.", "OK")

    # ── Log ───────────────────────────────────────────────────────────────

    def _registrar_log(self, mensaje: str, nivel: str = "INFO") -> None:
        entrada = EntradaLog(mensaje, nivel)
        self._log.append(entrada)

    def imprimir_log(self) -> None:
        """Imprime el log completo en la consola."""
        for entrada in self._log:
            print(entrada)

    def ultimo_log(self, n: int = 10) -> list[EntradaLog]:
        """Retorna las últimas n entradas del log."""
        return self._log[-n:]

    # ── Estado del sistema ────────────────────────────────────────────────

    def estado(self) -> dict:
        """
        Retorna un diccionario con el estado actual de todos los subsistemas.
        Útil para que la interfaz web/gráfica consulte datos.
        """
        def _proc_dict(p: Proceso, estado_override: str | None = None) -> dict:
            return {
                "pid":             p.pid,
                "nombre":          p.nombre,
                "estado":          estado_override or p.estado.name,
                "nice_value":      p.nice_value,
                "memoria":         p.memoria_requerida,
                "burst_time":      p.burst_time,
                "remaining_time":  p.remaining_time,
                "queue_level":     p.queue_level,
                "arrival_time":    p.arrival_time,
                "start_time":      p.start_time,
            }

        procesos_en_cola = [_proc_dict(p) for p in self._cola_procesos]

        procesos_terminados = [
            {
                **_proc_dict(p),
                "completion_time":  p.completion_time,
                "waiting_time":     p.waiting_time,
                "turnaround_time":  p.turnaround_time,
            }
            for p in self._procesos_terminados
        ]

        return {
            "kernel": {
                "nombre":    self._nombre,
                "version":   self._version,
                "activo":    self._activo,
                "ciclo":     self._ciclo_reloj,
                "scheduler": self._scheduler.nombre,
            },
            "cpu": {
                "libre":          self._cpu.esta_libre,
                "proceso_actual": (
                    self._cpu.proceso_actual.nombre
                    if not self._cpu.esta_libre else None
                ),
                "uso_porcentaje": self._cpu.uso_porcentaje,
                "ciclos_totales": self._cpu.ciclos_totales,
                "ciclos_en_cpu":  self._ciclos_en_cpu,
            },
            "memoria": self._memoria.estado(),
            "procesos_en_cola":   procesos_en_cola,
            "procesos_terminados": procesos_terminados,
            "dispositivos": {
                k: {"nombre": d.nombre, "estado": d.estado.name}
                for k, d in self._dispositivos.items()
            },
        }

    # ── Representación ────────────────────────────────────────────────────

    def __repr__(self) -> str:
        estado = "ACTIVO" if self._activo else "INACTIVO"
        return (
            f"Kernel('{self._nombre}' v{self._version}, {estado}, "
            f"ciclo={self._ciclo_reloj}, "
            f"scheduler='{self._scheduler.nombre}', "
            f"procesos_en_cola={len(self._cola_procesos)})"
        )
