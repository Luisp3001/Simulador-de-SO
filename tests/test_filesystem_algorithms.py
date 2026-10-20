"""Pruebas de comportamiento para los algoritmos de administración de archivos (Avance 5)."""

import unittest

from os_simulator.filesystem.almacenamiento import (
    ALGORITMOS_ARCHIVOS,
    ALGORITMOS_DISPONIBLES,
    crear_gestor,
)
from os_simulator.filesystem.continua import DiscoAsignacionContinua


class AsignacionContinuaTests(unittest.TestCase):
    def test_crea_archivo_y_registra_inicio_y_longitud(self):
        disco = DiscoAsignacionContinua(20)
        info = disco.crear_archivo("A.txt", 4)
        self.assertEqual(info["bloque_inicio"], 0)
        self.assertEqual(info["longitud"], 4)
        self.assertEqual(info["bloques"], [0, 1, 2, 3])
        self.assertEqual(disco.bloques_usados, 4)
        self.assertEqual(disco.bloques_disponibles, 16)

    def test_archivos_sucesivos_se_colocan_uno_tras_otro(self):
        disco = DiscoAsignacionContinua(20)
        disco.crear_archivo("A.txt", 4)   # 0-3
        disco.crear_archivo("B.txt", 3)   # 4-6
        disco.crear_archivo("C.txt", 5)   # 7-11
        disco.crear_archivo("D.txt", 2)   # 12-13
        self.assertEqual(disco.archivos["B.txt"]["bloque_inicio"], 4)
        self.assertEqual(disco.archivos["C.txt"]["bloque_inicio"], 7)
        self.assertEqual(disco.archivos["D.txt"]["bloque_inicio"], 12)
        self.assertEqual(disco.bloques_usados, 14)
        self.assertEqual(disco.bloques_disponibles, 6)

    def test_rechaza_si_no_hay_espacio_contiguo_aunque_alcance_la_suma(self):
        # 20 bloques; deja huecos de 3 y 3 (6 libres en total) pero ninguno
        # contiguo de 5: la asignación continua debe rechazar el archivo.
        disco = DiscoAsignacionContinua(20)
        disco.crear_archivo("A.txt", 4)    # 0-3
        disco.crear_archivo("X.txt", 3)    # 4-6   (se libera después)
        disco.crear_archivo("B.txt", 3)    # 7-9
        disco.crear_archivo("Y.txt", 3)    # 10-12 (se libera después)
        disco.crear_archivo("C.txt", 5)    # 13-17
        disco.eliminar_archivo("X.txt")    # libera 4-6 (3 bloques)
        disco.eliminar_archivo("Y.txt")    # libera 10-12 (3 bloques)
        self.assertEqual(disco.bloques_disponibles, 8)   # 6 sueltos + 18-19
        with self.assertRaises(RuntimeError):
            disco.crear_archivo("D.txt", 5)
        # Pero sí cabe uno que quepa en el hueco contiguo más grande (3).
        self.assertTrue(disco.crear_archivo("D.txt", 3))

    def test_rechaza_nombre_duplicado(self):
        disco = DiscoAsignacionContinua(20)
        disco.crear_archivo("A.txt", 4)
        with self.assertRaises(FileExistsError):
            disco.crear_archivo("A.txt", 2)

    def test_rechaza_tamano_mayor_al_disco(self):
        disco = DiscoAsignacionContinua(20)
        with self.assertRaises(RuntimeError):
            disco.crear_archivo("Enorme.bin", 21)

    def test_eliminar_libera_bloques_y_permite_reutilizarlos(self):
        disco = DiscoAsignacionContinua(20)
        disco.crear_archivo("A.txt", 4)
        disco.eliminar_archivo("A.txt")
        self.assertEqual(disco.bloques_usados, 0)
        self.assertNotIn("A.txt", disco.archivos)
        self.assertTrue(disco.crear_archivo("B.txt", 4))
        self.assertEqual(disco.archivos["B.txt"]["bloque_inicio"], 0)

    def test_eliminar_archivo_inexistente_falla(self):
        disco = DiscoAsignacionContinua(20)
        with self.assertRaises(FileNotFoundError):
            disco.eliminar_archivo("fantasma.txt")

    def test_consultar_archivo(self):
        disco = DiscoAsignacionContinua(20)
        disco.crear_archivo("C.txt", 5)
        info = disco.consultar_archivo("C.txt")
        self.assertEqual(info["bloques"], [0, 1, 2, 3, 4])
        self.assertEqual(info["estructura"]["bloque_inicial"], 0)
        self.assertEqual(info["estructura"]["longitud"], 5)
        self.assertEqual(info["estructura"]["bloque_final"], 4)
        with self.assertRaises(FileNotFoundError):
            disco.consultar_archivo("fantasma.txt")

    def test_espacio_disponible_lista_huecos(self):
        disco = DiscoAsignacionContinua(20)
        disco.crear_archivo("A.txt", 4)
        disco.crear_archivo("B.txt", 3)
        disco.eliminar_archivo("A.txt")
        self.assertEqual(disco.bloques_libres(), list(range(0, 4)) + list(range(7, 20)))
        self.assertEqual(disco.huecos_libres(), [
            {"inicio": 0, "longitud": 4},
            {"inicio": 7, "longitud": 13},
        ])

    def test_mayor_hueco_libre(self):
        disco = DiscoAsignacionContinua(20)
        self.assertEqual(disco.mayor_hueco_libre(), 20)
        disco.crear_archivo("A.txt", 4)
        self.assertEqual(disco.mayor_hueco_libre(), 16)

    def test_resetear_vacia_el_disco(self):
        disco = DiscoAsignacionContinua(20)
        disco.crear_archivo("A.txt", 4)
        disco.resetear()
        self.assertEqual(disco.bloques_usados, 0)
        self.assertEqual(disco.archivos, {})
        self.assertTrue(all(b["libre"] for b in disco.bloques()))

    def test_bloques_serializa_el_disco_completo(self):
        disco = DiscoAsignacionContinua(5)
        disco.crear_archivo("A.txt", 2)
        self.assertEqual(disco.bloques(), [
            {"indice": 0, "libre": False, "archivo": "A.txt"},
            {"indice": 1, "libre": False, "archivo": "A.txt"},
            {"indice": 2, "libre": True, "archivo": None},
            {"indice": 3, "libre": True, "archivo": None},
            {"indice": 4, "libre": True, "archivo": None},
        ])

    def test_escenario_del_enunciado_20_bloques(self):
        """Mismo escenario planteado: disco de 20 bloques, A/B/C/D en orden."""
        disco = DiscoAsignacionContinua(20)
        tamaños = {"A.txt": 4, "B.txt": 3, "C.txt": 5, "D.txt": 2}
        for nombre, tam in tamaños.items():
            self.assertTrue(disco.crear_archivo(nombre, tam))
        self.assertEqual(disco.bloques_usados, 14)
        self.assertEqual(disco.bloques_disponibles, 6)
        self.assertEqual(disco.archivos["A.txt"]["bloques"], [0, 1, 2, 3])
        self.assertEqual(disco.archivos["B.txt"]["bloques"], [4, 5, 6])
        self.assertEqual(disco.archivos["C.txt"]["bloques"], [7, 8, 9, 10, 11])
        self.assertEqual(disco.archivos["D.txt"]["bloques"], [12, 13])


class FabricaTests(unittest.TestCase):
    def test_crear_gestor_continua(self):
        gestor = crear_gestor("continua", 20)
        self.assertIsInstance(gestor, DiscoAsignacionContinua)
        self.assertEqual(gestor.clave, "continua")

    def test_algoritmos_anunciados_pero_no_implementados_lanzan_notimplemented(self):
        for clave in ALGORITMOS_ARCHIVOS:
            if clave in ALGORITMOS_DISPONIBLES:
                continue
            with self.assertRaises(NotImplementedError):
                crear_gestor(clave, 20)

    def test_algoritmo_desconocido_lanza_valueerror(self):
        with self.assertRaises(ValueError):
            crear_gestor("no_existe", 20)


if __name__ == "__main__":
    unittest.main()
