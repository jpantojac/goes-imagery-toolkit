import unittest
import os
import sys

# Asegurar que 'app' esté en el sys.path
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
APP_DIR = os.path.join(PROJECT_ROOT, "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

try:
    import numpy as np
except ImportError:
    np = None

import main


class TestCalibrationAndGeometry(unittest.TestCase):
    """
    Suite de pruebas unitarias para calibración radiométrica,
    geometría de coordenadas y validaciones del pipeline satelital.
    """

    def test_r2bt_infrared_c13_conversion(self):
        """Verifica la inversión de la función de Planck para la banda infrarroja limpia C13 (10.35 µm)."""
        if np is None:
            raise unittest.SkipTest("NumPy no está instalado en este entorno.")
        # Radiancia típica (~50 - 100 mW/(m²·sr·cm⁻¹))
        rad_sample = np.array([30.0, 70.0, 110.0])
        tb = main.R2BT(rad_sample, 'C13')

        self.assertEqual(len(tb), 3)
        # Temperaturas de brillo esperadas en la atmósfera (entre -70°C y +40°C)
        self.assertTrue(np.all(tb > -100.0))
        self.assertTrue(np.all(tb < 60.0))
        # Relación monótona: a mayor radiancia, mayor temperatura
        self.assertTrue(tb[0] < tb[1] < tb[2])

    def test_r2rt_visible_reflectance_and_gamma(self):
        """Verifica el cálculo de reflectancia con constante solar Esun y corrección gamma para C02 (0.64 µm)."""
        if np is None:
            raise unittest.SkipTest("NumPy no está instalado en este entorno.")
        rad_sample = np.array([0.0, 50.0, 200.0])
        ref = main.R2RT(rad_sample, 'C02')

        self.assertEqual(len(ref), 3)
        # La reflectancia gamma normalizada debe estar en [0, 1]
        self.assertTrue(np.all(ref >= 0.0))
        self.assertTrue(np.all(ref <= 1.0))
        self.assertEqual(ref[0], 0.0)
        self.assertTrue(ref[0] < ref[1] < ref[2])

    def test_r2bt_unsupported_channel_raises_error(self):
        """Verifica que un canal inexistente o no térmico lance KeyError en R2BT."""
        if np is None:
            raise unittest.SkipTest("NumPy no está instalado en este entorno.")
        with self.assertRaises(KeyError):
            main.R2BT(np.array([50.0]), 'C02')

    def test_validate_date(self):
        """Valida parsing de fechas en formato YYYYMMDD."""
        self.assertEqual(main.validate_date("20250523"), "20250523")
        self.assertIsNone(main.validate_date("2025-05-23"))
        self.assertIsNone(main.validate_date("abc"))
        self.assertIsNone(main.validate_date("20251340"))  # Mes 13 inválido

    def test_validate_time(self):
        """Valida parsing de horas o minutos de 2 dígitos."""
        self.assertEqual(main.validate_time("00"), "00")
        self.assertEqual(main.validate_time("12"), "12")
        self.assertEqual(main.validate_time("59"), "59")
        self.assertIsNone(main.validate_time("5"))   # Debe ser de 2 dígitos
        self.assertIsNone(main.validate_time("60"))  # Fuera de rango
        self.assertIsNone(main.validate_time("xx"))

    def test_validate_lat_lon(self):
        """Valida límites geográficos de latitud (-90 a 90) y longitud (-180 a 180)."""
        self.assertEqual(main.validate_lat(4.711), 4.711)
        self.assertEqual(main.validate_lat(-90.0), -90.0)
        self.assertEqual(main.validate_lat(90.0), 90.0)
        self.assertIsNone(main.validate_lat(95.0))
        self.assertIsNone(main.validate_lat(-95.0))

        self.assertEqual(main.validate_lon(-74.072), -74.072)
        self.assertEqual(main.validate_lon(-180.0), -180.0)
        self.assertEqual(main.validate_lon(180.0), 180.0)
        self.assertIsNone(main.validate_lon(-185.0))
        self.assertIsNone(main.validate_lon(190.0))

    def test_get_bounding_box(self):
        """Verifica el cálculo de bounding box centrado en coordenadas con radio en millas náuticas."""
        lat = 4.711
        lon = -74.072
        radius = 100
        bbox = main.get_bounding_box(lat, lon, radius)

        # Retorna [west, south, east, north]
        west, south, east, north = bbox
        self.assertLess(west, lon)
        self.assertGreater(east, lon)
        self.assertLess(south, lat)
        self.assertGreater(north, lat)

        # Simetría aproximada
        self.assertAlmostEqual(north - lat, lat - south, places=5)
        self.assertAlmostEqual(east - lon, lon - west, places=5)

    def test_cli_parser_english_flags(self):
        """Verifica que el parser acepte los parámetros en inglés (--mode, --source, --date, --hours, --minutes)."""
        parser = main.build_parser()
        args = parser.parse_args([
            "--mode=manual",
            "--source=aws",
            "--date=20240929",
            "--hours=11,12",
            "--minutes=00,30",
            "--lat=4.711",
            "--lon=-74.072",
            "--label=true",
            "--bullseye=false",
            "--watermark=MyProject"
        ])
        self.assertEqual(args.mode, "manual")
        self.assertEqual(args.source, "aws")
        self.assertEqual(args.date, "20240929")
        self.assertEqual(args.hours, "11,12")
        self.assertEqual(args.minutes, "00,30")
        self.assertEqual(args.lat, "4.711")
        self.assertEqual(args.lon, "-74.072")
        self.assertTrue(args.label)
        self.assertFalse(args.bullseye)
        self.assertEqual(args.watermark, "MyProject")

    def test_cli_parser_spanish_aliases(self):
        """Verifica compatibilidad hacia atrás con alias en español (--tipo, --fuente, --fecha, --horas, --minutos)."""
        parser = main.build_parser()
        args = parser.parse_args([
            "--tipo=manual",
            "--fuente=aws",
            "--fecha=20240929",
            "--horas=11,12",
            "--minutos=00,30",
            "--institucion=MyProject"
        ])
        self.assertEqual(args.mode, "manual")
        self.assertEqual(args.source, "aws")
        self.assertEqual(args.date, "20240929")
        self.assertEqual(args.hours, "11,12")
        self.assertEqual(args.minutes, "00,30")
        self.assertEqual(args.watermark, "MyProject")

    def test_get_band_extraction(self):
        """Verifica la extracción del número de banda para archivos G16 y G19."""
        f_g19 = "OR_ABI-L1b-RadF-M6C13_G19_s20263160150205_e20263160159527_c20263160159575.nc"
        self.assertEqual(main.get_band(f_g19, True), 13)
        self.assertEqual(main.get_band(f_g19, False), "13")

        f_g16 = "OR_ABI-L1b-RadF-M6C01_G16_s20242731200210_e20242731209518_c20242731209567.nc"
        self.assertEqual(main.get_band(f_g16, True), 1)
        self.assertEqual(main.get_band(f_g16, False), "01")


if __name__ == "__main__":
    unittest.main()

