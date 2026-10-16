# 🔥 BALJ OS

BALJ OS es un **Simulador de Sistema Operativo** interactivo con fines educativos. Su objetivo es demostrar visualmente el ciclo de vida de los procesos, el funcionamiento de un Kernel moderno, y cómo los distintos algoritmos de planificación (schedulers) administran la CPU.

Cuenta con un backend desarrollado en Python (con Flask para la API) y un frontend moderno y responsivo (HTML/CSS/JS) donde los usuarios pueden interactuar en tiempo real con el sistema operativo simulado.

---

## 🏗️ Estructura del Proyecto

El proyecto está dividido en un núcleo de simulación en Python (backend) y una interfaz de usuario web (frontend).

### 1. Núcleo del Simulador (Backend)
Ubicado en el directorio `os_simulator/`, implementa toda la lógica pura del sistema operativo sin dependencias web:

* **`core/`**
  * `kernel.py`: El corazón del SO. Instancia y orquesta la CPU, Memoria, I/O, Sistema de Archivos y Planificador de procesos. Contiene el bucle principal (`avanzar_ciclo()`).
  * `cpu.py`: Simula el procesador. Ejecuta los ciclos de reloj descontando el tiempo restante (burst time) del proceso activo.
* **`processes/`**
  * `process.py`: Define la clase `Proceso` (PID, nombre, memoria requerida, ráfaga de CPU `burst_time`, `nice_value`, estado) y la máquina de estados (`NUEVO`, `LISTO`, `EJECUTANDO`, `BLOQUEADO`, `TERMINADO`).
  * `schedulers.py`: Implementa el patrón Strategy. Contiene la interfaz base `SchedulerBase` y todas las clases concretas de los **algoritmos de planificación**.
* **`memory/` & `hardware/` & `fs/`**
  * Manejadores para la memoria RAM simulada (asignación/liberación), dispositivos de Entrada/Salida, y un Virtual File System (VFS) básico en memoria.

### 2. API y Servidor
* **`server.py`**: Servidor Flask que expone el motor de `os_simulator` mediante una API RESTful (`/api/process`, `/api/state`, `/api/scheduler`). Mantiene una única instancia global del Kernel y permite a los clientes enviar comandos.

### 3. Interfaz de Usuario (Frontend)
* **`index.html`**: Estructura de la aplicación a 3 columnas.
* **`style.css`**: Tema visual "Modern High-Contrast Tech Theme", con un diseño oscuro (slate), detalles vibrantes y feedback visual por colores.
* **`script.js`**: Lógica de renderizado. Realiza *polling* (peticiones periódicas) al endpoint `/api/state` del servidor, actualiza la cola de procesos, el anillo de carga de CPU y la consola del sistema (log).

---

## 🧠 Algoritmos de Planificación Implementados

El simulador implementa 7 algoritmos clásicos y avanzados de planificación de procesos:

1. **FCFS (First Come, First Served)**: No preemptivo. El proceso que llega primero se ejecuta hasta terminar.
2. **SJF (Shortest Job First)**: Preemptivo. Se selecciona siempre el proceso en la cola con el **menor tiempo restante** (`burst_time` o `remaining_time`).
3. **Round Robin (Turno Circular)**: Preemptivo. Cada proceso recibe un tiempo máximo de CPU continuo llamado **Quantum**. Si no termina en ese tiempo, es expulsado y mandado al final de la cola.
4. **Por Prioridad (`nice_value`)**: Preemptivo. Se escoge el proceso con la prioridad más alta (en este SO se usa el estándar Unix `nice_value` donde un número **menor** significa **mayor urgencia**).
5. **Colas Múltiples con Retroalimentación (Multilevel Feedback Queue)**: Preemptivo. Los procesos nuevos entran en la cola de mayor prioridad (Nivel 0) con un quantum corto. Si consumen su quantum sin terminar, son degradados a la siguiente cola inferior (Nivel 1, Nivel 2...) con quantums progresivamente más largos.
6. **Planificación Garantizada (Fair Share)**: Preemptivo. Promete dar a cada proceso equitativamente `1/N` de la CPU. Calcula el ratio de (Tiempo usado / Tiempo al que tiene derecho) y planifica siempre al proceso con el ratio más bajo.
7. **A Dos Niveles**: Preemptivo. Simula tener procesos en una cola "en memoria" (rápidos) y procesos en una cola "suspendida en disco". Los sube a memoria y los intercala para evitar sobrecargar la RAM.

---

## ⚙️ Flujo del Sistema (Cómo funciona)

### 1. Creación de Procesos
1. El usuario llena el modal web y envía una petición POST a `/api/process`.
2. El `Kernel` recibe la petición, intenta reservar la **memoria RAM** requerida.
3. Si hay memoria suficiente, instancia la clase `Proceso`, lo marca como estado **LISTO** y lo inserta en la cola de procesos.

### 2. Avanzar Ciclos (Tick del Reloj)
Cada vez que el usuario presiona "Avanzar Ciclo", el Kernel ejecuta el método `avanzar_ciclo()`:
1. **Preempción**: Si el scheduler es preemptivo, verifica si el proceso actual en CPU debe salir (e.g., porque se le acabó el Quantum en Round Robin, o porque llegó un proceso más importante en Prioridades). Si es así, se le interrumpe, pasa a estado **LISTO** y vuelve a la cola.
2. **Despacho (Dispatch)**: Si la CPU está libre, el Kernel le pide al `scheduler.seleccionar_siguiente()` que decida qué proceso en la cola debe ejecutarse ahora. El seleccionado pasa a estado **EJECUTANDO** y se monta en la CPU.
3. **Ejecución**: La CPU gasta 1 ciclo, decrementando el `remaining_time` del proceso actual.

### 3. Terminación
Si tras ejecutar un ciclo el `remaining_time` llega a 0:
1. El proceso finaliza (estado **TERMINADO**).
2. Se libera su memoria RAM (queda disponible para otros procesos).
3. Se calculan las métricas finales (*Turnaround Time* y *Waiting Time*).
4. El proceso se mueve a la tabla de procesos completados en la interfaz para analizar las estadísticas (Promedios).

---

## 🧩 Algoritmos de Administración de Memoria

El gestor de RAM también implementa el patrón Strategy y permite comparar tres
formas de asignación desde el panel **Memoria RAM**:

1. **Mapa de bits:** divide los 2048 MB en 64 marcos de 64 MB. Una asignación
   puede ocupar marcos no contiguos y puede producir fragmentación interna.
2. **Lista enlazada (First Fit):** mantiene nodos libres y ocupados de tamaño
   variable. Divide huecos al asignar y fusiona nodos libres adyacentes al liberar.
3. **Sistema de asociados (Buddy):** redondea cada solicitud a una potencia de
   dos, divide bloques y vuelve a fusionar asociados libres recursivamente.

La interfaz muestra la ubicación real de cada asignación, coloreada por PID, y
las métricas de memoria solicitada, reservada, fragmentación interna,
fragmentación externa y mayor bloque utilizable.

Por seguridad, el algoritmo solo puede cambiarse cuando no hay ningún proceso
en la CPU ni en la cola. La API devuelve `409 Conflict` si se intenta cambiarlo
con procesos activos.

### API de memoria

```http
GET /api/memory/strategy
POST /api/memory/strategy
Content-Type: application/json

{"tipo": "buddy"}
```

---

## 🧠 Módulo de memoria independiente (Avance 3)

Se accede desde la pestaña **Administración de memoria** (independiente de CPU y planificador; no requiere iniciar el SO).

* **RAM**: constante (2048 MB), no editable.
* **Unidad de asignación**: la define el usuario (debe dividir exactamente la RAM). El módulo permanece bloqueado hasta definirla.
* **Mapa de bits**: inicia en `0` (libre); cada proceso pone en `1` sus casillas.
* **Fórmulas**:
  * Malla = `RAM / unidad`
  * Casillas de un proceso = `⌈tamaño / unidad⌉`
* Los procesos se ubican en la primera secuencia de ceros consecutivos (First Fit sobre el mapa).
* API: `/api/memlab` (GET), `/api/memlab/unit`, `/api/memlab/strategy`, `/api/memlab/process` (POST/DELETE), `/api/memlab/reset`.

### Avance 3 · Sección 6 — navegación y capturas
Pestaña **Administración de memoria**: Mapa de bits · Lista ligada (First/Next/Best/Worst Fit) · Sistema de asociados · Reemplazo de páginas (OPT, NRU, FIFO, LRU). La unidad de asignación solo existe en el mapa de bits.
Las capturas para el informe están en `capturas/`. Pruebas: `python tests/test_memory_algorithms.py` (con `PYTHONPATH=.`).

---

## 🔌 Dispositivos de E/S (USB)

Pestaña **Dispositivos de E/S**: lista los dispositivos USB conectados (mouse, teclado, memoria USB, parlantes, audífonos, proyector, etc.) con la información del **driver** ligado a cada uno (driver, proveedor, versión, fecha, archivo INF, firma y drivers de sus interfaces). Inicia con «No se ha conectado ningún dispositivo» y se actualiza sola al conectar o desconectar.

* **Windows (real):** usa **WMI** (`Win32_PnPEntity`, `Win32_DiskDrive`) para listar y **pywin32** (`pythoncom`) para COM; el driver se lee del registro de Windows (rápido: `Win32_PnPSignedDriver` tarda decenas de segundos y no se usa). Los cambios se detectan por evento (`Win32_DeviceChangeEvent`), agrupando la ráfaga de eventos de cada USB en un solo escaneo.
  Instalación: `uv sync` (o `pip install wmi pywin32`). Ejecutar con `uv run python server.py`.
* Los dispositivos que ya estaban conectados al abrir el simulador se ocultan por defecto (casilla «Incluir los dispositivos ya conectados» para verlos).
* **Linux:** lee `/sys/bus/usb/devices`. **Sin USB accesible:** modo simulado con botones para conectar/desconectar dispositivos de prueba.
* Forzar el origen: variable de entorno `USB_BACKEND` = `wmi` | `sysfs` | `sim` (por defecto `auto`). En PowerShell: `$env:USB_BACKEND="sim"; uv run python server.py`.
* API: `GET /api/usb` (listado + `version` que cambia con cada conexión/desconexión).
* **Medir tiempos (Windows):** `uv run python diagnostico_usb.py`. Con `USB_DEBUG=1` el servidor imprime la duración de cada escaneo y la latencia evento→lista.
