"""Pruebas de comportamiento para los tres administradores de RAM."""

import unittest

from os_simulator.core.kernel import Kernel
from os_simulator.memory.bitmap import MemoriaBitmap
from os_simulator.memory.buddy import MemoriaBuddy
from os_simulator.memory.linked_list import MemoriaListaEnlazada


class BitmapTests(unittest.TestCase):
    def test_redondea_a_marcos_y_los_libera(self):
        memoria = MemoriaBitmap(4096)
        self.assertTrue(memoria.asignar(1, 100))
        self.assertEqual(memoria.estado()["reservada_mb"], 128)
        self.assertEqual(memoria.estado()["fragmentacion_interna_mb"], 28)
        self.assertEqual(memoria.liberar(1), 100)
        self.assertEqual(memoria.memoria_usada, 0)


class ListaEnlazadaTests(unittest.TestCase):
    def test_detecta_fragmentacion_y_fusiona_huecos(self):
        memoria = MemoriaListaEnlazada(4096)
        for pid, tamaño in ((1, 100), (2, 200), (3, 100)):
            self.assertTrue(memoria.asignar(pid, tamaño))
        memoria.liberar(2)
        self.assertEqual(memoria.estado()["fragmentacion_externa_mb"], 200)
        memoria.liberar(1)
        memoria.liberar(3)
        self.assertEqual(memoria.mayor_hueco_libre(), 4096)
        self.assertEqual(len(memoria.bloques()), 1)


class BuddyTests(unittest.TestCase):
    def test_divide_y_reune_asociados(self):
        memoria = MemoriaBuddy(4096)
        self.assertTrue(memoria.asignar(1, 100))
        self.assertTrue(memoria.asignar(2, 100))
        self.assertEqual(memoria.memoria_usada, 256)
        memoria.liberar(1)
        memoria.liberar(2)
        self.assertEqual(memoria.bloques(), [
            {"inicio": 0, "tamaño": 4096, "libre": True, "pid": None}
        ])


class CambioDeAlgoritmoTests(unittest.TestCase):
    def test_rechaza_cambio_con_procesos_activos(self):
        kernel = Kernel(ram_mb=4096)
        kernel.arrancar()
        proceso = kernel.crear_proceso("editor", memoria_mb=100)
        with self.assertRaises(RuntimeError):
            kernel.cambiar_algoritmo_memoria("buddy")
        kernel.terminar_proceso(proceso.pid)
        kernel.cambiar_algoritmo_memoria("buddy")
        self.assertEqual(kernel.memoria.algoritmo, "buddy")


if __name__ == "__main__":
    unittest.main()
