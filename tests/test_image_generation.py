import unittest
import os
import sys

# Asegurar que 'app' esté en el sys.path
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
APP_DIR = os.path.join(PROJECT_ROOT, "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from unittest.mock import patch
import main

class TestSatelliteImageGeneration(unittest.TestCase):
    """
    Suite de pruebas para verificar la generación de imágenes satelitales.
    
    NOTA: Las imágenes generadas se conservan en app/test_output/<nombre_del_caso>/
    para que el usuario pueda inspeccionarlas visualmente después de correr los tests.
    """

    @classmethod
    def setUpClass(cls):
        if getattr(main, 'gdal', None) is None or getattr(main, 'Basemap', None) is None:
            raise unittest.SkipTest("GDAL o Basemap no están disponibles en el entorno Python actual. Omitiendo prueba de renderizado.")

        # Configurar basePath al directorio app del proyecto
        main.basePath = APP_DIR

        # Buscar archivo de prueba NetCDF (C13) disponible en app/input/
        input_base = os.path.join(APP_DIR, "input")
        cls.sample_nc = None
        cls.day_julian = None
        cls.band_str = "13"

        if os.path.exists(input_base):
            for root, dirs, files in os.walk(input_base):
                for f in files:
                    if "C13" in f and f.endswith(".nc"):
                        cls.sample_nc = f
                        cls.day_julian = os.path.basename(root)
                        break
                if cls.sample_nc:
                    break

        if not cls.sample_nc:
            raise unittest.SkipTest("No se encontró ningún archivo NetCDF de prueba en app/input/. Omitiendo prueba de renderizado.")

        # Extraer timestamp
        start_idx = cls.sample_nc.find("_s")
        if start_idx != -1:
            s_tag = cls.sample_nc[start_idx+2:start_idx+13]
            from datetime import datetime, timedelta
            year = int(s_tag[0:4])
            dayj = int(s_tag[4:7])
            dt = datetime(year, 1, 1) + timedelta(days=dayj - 1)
            cls.expected_timestamp = dt.strftime('%Y%m%d') + s_tag[7:9] + s_tag[9:11]
        else:
            cls.expected_timestamp = "201907111000"

        # Directorio raíz para outputs de tests (se conserva para inspección)
        cls.base_test_output = os.path.join(APP_DIR, "test_output")
        os.makedirs(cls.base_test_output, exist_ok=True)
        cls.original_output_config = main.config['paths']['output']

    @classmethod
    def tearDownClass(cls):
        # Restaurar configuración original al terminar toda la suite
        main.config['paths']['output'] = cls.original_output_config
        print(f"\n📁 [INFO] Todas las imágenes generadas se conservaron en:")
        print(f"   {cls.base_test_output}")

    def _prepare_case_folder(self, case_name):
        """Asigna una carpeta de salida específica para cada caso de prueba."""
        case_output_rel = os.path.join("test_output", case_name)
        main.config['paths']['output'] = case_output_rel
        self.current_output_dir = os.path.join(APP_DIR, case_output_rel)
        return self.current_output_dir

    def _assert_generated_files(self):
        """Verifica que se hayan generado los archivos PNG, PGW y TIF esperados."""
        channel_folder = os.path.join(self.current_output_dir, self.day_julian, f"C{self.band_str}")
        png_file = os.path.join(channel_folder, f"{self.expected_timestamp}.png")
        pgw_file = os.path.join(channel_folder, f"{self.expected_timestamp}.pgw")
        tif_file = os.path.join(channel_folder, f"{self.expected_timestamp}.tif")
        latest_png = os.path.join(APP_DIR, "latest", f"latestC{self.band_str}.png")
        latest_pgw = os.path.join(APP_DIR, "latest", f"latestC{self.band_str}.pgw")

        # 1. Validar existencia y tamaño
        self.assertTrue(os.path.exists(png_file), f"No se generó el PNG en output: {png_file}")
        self.assertGreater(os.path.getsize(png_file), 0, "El archivo PNG generado está vacío")

        self.assertTrue(os.path.exists(pgw_file), f"No se generó el PGW en output: {pgw_file}")
        self.assertGreater(os.path.getsize(pgw_file), 0, "El archivo PGW generado está vacío")

        self.assertTrue(os.path.exists(tif_file), f"No se generó el TIF en output: {tif_file}")
        self.assertGreater(os.path.getsize(tif_file), 0, "El archivo TIF generado está vacío")

        self.assertTrue(os.path.exists(latest_png), f"No se generó el PNG en latest: {latest_png}")
        self.assertTrue(os.path.exists(latest_pgw), f"No se generó el PGW en latest: {latest_pgw}")

        print(f"   ✔ Imagen generada con éxito ({os.path.getsize(png_file)} bytes): {png_file}")

    def test_01_single_coord_with_label_and_bullseye(self):
        """Prueba: 1 coordenada, con label=True y con bullseye=True."""
        print("\n[TEST 1] Ejecutando: 1 coordenada con label y con bullseye...")
        self._prepare_case_folder("01_single_coord_with_label_and_bullseye")
        main.processImage(
            self.sample_nc,
            lat=4.711,
            lon=-74.072,
            label=True,
            bullseye=True
        )
        self._assert_generated_files()

    def test_02_single_coord_without_label_and_bullseye(self):
        """Prueba: 1 coordenada, sin label (label=False) y con bullseye=True."""
        print("\n[TEST 2] Ejecutando: 1 coordenada SIN label y con bullseye...")
        self._prepare_case_folder("02_single_coord_without_label_and_bullseye")
        main.processImage(
            self.sample_nc,
            lat=4.711,
            lon=-74.072,
            label=False,
            bullseye=True
        )
        self._assert_generated_files()

    def test_03_single_coord_without_bullseye(self):
        """Prueba: 1 coordenada, sin bullseye (bullseye=False, con etiqueta P1)."""
        print("\n[TEST 3] Ejecutando: 1 coordenada con label y SIN bullseye (etiqueta P1)...")
        self._prepare_case_folder("03_single_coord_without_bullseye")
        main.processImage(
            self.sample_nc,
            lat=4.711,
            lon=-74.072,
            label=True,
            bullseye=False
        )
        self._assert_generated_files()

    def test_04_multiple_coords_with_bullseye(self):
        """Prueba: múltiples coordenadas (lista de lat/lon), con bullseye=True."""
        print("\n[TEST 4] Ejecutando: Múltiples coordenadas con bullseye...")
        self._prepare_case_folder("04_multiple_coords_with_bullseye")
        main.processImage(
            self.sample_nc,
            lat=[4.711, 10.968, 6.244],
            lon=[-74.072, -74.781, -75.581],
            label=True,
            bullseye=True
        )
        self._assert_generated_files()

    def test_05_multiple_coords_without_bullseye(self):
        """Prueba: múltiples coordenadas sin bullseye (bullseye=False, rotulados P1, P2, P3)."""
        print("\n[TEST 5] Ejecutando: Múltiples coordenadas SIN bullseye (etiquetas P1, P2, P3)...")
        self._prepare_case_folder("05_multiple_coords_without_bullseye")
        main.processImage(
            self.sample_nc,
            lat=[4.711, 10.968, 6.244],
            lon=[-74.072, -74.781, -75.581],
            label=True,
            bullseye=False
        )
        self._assert_generated_files()

    def test_06_without_coords_full_domain(self):
        """Prueba: sin coordenadas (dominio por defecto/completo de Colombia)."""
        print("\n[TEST 6] Ejecutando: Sin coordenadas (dominio completo Colombia)...")
        self._prepare_case_folder("06_without_coords_full_domain")
        main.processImage(
            self.sample_nc,
            lat=None,
            lon=None,
            label=True,
            bullseye=True
        )
        self._assert_generated_files()

    def test_07_cli_command_invocation_with_arguments(self):
        """Prueba a nivel CLI simulando ejecución de main.py completo con argumentos en inglés."""
        print("\n[TEST 7] Ejecutando: Invocación CLI completa en inglés (main())...")
        self._prepare_case_folder("07_cli_full_invocation")

        cli_args = [
            "main.py",
            "--mode=manual",
            "--source=aws",
            f"--date={self.expected_timestamp[:8]}",
            f"--hours={self.expected_timestamp[8:10]}",
            f"--minutes={self.expected_timestamp[10:12]}",
            "--lat=4.711,10.968",
            "--lon=-74.072,-74.781",
            "--label=true",
            "--bullseye=false"
        ]

        with patch.object(sys, "argv", cli_args):
            with patch("main.download", return_value=[self.sample_nc]):
                main.main()

        self._assert_generated_files()

    def test_08_cli_spanish_aliases_invocation(self):
        """Prueba a nivel CLI simulando ejecución con alias en español (--tipo, --fuente, --fecha...)."""
        print("\n[TEST 8] Ejecutando: Invocación CLI con alias en español (--tipo, --fuente)...")
        self._prepare_case_folder("08_cli_spanish_aliases")

        cli_args = [
            "main.py",
            "--tipo=manual",
            "--fuente=aws",
            f"--fecha={self.expected_timestamp[:8]}",
            f"--horas={self.expected_timestamp[8:10]}",
            f"--minutos={self.expected_timestamp[10:12]}",
            "--lat=4.711,10.968",
            "--lon=-74.072,-74.781",
            "--label=true",
            "--bullseye=false"
        ]

        with patch.object(sys, "argv", cli_args):
            with patch("main.download", return_value=[self.sample_nc]):
                main.main()

        self._assert_generated_files()

if __name__ == "__main__":
    unittest.main()
