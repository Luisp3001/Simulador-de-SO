"""
filesystem/filesystem.py
========================
Módulo que modela un Sistema de Archivos jerárquico simplificado.

Implementa un árbol de nodos (archivos y directorios) que representa
la estructura de un sistema de archivos tipo Unix.

Principios OOP aplicados:
    - Composición: el FileSystem está compuesto de nodos (Archivo, Directorio).
    - Herencia: Archivo y Directorio heredan de NodoFS.
    - Patrón Composite: los directorios pueden contener otros nodos.
"""

from __future__ import annotations
from typing import Optional
from datetime import datetime


# ── Nodos del árbol de archivos ──────────────────────────────────────────

class NodoFS:
    """
    Clase base de un nodo en el sistema de archivos.

    Attributes:
        nombre (str): Nombre del nodo (archivo o directorio).
        padre (Optional[Directorio]): Directorio padre, None para la raíz.
    """

    def __init__(self, nombre: str, padre: Optional[Directorio] = None) -> None:
        self._nombre: str = nombre
        self._padre: Optional[Directorio] = padre
        self._fecha_creacion: datetime = datetime.now()

    @property
    def nombre(self) -> str:
        return self._nombre

    @property
    def padre(self) -> Optional[Directorio]:
        return self._padre

    @property
    def fecha_creacion(self) -> datetime:
        return self._fecha_creacion

    @property
    def ruta_absoluta(self) -> str:
        """Ruta completa desde la raíz hasta este nodo."""
        if self._padre is None:
            return "/" + self._nombre
        return self._padre.ruta_absoluta.rstrip("/") + "/" + self._nombre

    def es_directorio(self) -> bool:
        """Retorna True si el nodo es un directorio."""
        return False

    def __repr__(self) -> str:
        return f"NodoFS('{self._nombre}')"


class Archivo(NodoFS):
    """
    Representa un archivo en el sistema de archivos.

    Attributes:
        contenido (str): Contenido textual del archivo.
        extension (str): Extensión del archivo (ej. 'txt', 'py').
    """

    def __init__(
        self,
        nombre: str,
        contenido: str = "",
        padre: Optional[Directorio] = None,
    ) -> None:
        super().__init__(nombre, padre)
        self._contenido: str = contenido

    @property
    def contenido(self) -> str:
        return self._contenido

    @contenido.setter
    def contenido(self, nuevo_contenido: str) -> None:
        self._contenido = nuevo_contenido

    @property
    def tamaño_bytes(self) -> int:
        """Tamaño del archivo en bytes (basado en el contenido)."""
        return len(self._contenido.encode("utf-8"))

    @property
    def extension(self) -> str:
        partes = self._nombre.rsplit(".", 1)
        return partes[1] if len(partes) > 1 else ""

    def leer(self) -> str:
        """Retorna el contenido del archivo."""
        return self._contenido

    def escribir(self, texto: str) -> None:
        """Sobreescribe el contenido del archivo."""
        self._contenido = texto

    def adjuntar(self, texto: str) -> None:
        """Añade texto al final del contenido existente."""
        self._contenido += texto

    def __repr__(self) -> str:
        return f"Archivo('{self._nombre}', {self.tamaño_bytes}B)"


class Directorio(NodoFS):
    """
    Representa un directorio (carpeta) en el sistema de archivos.
    Puede contener otros Archivos y Directorios (patrón Composite).
    """

    def __init__(
        self,
        nombre: str,
        padre: Optional[Directorio] = None,
    ) -> None:
        super().__init__(nombre, padre)
        self._hijos: dict[str, NodoFS] = {}

    @property
    def hijos(self) -> dict[str, NodoFS]:
        """Mapa de nombre → nodo hijo (solo lectura)."""
        return dict(self._hijos)

    def es_directorio(self) -> bool:
        return True

    def agregar(self, nodo: NodoFS) -> None:
        """
        Agrega un archivo o directorio a este directorio.

        Raises:
            FileExistsError: Si ya existe un nodo con ese nombre.
        """
        if nodo.nombre in self._hijos:
            raise FileExistsError(
                f"Ya existe '{nodo.nombre}' en '{self.ruta_absoluta}'"
            )
        self._hijos[nodo.nombre] = nodo
        # Establece la referencia al padre
        nodo._padre = self

    def eliminar(self, nombre: str) -> None:
        """
        Elimina un nodo hijo por nombre.

        Raises:
            FileNotFoundError: Si el nodo no existe.
        """
        if nombre not in self._hijos:
            raise FileNotFoundError(
                f"'{nombre}' no encontrado en '{self.ruta_absoluta}'"
            )
        del self._hijos[nombre]

    def buscar(self, nombre: str) -> Optional[NodoFS]:
        """Busca un hijo directo por nombre. Retorna None si no existe."""
        return self._hijos.get(nombre)

    def listar(self) -> list[str]:
        """Retorna los nombres de los hijos ordenados alfabéticamente."""
        return sorted(self._hijos.keys())

    def __repr__(self) -> str:
        return f"Directorio('{self._nombre}', {len(self._hijos)} hijos)"


# ── Sistema de Archivos principal ────────────────────────────────────────

class SistemaArchivos:
    """
    Sistema de archivos jerárquico del sistema operativo.

    Gestiona el árbol de directorios y archivos, y provee
    operaciones de alto nivel (crear, eliminar, leer, escribir).
    """

    def __init__(self) -> None:
        # Directorio raíz del sistema
        self._raiz: Directorio = Directorio("raiz")
        self._inicializar_estructura_base()

    def _inicializar_estructura_base(self) -> None:
        """Crea la estructura de directorios inicial del SO."""
        for nombre in ["bin", "usr", "tmp", "etc"]:
            self._raiz.agregar(Directorio(nombre))

        # Archivo de configuración del kernel
        etc = self._raiz.buscar("etc")
        if isinstance(etc, Directorio):
            etc.agregar(Archivo("kernel.conf", "# Configuración del kernel\nversion=1.0\n"))
            etc.agregar(Archivo("init.conf",   "# Configuración de arranque\nrunlevel=3\n"))

    # ── Propiedades ──────────────────────────────────────────────────────

    @property
    def raiz(self) -> Directorio:
        return self._raiz

    # ── Operaciones ──────────────────────────────────────────────────────

    def _navegar(self, ruta: str) -> Optional[NodoFS]:
        """
        Navega el árbol siguiendo una ruta separada por '/'.

        Args:
            ruta: Ruta absoluta (ej. "bin/ls") o solo el nombre para la raíz.

        Returns:
            El nodo encontrado, o None si no existe.
        """
        partes = [p for p in ruta.strip("/").split("/") if p]
        nodo_actual: NodoFS = self._raiz

        for parte in partes:
            if not isinstance(nodo_actual, Directorio):
                return None
            nodo_actual = nodo_actual.buscar(parte)
            if nodo_actual is None:
                return None

        return nodo_actual

    def crear_archivo(self, ruta_directorio: str, nombre: str, contenido: str = "") -> Archivo:
        """
        Crea un nuevo archivo en el directorio especificado.

        Args:
            ruta_directorio: Ruta del directorio destino (vacía para la raíz).
            nombre: Nombre del archivo a crear.
            contenido: Contenido inicial del archivo.

        Returns:
            El archivo recién creado.
        """
        directorio = self._raiz if not ruta_directorio else self._navegar(ruta_directorio)
        if not isinstance(directorio, Directorio):
            raise NotADirectoryError(f"'{ruta_directorio}' no es un directorio válido.")
        nuevo_archivo = Archivo(nombre, contenido)
        directorio.agregar(nuevo_archivo)
        return nuevo_archivo

    def crear_directorio(self, ruta_padre: str, nombre: str) -> Directorio:
        """Crea un nuevo subdirectorio dentro del directorio indicado."""
        padre = self._raiz if not ruta_padre else self._navegar(ruta_padre)
        if not isinstance(padre, Directorio):
            raise NotADirectoryError(f"'{ruta_padre}' no es un directorio válido.")
        nuevo_dir = Directorio(nombre)
        padre.agregar(nuevo_dir)
        return nuevo_dir

    def leer_archivo(self, ruta: str) -> str:
        """Lee y retorna el contenido de un archivo."""
        nodo = self._navegar(ruta)
        if not isinstance(nodo, Archivo):
            raise FileNotFoundError(f"Archivo '{ruta}' no encontrado.")
        return nodo.leer()

    def escribir_archivo(self, ruta: str, contenido: str) -> None:
        """Escribe contenido en un archivo existente (sobreescribe)."""
        nodo = self._navegar(ruta)
        if not isinstance(nodo, Archivo):
            raise FileNotFoundError(f"Archivo '{ruta}' no encontrado.")
        nodo.escribir(contenido)

    def listar_directorio(self, ruta: str = "") -> list[str]:
        """Lista los contenidos de un directorio."""
        nodo = self._raiz if not ruta else self._navegar(ruta)
        if not isinstance(nodo, Directorio):
            raise NotADirectoryError(f"'{ruta}' no es un directorio.")
        return nodo.listar()

    def eliminar(self, ruta_padre: str, nombre: str) -> None:
        """Elimina un archivo o directorio del sistema."""
        padre = self._raiz if not ruta_padre else self._navegar(ruta_padre)
        if not isinstance(padre, Directorio):
            raise NotADirectoryError(f"'{ruta_padre}' no es un directorio.")
        padre.eliminar(nombre)

    def __repr__(self) -> str:
        return f"SistemaArchivos(raiz='{self._raiz.nombre}', hijos={self._raiz.listar()})"
