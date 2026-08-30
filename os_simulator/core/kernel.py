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
"""

from __future__ import annotations
from collections import deque
from datetime import datetime
from typing import Optional

from os_simulator.core.cpu import CPU
from os_simulator.memory.memory import Memoria
from os_simulator.processes.process import Proceso, EstadoProceso, PrioridadProceso
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
    Sistema de Archivos. Implementa un planificador Round-Robin simple
    y mantiene el registro de eventos del sistema.

    Attributes:
        nombre (str): Nombre del SO (por defecto 'Aethelred OS').
        version (str): Versión del SO.
    """

    def __init__(
        self,
        nombre: str = "Aethelred OS",
        version: str = "0.1.0",
        ram_mb: int = 4096,
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

        # ── Cola de procesos (planificación FIFO / por prioridad) ─────────
        # Usamos una deque por prioridad: alta → media → baja
        self._cola_procesos: deque[Proceso] = deque()
        self._procesos_terminados: list[Proceso] = []

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

    # ── Gestión de procesos ───────────────────────────────────────────────

    def crear_proceso(
        self,
        nombre: str,
        memoria_mb: int = 128,
        prioridad: PrioridadProceso = PrioridadProceso.MEDIA,
    ) -> Optional[Proceso]:
        """
        Crea un proceso, le asigna memoria y lo encola para ejecución.

        Args:
            nombre: Nombre del proceso.
            memoria_mb: Memoria requerida en MB.
            prioridad: Prioridad de planificación.

        Returns:
            El proceso creado, o None si no hay recursos suficientes.
        """
        if not self._activo:
            self._registrar_log("Error: kernel inactivo. No se puede crear proceso.", "ERR")
            return None

        proceso = Proceso(nombre, memoria_mb, prioridad)

        if not self._memoria.asignar(proceso.pid, memoria_mb):
            self._registrar_log(
                f"Error: Memoria insuficiente para '{nombre}' ({memoria_mb} MB).", "ERR"
            )
            return None

        proceso.admitir()

        # Insertar en cola según prioridad (Alta al frente)
        if prioridad == PrioridadProceso.ALTA:
            self._cola_procesos.appendleft(proceso)
        else:
            self._cola_procesos.append(proceso)

        self._registrar_log(
            f"Proceso '{nombre}' [PID {proceso.pid}] encolado "
            f"({memoria_mb} MB, prioridad {prioridad.name}).",
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

        Planificador Round-Robin simple:
          1. Si la CPU está libre y hay procesos en cola → despachar el siguiente.
          2. Ejecutar un ciclo en el proceso actual.
          3. Si el proceso terminó → liberar recursos y despachar el siguiente.
        """
        if not self._activo:
            self._registrar_log("Error: el kernel está inactivo.", "ERR")
            return

        self._ciclo_reloj += 1
        self._registrar_log(f"═══ Ciclo #{self._ciclo_reloj} ═══", "SYS")

        # Despachar si CPU libre y hay procesos
        if self._cpu.esta_libre and self._cola_procesos:
            siguiente = self._cola_procesos.popleft()
            self._cpu.despachar(siguiente, uso=20.0 + len(self._cola_procesos) * 10.0)
            self._registrar_log(
                f"CPU → '{siguiente.nombre}' [PID {siguiente.pid}].", "OK"
            )

        # Ejecutar ciclo en la CPU
        if not self._cpu.esta_libre:
            proceso_actual = self._cpu.proceso_actual
            terminado = self._cpu.ejecutar_ciclo()
            if terminado:
                self._memoria.liberar(proceso_actual.pid)
                self._procesos_terminados.append(proceso_actual)
                self._registrar_log(
                    f"Proceso '{proceso_actual.nombre}' [PID {proceso_actual.pid}] completado.",
                    "OK",
                )
        else:
            self._registrar_log("CPU inactiva — sin procesos en cola.", "INFO")

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
        return {
            "kernel": {
                "nombre":  self._nombre,
                "version": self._version,
                "activo":  self._activo,
                "ciclo":   self._ciclo_reloj,
            },
            "cpu": {
                "libre":          self._cpu.esta_libre,
                "proceso_actual": (
                    self._cpu.proceso_actual.nombre
                    if not self._cpu.esta_libre else None
                ),
                "uso_porcentaje": self._cpu.uso_porcentaje,
                "ciclos_totales": self._cpu.ciclos_totales,
            },
            "memoria": {
                "total_mb":      self._memoria.capacidad_total,
                "usada_mb":      self._memoria.memoria_usada,
                "disponible_mb": self._memoria.memoria_disponible,
                "uso_pct":       round(self._memoria.uso_porcentaje, 2),
            },
            "procesos_en_cola": [
                {"pid": p.pid, "nombre": p.nombre, "estado": p.estado.name}
                for p in self._cola_procesos
            ],
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
            f"procesos_en_cola={len(self._cola_procesos)})"
        )
