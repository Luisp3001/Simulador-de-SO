"""
hardware/device.py
==================
Módulo que modela los Dispositivos de Entrada/Salida (E/S).

Un dispositivo puede estar disponible, ocupado atendiendo una
operación, o en fallo. El Kernel coordina el acceso a los
dispositivos para que los procesos no colisionen.

Principios OOP aplicados:
    - Herencia: clase base Dispositivo con subclases especializadas.
    - Polimorfismo: cada tipo de dispositivo puede sobreescribir `operar`.
    - Encapsulamiento: estado interno protegido.
"""

from __future__ import annotations
from enum import Enum, auto
from typing import Optional


class EstadoDispositivo(Enum):
    """Estados posibles de un dispositivo de E/S."""
    DISPONIBLE = auto()   # Listo para aceptar operaciones.
    OCUPADO    = auto()   # Procesando una operación.
    FALLO      = auto()   # Error de hardware (requiere atención).


class TipoDispositivo(Enum):
    """Categorías de dispositivos."""
    ENTRADA   = auto()   # Solo lectura desde el dispositivo (teclado, ratón).
    SALIDA    = auto()   # Solo escritura hacia el dispositivo (pantalla, impresora).
    ALMACEN   = auto()   # Lectura y escritura (disco duro, USB).
    RED       = auto()   # Comunicación de red.


class Dispositivo:
    """
    Clase base que representa un dispositivo de E/S genérico.

    Attributes:
        nombre (str): Nombre descriptivo del dispositivo.
        tipo (TipoDispositivo): Categoría del dispositivo.
    """

    def __init__(self, nombre: str, tipo: TipoDispositivo) -> None:
        self._nombre: str = nombre
        self._tipo: TipoDispositivo = tipo
        self._estado: EstadoDispositivo = EstadoDispositivo.DISPONIBLE
        self._pid_solicitante: Optional[int] = None

    # ── Propiedades ──────────────────────────────────────────────────────

    @property
    def nombre(self) -> str:
        return self._nombre

    @property
    def tipo(self) -> TipoDispositivo:
        return self._tipo

    @property
    def estado(self) -> EstadoDispositivo:
        return self._estado

    @property
    def disponible(self) -> bool:
        return self._estado == EstadoDispositivo.DISPONIBLE

    @property
    def pid_solicitante(self) -> Optional[int]:
        """PID del proceso que está usando el dispositivo actualmente."""
        return self._pid_solicitante

    # ── Operaciones ──────────────────────────────────────────────────────

    def solicitar(self, pid: int) -> bool:
        """
        Un proceso solicita el uso del dispositivo.

        Args:
            pid: PID del proceso solicitante.

        Returns:
            True si el dispositivo quedó asignado al proceso.
            False si el dispositivo está ocupado o en fallo.
        """
        if not self.disponible:
            return False
        self._estado = EstadoDispositivo.OCUPADO
        self._pid_solicitante = pid
        return True

    def liberar(self) -> None:
        """El proceso termina de usar el dispositivo; queda disponible."""
        self._estado = EstadoDispositivo.DISPONIBLE
        self._pid_solicitante = None

    def reportar_fallo(self) -> None:
        """Marca el dispositivo como en fallo de hardware."""
        self._estado = EstadoDispositivo.FALLO
        self._pid_solicitante = None

    def reparar(self) -> None:
        """Restablece el dispositivo después de un fallo."""
        self._estado = EstadoDispositivo.DISPONIBLE

    def operar(self, datos: str = "") -> str:
        """
        Ejecuta la operación característica del dispositivo.
        Las subclases deben sobreescribir este método.

        Args:
            datos: Datos de entrada para la operación (puede ser vacío).

        Returns:
            Resultado de la operación como cadena de texto.
        """
        return f"[{self._nombre}] Operación genérica ejecutada."

    # ── Representación ───────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"Dispositivo(nombre='{self._nombre}', tipo={self._tipo.name}, "
            f"estado={self._estado.name})"
        )


# ── Subclases especializadas ─────────────────────────────────────────────

class Teclado(Dispositivo):
    """Dispositivo de entrada: teclado."""

    def __init__(self) -> None:
        super().__init__("Teclado", TipoDispositivo.ENTRADA)

    def operar(self, datos: str = "") -> str:
        return f"[Teclado] Tecla capturada: '{datos}'"


class Disco(Dispositivo):
    """Dispositivo de almacenamiento: disco duro."""

    def __init__(self, nombre: str = "Disco Duro 1", capacidad_gb: int = 500) -> None:
        super().__init__(nombre, TipoDispositivo.ALMACEN)
        self._capacidad_gb: int = capacidad_gb

    @property
    def capacidad_gb(self) -> int:
        return self._capacidad_gb

    def operar(self, datos: str = "") -> str:
        return f"[{self._nombre}] Lectura/escritura: '{datos}'"


class DispositivoRed(Dispositivo):
    """Dispositivo de red: tarjeta de red."""

    def __init__(self, nombre: str = "Tarjeta de Red") -> None:
        super().__init__(nombre, TipoDispositivo.RED)
        self._conectado: bool = False

    @property
    def conectado(self) -> bool:
        return self._conectado

    def conectar(self) -> None:
        self._conectado = True

    def desconectar(self) -> None:
        self._conectado = False

    def operar(self, datos: str = "") -> str:
        if not self._conectado:
            return f"[{self._nombre}] Sin conexión de red."
        return f"[{self._nombre}] Paquete enviado/recibido: '{datos}'"
