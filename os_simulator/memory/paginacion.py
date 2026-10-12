"""Simulador de algoritmos de reemplazo de páginas: OPT, NRU, FIFO y LRU.

Recibe una cadena de referencias (opcionalmente con 'w' para marcar escrituras,
necesario para los bits R/M del NRU) y devuelve la traza completa paso a paso.
"""

from __future__ import annotations

import re

ALGORITMOS_PAGINAS = {
    "opt": "OPT (Óptimo)",
    "nru": "NRU (No usada recientemente)",
    "fifo": "FIFO (Primera en entrar, primera en salir)",
    "lru": "LRU (Menos recientemente usada)",
}

MAX_REFERENCIAS = 60
MAX_MARCOS = 10
MAX_PAGINA = 99
_INF = float("inf")


def parsear_referencias(texto: str) -> list[tuple[int, bool]]:
    """'7 0w 1' → [(7, False), (0, True), (1, False)]."""
    tokens = [t for t in re.split(r"[\s,;]+", (texto or "").strip()) if t]
    if not tokens:
        raise ValueError("Escribe al menos una referencia de página.")
    if len(tokens) > MAX_REFERENCIAS:
        raise ValueError(f"Máximo {MAX_REFERENCIAS} referencias.")
    refs = []
    for token in tokens:
        m = re.fullmatch(r"(\d+)([wWrR]?)", token)
        if not m:
            raise ValueError(
                f"Referencia inválida: '{token}'. Usa números separados por espacios "
                "(agrega 'w' para una escritura, ej. 3w)."
            )
        pagina = int(m.group(1))
        if pagina > MAX_PAGINA:
            raise ValueError(f"Las páginas deben estar entre 0 y {MAX_PAGINA}.")
        refs.append((pagina, m.group(2).lower() == "w"))
    return refs


def _elegir_victima(alg: str, slots: list[dict], refs: list, t: int) -> tuple[int, str]:
    indices = range(len(slots))
    if alg == "fifo":
        pos = min(indices, key=lambda i: slots[i]["carga"])
        return pos, (f"FIFO: sale la página {slots[pos]['pagina']}, la que lleva más tiempo "
                     f"en memoria (cargada en la referencia {slots[pos]['carga'] + 1}).")
    if alg == "lru":
        pos = min(indices, key=lambda i: slots[i]["uso"])
        return pos, (f"LRU: sale la página {slots[pos]['pagina']}, la menos recientemente "
                     f"usada (último uso en la referencia {slots[pos]['uso'] + 1}).")
    if alg == "opt":
        def proximo(i: int) -> float:
            pagina = slots[i]["pagina"]
            return next((j for j in range(t + 1, len(refs)) if refs[j][0] == pagina), _INF)
        pos = max(indices, key=lambda i: (proximo(i), -i))
        d = proximo(pos)
        cuando = "no se vuelve a usar" if d == _INF else f"se usará en la referencia {int(d) + 1}"
        return pos, f"OPT: sale la página {slots[pos]['pagina']} porque {cuando} (la más lejana)."
    # NRU: clase = 2*R + M; sale la de menor clase (desempate: la más antigua)
    pos = min(indices, key=lambda i: (2 * slots[i]["r"] + slots[i]["m"], slots[i]["carga"]))
    s = slots[pos]
    return pos, (f"NRU: clase {2 * s['r'] + s['m']} (R={s['r']}, M={s['m']}) es la más baja "
                 f"presente; sale la página {s['pagina']}.")


def simular(algoritmo: str, refs: list[tuple[int, bool]], marcos: int,
            intervalo_nru: int = 4) -> dict:
    algoritmo = algoritmo.lower().strip()
    if algoritmo not in ALGORITMOS_PAGINAS:
        raise ValueError(f"Algoritmo desconocido: '{algoritmo}'.")
    if not 1 <= marcos <= MAX_MARCOS:
        raise ValueError(f"El número de marcos debe estar entre 1 y {MAX_MARCOS}.")
    if intervalo_nru < 1:
        raise ValueError("El intervalo de limpieza del bit R debe ser al menos 1.")

    slots: list[dict | None] = [None] * marcos
    pasos, fallas = [], 0
    for t, (pagina, escritura) in enumerate(refs):
        pos = next((i for i, s in enumerate(slots) if s and s["pagina"] == pagina), None)
        falla = pos is None
        saliente = None
        if not falla:
            slots[pos].update(r=1, uso=t)
            if escritura:
                slots[pos]["m"] = 1
            detalle = f"Acierto: la página {pagina} ya está en el marco {pos}."
        else:
            fallas += 1
            libre = next((i for i, s in enumerate(slots) if s is None), None)
            if libre is not None:
                pos = libre
                detalle = f"Falla de página: se carga la {pagina} en el marco libre {pos}."
            else:
                pos, motivo = _elegir_victima(algoritmo, slots, refs, t)
                saliente = slots[pos]["pagina"]
                detalle = f"Falla de página. {motivo} Entra la {pagina}."
            slots[pos] = {"pagina": pagina, "r": 1, "m": 1 if escritura else 0,
                          "carga": t, "uso": t}

        paso = {
            "ref": pagina,
            "escritura": escritura,
            "falla": falla,
            "posicion": pos,
            "saliente": saliente,
            "marcos": [None if s is None else {"pagina": s["pagina"], "r": s["r"], "m": s["m"]}
                       for s in slots],
            "detalle": detalle,
        }
        if algoritmo == "lru":
            orden = sorted((s for s in slots if s), key=lambda s: s["uso"])
            paso["recencia"] = [s["pagina"] for s in orden]  # menos → más reciente
        if algoritmo == "nru" and (t + 1) % intervalo_nru == 0:
            for s in slots:
                if s:
                    s["r"] = 0
            paso["limpieza_r"] = True
            paso["detalle"] += " (Tic de reloj: se ponen en 0 todos los bits R.)"
        pasos.append(paso)

    total = len(refs)
    return {
        "algoritmo": algoritmo,
        "nombre": ALGORITMOS_PAGINAS[algoritmo],
        "marcos": marcos,
        "intervalo_nru": intervalo_nru,
        "pasos": pasos,
        "total": total,
        "fallas": fallas,
        "aciertos": total - fallas,
        "tasa_fallas": round(fallas / total * 100, 1),
        "tasa_aciertos": round((total - fallas) / total * 100, 1),
    }


def comparar(refs: list[tuple[int, bool]], marcos: int, intervalo_nru: int = 4) -> list[dict]:
    return [
        {"algoritmo": clave, "nombre": nombre,
         "fallas": simular(clave, refs, marcos, intervalo_nru)["fallas"]}
        for clave, nombre in ALGORITMOS_PAGINAS.items()
    ]
