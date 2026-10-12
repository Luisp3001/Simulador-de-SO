"""Particiones variables administradas mediante una lista ligada.

Cada nodo de la lista es un proceso (P) o un hueco (H). Al asignar, la
estrategia decide en qué hueco se coloca el proceso:

    First Fit : primer hueco (desde el inicio) donde cabe.
    Next Fit  : como First Fit, pero la búsqueda continúa desde donde terminó
                la última asignación (con retorno circular).
    Best Fit  : el hueco más pequeño donde cabe (recorre toda la lista).
    Worst Fit : el hueco más grande (recorre toda la lista).
"""

from __future__ import annotations

from dataclasses import dataclass

from os_simulator.memory.base import GestorMemoriaBase

ESTRATEGIAS_LISTA = {
    "first_fit": "First Fit",
    "next_fit": "Next Fit",
    "best_fit": "Best Fit",
    "worst_fit": "Worst Fit",
}


@dataclass
class NodoMemoria:
    inicio: int
    tamaño: int
    pid: int | None = None
    siguiente: "NodoMemoria | None" = None

    @property
    def libre(self) -> bool:
        return self.pid is None


class MemoriaListaEnlazada(GestorMemoriaBase):
    def __init__(self, capacidad_total: int, estrategia: str = "first_fit") -> None:
        # Las particiones son variables: cada proceso recibe exactamente su tamaño
        # (la lista ligada NO usa unidad de asignación; eso es solo del mapa de bits).
        super().__init__(capacidad_total)
        self.ultima_decision: str | None = None
        self._estrategia = "first_fit"
        self.estrategia = estrategia
        self._puntero = 0  # dirección donde terminó la última asignación (Next Fit)
        self._cabeza = NodoMemoria(0, capacidad_total)
        self._asignaciones: dict[int, dict] = {}

    # ── Estrategia ───────────────────────────────────────────────────
    @property
    def estrategia(self) -> str:
        return self._estrategia

    @estrategia.setter
    def estrategia(self, valor: str) -> None:
        clave = str(valor).lower().strip()
        if clave not in ESTRATEGIAS_LISTA:
            raise ValueError(
                f"Estrategia desconocida: '{valor}'. Opciones: {', '.join(ESTRATEGIAS_LISTA)}."
            )
        self._estrategia = clave

    @property
    def clave(self) -> str:  # type: ignore[override]
        """Clave pública del gestor: la estrategia activa (first_fit, next_fit, ...)."""
        return self._estrategia

    @property
    def nombre(self) -> str:  # type: ignore[override]
        return f"Lista ligada · {ESTRATEGIAS_LISTA[self._estrategia]}"

    # ── Utilidades ───────────────────────────────────────────────────
    def _iterar(self):
        actual = self._cabeza
        while actual is not None:
            yield actual
            actual = actual.siguiente

    @property
    def memoria_usada(self) -> int:
        return sum(nodo.tamaño for nodo in self._iterar() if not nodo.libre)

    @property
    def asignaciones(self) -> dict[int, dict]:
        return {pid: dict(datos) for pid, datos in self._asignaciones.items()}

    def _elegir_nodo(self, reservada: int) -> NodoMemoria | None:
        nodos = list(self._iterar())
        if self._estrategia == "next_fit":
            # Se parte del nodo que contiene (o sigue a) el puntero y se da la vuelta.
            k = next((i for i, n in enumerate(nodos) if n.inicio + n.tamaño > self._puntero), 0)
            nodos = nodos[k:] + nodos[:k]
        huecos = [n for n in nodos if n.libre]
        candidatos = [n for n in huecos if n.tamaño >= reservada]
        fmt = lambda lista: ", ".join(f"{n.tamaño} MB@{n.inicio}" for n in lista) or "ninguno"
        nombre = ESTRATEGIAS_LISTA[self._estrategia]
        if not candidatos:
            self.ultima_decision = f"{nombre}: ningún hueco ({fmt(huecos)}) alcanza para {reservada} MB."
            return None
        if self._estrategia == "best_fit":
            elegido = min(candidatos, key=lambda n: n.tamaño)       # empate → el primero
            self.ultima_decision = (f"{nombre}: revisó toda la lista (huecos: {fmt(huecos)}) y eligió el "
                                    f"más pequeño donde cabe: {elegido.tamaño} MB@{elegido.inicio}.")
        elif self._estrategia == "worst_fit":
            elegido = max(candidatos, key=lambda n: n.tamaño)       # empate → el primero
            self.ultima_decision = (f"{nombre}: revisó toda la lista (huecos: {fmt(huecos)}) y eligió siempre "
                                    f"el más grande: {elegido.tamaño} MB@{elegido.inicio}.")
        else:                                                         # first_fit / next_fit
            elegido = candidatos[0]
            vistos = huecos[: huecos.index(elegido) + 1]
            desde = f" desde la dirección {self._puntero}" if self._estrategia == "next_fit" else ""
            self.ultima_decision = (f"{nombre}: recorrió la lista{desde} (huecos vistos: {fmt(vistos)}) "
                                    f"y tomó el primero donde cabe: {elegido.tamaño} MB@{elegido.inicio}.")
        return elegido

    # ── Operaciones ──────────────────────────────────────────────────
    def asignar(self, pid: int, cantidad_mb: int) -> bool:
        self._validar_solicitud(pid, cantidad_mb)
        reservada = cantidad_mb   # tamaño exacto, sin redondeo a unidades
        self.ultima_decision = None
        nodo = self._elegir_nodo(reservada)
        if nodo is None:
            return False
        if nodo.tamaño > reservada:
            nodo.siguiente = NodoMemoria(
                nodo.inicio + reservada,
                nodo.tamaño - reservada,
                siguiente=nodo.siguiente,
            )
        nodo.tamaño = reservada
        nodo.pid = pid
        self._puntero = nodo.inicio + nodo.tamaño
        self._asignaciones[pid] = {
            "solicitada_mb": cantidad_mb,
            "reservada_mb": reservada,
            "inicio": nodo.inicio,
        }
        return True

    def liberar(self, pid: int) -> int:
        datos = self._asignaciones.pop(pid, None)
        if datos is None:
            return 0
        for nodo in self._iterar():
            if nodo.pid == pid:
                nodo.pid = None
                break
        self._fusionar_libres()
        return datos["solicitada_mb"]

    def _fusionar_libres(self) -> None:
        actual = self._cabeza
        while actual.siguiente is not None:
            if actual.libre and actual.siguiente.libre:
                actual.tamaño += actual.siguiente.tamaño
                actual.siguiente = actual.siguiente.siguiente
            else:
                actual = actual.siguiente

    def resetear(self) -> None:
        self._cabeza = NodoMemoria(0, self.capacidad_total)
        self._asignaciones.clear()
        self._puntero = 0
        self.ultima_decision = None

    def bloques(self) -> list[dict]:
        return [
            {"inicio": n.inicio, "tamaño": n.tamaño, "libre": n.libre, "pid": n.pid}
            for n in self._iterar()
        ]

    def mayor_hueco_libre(self) -> int:
        return max((n.tamaño for n in self._iterar() if n.libre), default=0)

    def estado(self) -> dict:
        datos = super().estado()
        datos["estrategia"] = self._estrategia
        datos["puntero_mb"] = self._puntero if self._estrategia == "next_fit" else None
        datos["decision"] = self.ultima_decision
        return datos
