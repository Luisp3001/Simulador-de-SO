"""Pruebas de comportamiento para los tres administradores de RAM."""

import unittest

from os_simulator.core.kernel import Kernel
from os_simulator.memory.bitmap import MemoriaBitmap
from os_simulator.memory.buddy import MemoriaBuddy
from os_simulator.memory.memory import Memoria, crear_gestor
from os_simulator.memory.paginacion import parsear_referencias, simular
from os_simulator.memory.linked_list import MemoriaListaEnlazada


class BitmapTests(unittest.TestCase):
    def test_redondea_a_marcos_y_los_libera(self):
        memoria = MemoriaBitmap(2048)
        self.assertTrue(memoria.asignar(1, 100))
        self.assertEqual(memoria.estado()["reservada_mb"], 128)
        self.assertEqual(memoria.estado()["fragmentacion_interna_mb"], 28)
        self.assertEqual(memoria.liberar(1), 100)
        self.assertEqual(memoria.memoria_usada, 0)


class BitmapUnidadTests(unittest.TestCase):
    def test_malla_es_ram_entre_unidad_y_empieza_en_ceros(self):
        memoria = MemoriaBitmap(2048, unidad=128)
        self.assertEqual(memoria.total_unidades, 2048 // 128)
        self.assertEqual(memoria.mapa_bits, [0] * 16)

    def test_proceso_ocupa_techo_de_tamano_entre_unidad_bits_en_uno(self):
        memoria = MemoriaBitmap(2048, unidad=64)
        self.assertTrue(memoria.asignar(1, 100))   # ceil(100/64) = 2
        self.assertTrue(memoria.asignar(2, 64))    # ceil(64/64)  = 1
        self.assertEqual(memoria.mapa_bits[:4], [1, 1, 1, 0])
        self.assertEqual(sum(memoria.mapa_bits), 3)
        memoria.liberar(1)
        self.assertEqual(memoria.mapa_bits[:4], [0, 0, 1, 0])

    def test_busca_ceros_consecutivos(self):
        memoria = MemoriaBitmap(512, unidad=64)    # 8 casillas
        for pid in (1, 2, 3, 4):
            memoria.asignar(pid, 128)              # 2 casillas cada uno
        memoria.liberar(2)                         # hueco de 2 en casillas 2-3
        self.assertFalse(memoria.asignar(5, 192))  # necesita 3 seguidas
        self.assertTrue(memoria.asignar(5, 128))
        self.assertEqual(memoria.mapa_bits, [1] * 8)

    def test_unidad_debe_dividir_la_ram(self):
        with self.assertRaises(ValueError):
            MemoriaBitmap(2048, unidad=100)


class MemoriaUnidadTests(unittest.TestCase):
    def test_unidad_no_definida_hasta_configurarla_y_no_cambia_con_procesos(self):
        memoria = Memoria(2048)
        self.assertFalse(memoria.unidad_definida)
        memoria.configurar_unidad(32)
        self.assertTrue(memoria.unidad_definida)
        self.assertEqual(memoria.estado()["total_unidades"], 64)
        memoria.asignar(1, 10)
        with self.assertRaises(RuntimeError):
            memoria.configurar_unidad(64)


class ListaEnlazadaTests(unittest.TestCase):
    def test_detecta_fragmentacion_y_fusiona_huecos(self):
        memoria = MemoriaListaEnlazada(2048)
        for pid, tamaño in ((1, 100), (2, 200), (3, 100)):
            self.assertTrue(memoria.asignar(pid, tamaño))
        memoria.liberar(2)
        self.assertEqual(memoria.estado()["fragmentacion_externa_mb"], 200)
        memoria.liberar(1)
        memoria.liberar(3)
        self.assertEqual(memoria.mayor_hueco_libre(), 2048)
        self.assertEqual(len(memoria.bloques()), 1)


def _escenario_huecos(estrategia):
    """A B C D E H ocupados; se liberan B y D. Huecos: 384@128, 256@640, resto al final."""
    memoria = MemoriaListaEnlazada(2048, estrategia=estrategia)
    for pid, tam in ((1, 128), (2, 384), (3, 128), (4, 256), (5, 128), (6, 704)):
        assert memoria.asignar(pid, tam)
    memoria.liberar(2)
    memoria.liberar(4)
    return memoria


class EstrategiasListaTests(unittest.TestCase):
    def _inicio_de(self, estrategia, tam=150):
        memoria = _escenario_huecos(estrategia)
        self.assertTrue(memoria.asignar(99, tam))
        return memoria.asignaciones[99]["inicio"]

    def test_first_fit_usa_el_primer_hueco(self):
        self.assertEqual(self._inicio_de("first_fit"), 128)

    def test_best_fit_usa_el_hueco_mas_ajustado(self):
        self.assertEqual(self._inicio_de("best_fit"), 640)

    def test_worst_fit_usa_el_hueco_mas_grande(self):
        # huecos: 384@128, 256@640 y 320 al final → gana el de 384
        self.assertEqual(self._inicio_de("worst_fit"), 128)
        memoria = MemoriaListaEnlazada(1024, estrategia="worst_fit")
        memoria.asignar(1, 100); memoria.asignar(2, 100); memoria.asignar(3, 100)
        memoria.liberar(1)  # hueco 100@0 y hueco grande 724@300
        memoria.asignar(4, 50)
        self.assertEqual(memoria.asignaciones[4]["inicio"], 300)

    def test_next_fit_continua_desde_la_ultima_asignacion(self):
        # El puntero quedó después del último proceso (dirección 1728): hueco final.
        self.assertEqual(self._inicio_de("next_fit"), 1728)

    def test_next_fit_da_la_vuelta_a_la_lista(self):
        memoria = MemoriaListaEnlazada(1024, estrategia="next_fit")
        memoria.asignar(1, 512); memoria.asignar(2, 512)
        memoria.liberar(1)
        self.assertTrue(memoria.asignar(3, 100))
        self.assertEqual(memoria.asignaciones[3]["inicio"], 0)

    def test_lista_ligada_no_usa_unidad_y_reserva_el_tamano_exacto(self):
        gestor = crear_gestor("best_fit", 2048)
        gestor.asignar(1, 100)
        self.assertEqual(gestor.asignaciones[1]["reservada_mb"], 100)
        self.assertEqual(crear_gestor("lista_enlazada", 2048).clave, "first_fit")
        with self.assertRaises(ValueError):
            crear_gestor("best_fit", 2048, 64)          # la unidad es solo del mapa de bits
        with self.assertRaises(ValueError):
            Memoria(2048, "worst_fit").configurar_unidad(64)

    def test_worst_fit_siempre_elige_el_hueco_mas_grande_de_toda_la_lista(self):
        memoria = _escenario_huecos("worst_fit")
        memoria.asignar(99, 50)
        self.assertEqual(memoria.asignaciones[99]["inicio"], 128)   # 384 MB, el mayor de los huecos
        self.assertIn("más grande", memoria.estado()["decision"])

    def test_solo_el_mapa_de_bits_necesita_unidad_para_activarse(self):
        self.assertFalse(Memoria(2048, "bitmap").listo)
        self.assertTrue(Memoria(2048, "first_fit").listo)
        self.assertTrue(Memoria(2048, "buddy").listo)


class PaginacionTests(unittest.TestCase):
    REFS = "7 0 1 2 0 3 0 4 2 3 0 3 2 1 2 0 1 7 0 1"

    def _fallas(self, alg, marcos=3, refs=None):
        return simular(alg, parsear_referencias(refs or self.REFS), marcos)["fallas"]

    def test_resultados_clasicos_con_3_marcos(self):
        self.assertEqual(self._fallas("fifo"), 15)
        self.assertEqual(self._fallas("lru"), 12)
        self.assertEqual(self._fallas("opt"), 9)

    def test_opt_nunca_falla_mas_que_los_demas(self):
        for alg in ("fifo", "lru", "nru"):
            self.assertLessEqual(self._fallas("opt"), self._fallas(alg))

    def test_fifo_anomalia_de_belady(self):
        refs = "1 2 3 4 1 2 5 1 2 3 4 5"
        self.assertEqual(self._fallas("fifo", 3, refs), 9)
        self.assertEqual(self._fallas("fifo", 4, refs), 10)

    def test_nru_prefiere_paginas_no_referenciadas_ni_modificadas(self):
        # Con intervalo 2 se limpian los R; la página modificada (0w) debe sobrevivir.
        res = simular("nru", parsear_referencias("0w 1 2 3"), 2, intervalo_nru=2)
        self.assertEqual(res["pasos"][2]["saliente"], 1)

    def test_lru_muestra_recencia_y_referencias_invalidas_fallan(self):
        res = simular("lru", parsear_referencias("1 2 1 3"), 3)
        self.assertEqual(res["pasos"][-1]["recencia"], [2, 1, 3])
        with self.assertRaises(ValueError):
            parsear_referencias("1 x 2")


class BuddyTests(unittest.TestCase):
    def test_divide_y_reune_asociados(self):
        memoria = MemoriaBuddy(2048)
        self.assertTrue(memoria.asignar(1, 100))
        self.assertTrue(memoria.asignar(2, 100))
        self.assertEqual(memoria.memoria_usada, 256)
        memoria.liberar(1)
        memoria.liberar(2)
        self.assertEqual(memoria.bloques(), [
            {"inicio": 0, "tamaño": 2048, "libre": True, "pid": None}
        ])


class CambioDeAlgoritmoTests(unittest.TestCase):
    def test_rechaza_cambio_con_procesos_activos(self):
        kernel = Kernel(ram_mb=2048)
        kernel.arrancar()
        proceso = kernel.crear_proceso("editor", memoria_mb=100)
        with self.assertRaises(RuntimeError):
            kernel.cambiar_algoritmo_memoria("buddy")
        kernel.terminar_proceso(proceso.pid)
        kernel.cambiar_algoritmo_memoria("buddy")
        self.assertEqual(kernel.memoria.algoritmo, "buddy")


if __name__ == "__main__":
    unittest.main()
