"""
main.py
os_simulator/main.py
====================
Punto de entrada del Simulador de Sistema Operativo — BALJ OS.
Demuestra el ciclo de vida completo del sistema operativo simulado.

Uso:
    python main.py
"""

from os_simulator.core.kernel import Kernel
from os_simulator.hardware.device import Disco


def separador(titulo: str = "") -> None:
    linea = "═" * 60
    if titulo:
        print(f"\n{linea}")
        print(f"  {titulo}")
        print(f"{linea}")
    else:
        print(f"\n{linea}\n")


def main() -> None:
    # ── 1. Crear e inicializar el Kernel ─────────────────────────────────
    separador("BALJ OS — Demo de inicio")
    kernel = Kernel(nombre="BALJ OS", version="0.1.0", ram_mb=2048)
    kernel.arrancar()

    for entrada in kernel.ultimo_log(6):
        print(entrada)

    # ── 2. Crear procesos con distintas prioridades ───────────────────────
    separador("Creando procesos")
    p1 = kernel.crear_proceso("sistema_base",   memoria_mb=256,  burst_time=4, nice_value=-5)
    p2 = kernel.crear_proceso("editor_texto",   memoria_mb=128,  burst_time=3, nice_value=0)
    p3 = kernel.crear_proceso("reproductor_mp3",memoria_mb=96,   burst_time=6, nice_value=5)
    p4 = kernel.crear_proceso("compilador",     memoria_mb=512,  burst_time=8, nice_value=-2)

    for entrada in kernel.ultimo_log(4):
        print(entrada)

    # ── 3. Estado del sistema ─────────────────────────────────────────────
    separador("Estado del sistema")
    estado = kernel.estado()
    mem = estado["memoria"]
    print(f"  RAM: {mem['usada_mb']} / {mem['total_mb']} MB usados ({mem['uso_pct']}%)")
    print(f"  Procesos en cola: {len(estado['procesos_en_cola'])}")
    for p in estado["procesos_en_cola"]:
        print(f"    PID {p['pid']:>3} | {p['nombre']:<20} | {p['estado']}")

    # ── 4. Avanzar ciclos del reloj ───────────────────────────────────────
    separador("Avanzando ciclos de reloj")
    for _ in range(4):
        kernel.avanzar_ciclo()
        estado = kernel.estado()
        cpu = estado["cpu"]
        mem = estado["memoria"]
        en_ejecucion = cpu["proceso_actual"] or "— (inactivo) —"
        print(
            f"  Ciclo {estado['kernel']['ciclo']:>3} | CPU: {en_ejecucion:<20} "
            f"| RAM usada: {mem['usada_mb']:>5} MB ({mem['uso_pct']:>5.1f}%)"
        )

    # ── 5. Dispositivos de E/S ────────────────────────────────────────────
    separador("Dispositivos de E/S")
    # Registrar un segundo disco
    kernel.registrar_dispositivo("disco2", Disco("Disco Duro 2", capacidad_gb=1000))

    for clave, info in kernel.estado()["dispositivos"].items():
        print(f"  {clave:<12} | {info['nombre']:<20} | {info['estado']}")

    # ── 6. Sistema de Archivos ─────────────────────────────────────────────
    separador("Sistema de Archivos")
    fs = kernel.sistema_archivos

    # Crear estructura de usuario
    fs.crear_directorio("usr", "local")
    fs.crear_archivo("usr/local", "readme.txt", "# BALJ OS\nBienvenido al simulador.\n")
    fs.crear_archivo("tmp", "sesion.log", "Sesión iniciada.\n")

    # Leer un archivo
    contenido_conf = fs.leer_archivo("etc/kernel.conf")
    print(f"  /etc/kernel.conf:\n    {contenido_conf.strip()}")

    # Listar directorios raíz
    print(f"\n  Contenido de /raiz: {fs.listar_directorio()}")
    print(f"  Contenido de /usr:  {fs.listar_directorio('usr')}")

    # ── 7. Terminar proceso manualmente ───────────────────────────────────
    separador("Terminación manual de proceso")
    if p2:
        exito = kernel.terminar_proceso(p2.pid)
        print(f"  Terminar PID {p2.pid} ('{p2.nombre}'): {'✓' if exito else '✗'}")
        for entrada in kernel.ultimo_log(2):
            print(f"  {entrada}")

    # ── 8. Detener el sistema ──────────────────────────────────────────────
    separador("Apagando el sistema")
    kernel.detener()
    for entrada in kernel.ultimo_log(2):
        print(entrada)

    separador()
    print("  Simulación completada. Estado final del Kernel:")
    print(f"  {kernel}")


if __name__ == "__main__":
    main()
