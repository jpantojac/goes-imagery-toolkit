import unittest
import os
import sys

# Asegurar que 'app' esté en el sys.path
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
APP_DIR = os.path.join(PROJECT_ROOT, "app")
if not os.path.exists(os.path.join(APP_DIR, "colors")) and os.path.exists(os.path.join(PROJECT_ROOT, "colors")):
    APP_DIR = PROJECT_ROOT
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

    def test_all_16_cpt_colormaps_exist_and_load(self):
        """Verifica que existan y sean válidos los 16 archivos CPT (ch01.cpt a ch16.cpt)."""
        colors_dir = os.path.join(APP_DIR, "colors")
        for band in range(1, 17):
            cpt_file = os.path.join(colors_dir, f"ch{band:02d}.cpt")
            self.assertTrue(os.path.exists(cpt_file), f"Falta el archivo CPT para el canal {band:02d}: {cpt_file}")
            if main.loadCPT is not None:
                cpt_dict = main.loadCPT(cpt_file)
                self.assertIsNotNone(cpt_dict, f"Error cargando CPT {cpt_file}")
                self.assertIn("red", cpt_dict)
                self.assertIn("green", cpt_dict)
                self.assertIn("blue", cpt_dict)

    def test_enhancement_families_exist_and_load(self):
        """Verifica la existencia y validez de las familias 'default' y 'noaa' con sus 16 canales."""
        colors_dir = os.path.join(APP_DIR, "colors")
        for family in ["default", "noaa"]:
            fam_dir = os.path.join(colors_dir, family)
            self.assertTrue(os.path.isdir(fam_dir), f"Directorio de familia {family} no existe: {fam_dir}")
            for band in range(1, 17):
                fam_cpt = os.path.join(fam_dir, f"ch{band:02d}.cpt")
                self.assertTrue(os.path.exists(fam_cpt), f"Falta CPT para {family}/ch{band:02d}.cpt")
                if main.loadCPT is not None:
                    cpt_dict = main.loadCPT(fam_cpt)
                    self.assertIsNotNone(cpt_dict, f"Error cargando CPT {fam_cpt}")
                    self.assertIn("red", cpt_dict)

        # Verificar sufijos híbridos _noaa.cpt
        for band in range(1, 17):
            suffix_cpt = os.path.join(colors_dir, f"ch{band:02d}_noaa.cpt")
            self.assertTrue(os.path.exists(suffix_cpt), f"Falta CPT con sufijo: {suffix_cpt}")

    def test_resolve_colormap_and_limits_default(self):
        """Verifica la resolución de paletas y rangos para la familia por defecto (Oklahoma en C13)."""
        # C13 en default debe preservar la paleta Oklahoma (colors.rainbow) y rango [-90, 50]
        cmap13, cmin13, cmax13 = main.resolve_colormap_and_limits(13, family="default", base_path=APP_DIR)
        self.assertEqual(cmin13, -90.0)
        self.assertEqual(cmax13, 50.0)
        if main.colors and hasattr(main.colors, 'rainbow'):
            self.assertEqual(cmap13, main.colors.rainbow)

        # C01 visible: [0.0, 1.0]
        _, cmin01, cmax01 = main.resolve_colormap_and_limits(1, family="default", base_path=APP_DIR)
        self.assertEqual(cmin01, 0.0)
        self.assertEqual(cmax01, 1.0)

        # C09 vapor de agua default: [-85.0, -30.0]
        _, cmin09, cmax09 = main.resolve_colormap_and_limits(9, family="default", base_path=APP_DIR)
        self.assertEqual(cmin09, -85.0)
        self.assertEqual(cmax09, -30.0)

    def test_resolve_colormap_and_limits_noaa(self):
        """Verifica la resolución de paletas y rangos para la familia oficial 'noaa' (goes.noaa.gov)."""
        # C01..C06 reflectancia NOAA: [0.0, 1.0]
        _, cmin01, cmax01 = main.resolve_colormap_and_limits(1, family="noaa", base_path=APP_DIR)
        self.assertEqual(cmin01, 0.0)
        self.assertEqual(cmax01, 1.0)

        # C07 onda corta / incendios NOAA: [-90.0, 130.0]
        _, cmin07, cmax07 = main.resolve_colormap_and_limits(7, family="noaa", base_path=APP_DIR)
        self.assertEqual(cmin07, -90.0)
        self.assertEqual(cmax07, 130.0)

        # C08..C10 vapor de agua NOAA: [-90.0, 20.0]
        _, cmin09, cmax09 = main.resolve_colormap_and_limits(9, family="noaa", base_path=APP_DIR)
        self.assertEqual(cmin09, -90.0)
        self.assertEqual(cmax09, 20.0)

        # C11..C15 infrarrojo térmico NOAA: [-110.0, 55.0]
        cmap13, cmin13, cmax13 = main.resolve_colormap_and_limits(13, family="noaa", base_path=APP_DIR)
        self.assertEqual(cmin13, -110.0)
        self.assertEqual(cmax13, 55.0)
        # En NOAA, C13 no debe ser el colors.rainbow estático
        if main.colors and hasattr(main.colors, 'rainbow'):
            self.assertNotEqual(cmap13, main.colors.rainbow)

        # C16 CO2 NOAA: [-120.0, 50.0]
        _, cmin16, cmax16 = main.resolve_colormap_and_limits(16, family="noaa", base_path=APP_DIR)
        self.assertEqual(cmin16, -120.0)
        self.assertEqual(cmax16, 50.0)

    def test_cli_parser_enhancement_family_flag(self):
        """Verifica que el parser acepte --family, --palette y --enhancement."""
        parser = main.build_parser()

        args1 = parser.parse_args(["--mode=auto", "--source=aws", "--family=noaa"])
        self.assertEqual(args1.family, "noaa")

        args2 = parser.parse_args(["--mode=auto", "--source=aws", "--palette=default"])
        self.assertEqual(args2.family, "default")

        args3 = parser.parse_args(["--mode=auto", "--source=aws", "--enhancement=noaa"])
        self.assertEqual(args3.family, "noaa")

    def test_r2bt_water_vapor_physical_range(self):
        """Verifica que R2BT con los coeficientes ABI reales de C09 produzca temperaturas físicas realistas."""
        if np is None:
            raise unittest.SkipTest("NumPy no está instalado en este entorno.")
        # Radiancias típicas de vapor de agua (~0.5 para nubes frías, ~10 para humedad media, ~30 para aire seco)
        rad_wv = np.array([0.5, 10.0, 30.0])
        tb_wv = main.R2BT(rad_wv, 'C09')
        # -88°C (nubes frías) < -20°C (humedad) < +15°C (aire seco)
        self.assertTrue(tb_wv[0] < -80.0)
        self.assertTrue(-35.0 < tb_wv[1] < -10.0)
        self.assertTrue(tb_wv[2] > 0.0)
        self.assertTrue(tb_wv[0] < tb_wv[1] < tb_wv[2])

    def test_r2rt_astronomical_distance_scaling(self):
        """Verifica que la reflectancia visible use d2=1.0 para contraste natural brillante."""
        if np is None:
            raise unittest.SkipTest("NumPy no está instalado en este entorno.")
        # Radiancia de nube muy brillante (400 mW/(m²·sr·cm⁻¹))
        rad_cloud = np.array([400.0])
        ref_gamma = main.R2RT(rad_cloud, 'C02', d2=1.0)
        # Debe ser brillante (> 0.8) y no un gris oscuro (< 0.5)
        self.assertGreater(ref_gamma[0], 0.8)

    def test_cli_parser_borders_and_croquis_flags(self):
        """Verifica que el parser acepte --borders y --croquis (True/False)."""
        parser = main.build_parser()

        args1 = parser.parse_args(["--mode=auto", "--source=aws", "--borders=false"])
        self.assertFalse(args1.borders)

        args2 = parser.parse_args(["--mode=auto", "--source=aws", "--croquis=false"])
        self.assertFalse(args2.borders)

        args3 = parser.parse_args(["--mode=auto", "--source=aws", "--croquis=true"])
        self.assertTrue(args3.borders)

    def test_cli_parser_max_dim_flags(self):
        """Verifica que el parser acepte --max-dim y --resolution-px con enteros."""
        parser = main.build_parser()

        args1 = parser.parse_args(["--mode=auto", "--source=aws", "--max-dim=2048"])
        self.assertEqual(args1.max_dim, 2048)

        args2 = parser.parse_args(["--mode=auto", "--source=aws", "--resolution-px=4096"])
        self.assertEqual(args2.max_dim, 4096)

        args3 = parser.parse_args(["--mode=auto", "--source=aws", "--max-dim=0"])
        self.assertEqual(args3.max_dim, 0)

        args4 = parser.parse_args(["--mode=auto", "--source=aws"])
        self.assertIsNone(args4.max_dim)

    def test_cli_parser_c16_enhanced_flag(self):
        """Verifica que el parser acepte --c16-enhanced y --c16-color."""
        parser = main.build_parser()

        args1 = parser.parse_args(["--mode=auto", "--source=aws", "--c16-enhanced=true"])
        self.assertTrue(args1.c16_enhanced)

        args2 = parser.parse_args(["--mode=auto", "--source=aws", "--c16-color=false"])
        self.assertFalse(args2.c16_enhanced)


if __name__ == "__main__":
    unittest.main()

