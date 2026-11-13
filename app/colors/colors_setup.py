#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Colormap generation and organization toolkit for GOES ABI imagery.

Generates and manages multi-family CPT palettes:
    1. 'default' family: Regional calibrated stack
       - C01: Reflective grayscale (grey255.cpt)
       - C09: Operational Water Vapor (WV_red_black.cpt reversed)
       - C13: Oklahoma Convective Rainbow (oklahoma.cpt / colors.rainbow)
       - C02-C16: RAMMB/CIRA scientific enhancements
    2. 'noaa' family: Official NOAA / NESDIS / NHC full-disk operational palettes (goes.noaa.gov)
       - C01-C06: Linear solar reflectance grayscale (0.0 to 1.0)
       - C07: Shortwave IR / Fire temperature anomaly (-90°C to +130°C)
       - C08-C10: NOAA Water Vapor spectrum (-90°C to +20°C)
       - C11-C15: NOAA / NHC Longwave IR window (-110°C to +55°C)
       - C16: NOAA CO2 Inverted thermal grayscale (-120°C to +50°C)
"""
import os
import shutil
import re

COLORS_DIR = os.path.dirname(os.path.abspath(__file__))

NOAA_STOPS_B07 = [
    (-90.0, 124, 124, 124), (-85.51, 110, 110, 110), (-81.02, 95, 95, 95), (-76.53, 81, 81, 81),
    (-72.04, 68, 68, 68), (-67.55, 52, 52, 52), (-63.06, 39, 39, 39), (-58.57, 6, 9, 9),
    (-54.08, 103, 0, 0), (-49.59, 218, 0, 0), (-45.1, 255, 67, 0), (-40.61, 255, 169, 0),
    (-36.12, 243, 255, 0), (-31.63, 125, 255, 0), (-27.14, 21, 255, 0), (-22.65, 0, 165, 40),
    (-18.16, 0, 52, 91), (-13.67, 0, 25, 129), (-9.18, 0, 110, 175), (-4.69, 0, 195, 222),
    (-0.2, 204, 185, 185), (4.29, 185, 185, 185), (8.78, 180, 180, 180), (13.27, 176, 176, 176),
    (17.76, 171, 171, 171), (22.24, 167, 167, 167), (26.73, 163, 163, 163), (31.22, 158, 158, 158),
    (35.71, 154, 154, 154), (40.2, 255, 255, 255), (44.69, 145, 145, 145), (49.18, 255, 255, 255),
    (53.67, 255, 255, 255), (58.16, 131, 131, 131), (62.65, 127, 127, 127), (67.14, 123, 123, 123),
    (71.63, 119, 119, 119), (76.12, 113, 113, 113), (80.61, 109, 109, 109), (85.1, 104, 104, 104),
    (89.59, 100, 100, 100), (94.08, 96, 96, 96), (98.57, 91, 91, 91), (103.06, 87, 87, 87),
    (107.55, 82, 82, 82), (112.04, 78, 78, 78), (116.53, 72, 72, 72), (121.02, 69, 69, 69),
    (125.51, 65, 65, 65), (130.0, 60, 60, 60)
]

NOAA_STOPS_B08_10 = [
    (-90.0, 0, 255, 255), (-87.76, 12, 233, 217), (-85.51, 25, 208, 172), (-83.27, 38, 186, 132),
    (-81.02, 51, 160, 87), (-78.78, 63, 138, 48), (-76.53, 75, 136, 44), (-74.29, 93, 148, 65),
    (-72.04, 109, 159, 84), (-69.8, 127, 171, 105), (-67.55, 143, 181, 124), (-65.31, 159, 192, 143),
    (-63.06, 177, 204, 164), (-60.82, 193, 214, 182), (-58.57, 211, 226, 204), (-56.33, 228, 237, 223),
    (-54.08, 246, 249, 245), (-51.84, 251, 251, 252), (-49.59, 226, 226, 239), (-47.35, 199, 199, 224),
    (-45.1, 174, 174, 211), (-42.86, 148, 148, 196), (-40.61, 124, 124, 183), (-38.37, 99, 99, 169),
    (-36.12, 72, 72, 155), (-33.88, 48, 48, 141), (-31.63, 21, 21, 127), (-29.39, 0, 0, 115),
    (-27.14, 35, 35, 99), (-24.9, 79, 79, 79), (-22.65, 117, 117, 62), (-20.41, 161, 161, 43),
    (-18.16, 199, 199, 25), (-15.92, 237, 237, 8), (-13.67, 255, 248, 0), (-11.43, 255, 232, 0),
    (-9.18, 255, 214, 0), (-6.94, 255, 198, 0), (-4.69, 255, 181, 0), (-2.45, 255, 165, 0),
    (-0.2, 255, 149, 0), (2.04, 255, 131, 0), (4.29, 255, 115, 0), (6.53, 255, 97, 0),
    (8.78, 255, 81, 0), (11.02, 255, 65, 0), (13.27, 255, 47, 0), (15.51, 255, 31, 0),
    (17.76, 255, 14, 0), (20.0, 114, 0, 0)
]

NOAA_STOPS_B11_15 = [
    (-110.0, 255, 255, 255), (-106.63, 255, 255, 255), (-103.27, 255, 255, 255), (-99.9, 255, 255, 255),
    (-96.53, 255, 255, 255), (-93.16, 202, 202, 202), (-89.8, 120, 120, 120), (-86.43, 38, 38, 38),
    (-83.06, 70, 0, 0), (-79.69, 185, 0, 0), (-76.33, 255, 36, 0), (-72.96, 255, 152, 0),
    (-69.59, 255, 254, 0), (-66.22, 154, 255, 0), (-62.86, 52, 255, 0), (-59.49, 0, 199, 26),
    (-56.12, 0, 86, 77), (-52.76, 0, 0, 115), (-49.39, 0, 96, 168), (-46.02, 0, 181, 214),
    (-42.65, 108, 220, 219), (-39.29, 186, 186, 186), (-35.92, 181, 181, 181), (-32.55, 177, 177, 177),
    (-29.18, 173, 173, 173), (-25.82, 168, 168, 168), (-22.45, 164, 164, 164), (-19.08, 159, 159, 159),
    (-15.71, 155, 155, 155), (-12.35, 194, 194, 194), (-8.98, 146, 146, 146), (-5.61, 249, 249, 249),
    (-2.24, 255, 255, 255), (1.12, 132, 132, 132), (4.49, 127, 127, 127), (7.86, 123, 123, 123),
    (11.22, 119, 119, 119), (14.59, 114, 114, 114), (17.96, 110, 110, 110), (21.33, 105, 105, 105),
    (24.69, 101, 101, 101), (28.06, 96, 96, 96), (31.43, 92, 92, 92), (34.8, 88, 88, 88),
    (38.16, 83, 83, 83), (41.53, 79, 79, 79), (44.9, 73, 73, 73), (48.27, 69, 69, 69),
    (51.63, 65, 65, 65), (55.0, 60, 60, 60)
]

NOAA_STOPS_B16 = [
    (-120.0, 255, 255, 255),
    (-80.0, 200, 200, 200),
    (-40.0, 140, 140, 140),
    (0.0, 80, 80, 80),
    (50.0, 0, 0, 0)
]


def create_interpolated_cpt(points, filename, target_dir=COLORS_DIR):
    """
    Writes a GMT-compatible CPT file from a sequence of (value, r, g, b) control points.
    """
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write("# CPT Colormap for GOES ABI\n# COLOR_MODEL = RGB\n")
        for i in range(len(points) - 1):
            v1, r1, g1, b1 = points[i]
            v2, r2, g2, b2 = points[i + 1]
            f.write(f"{v1:<10.3f} {r1:<4d} {g1:<4d} {b1:<4d} {v2:<10.3f} {r2:<4d} {g2:<4d} {b2:<4d}\n")
    return path


def get_oklahoma_points():
    """Extracts Oklahoma color stops from colors.py."""
    colors_py = os.path.join(COLORS_DIR, "colors.py")
    stops = []
    if os.path.exists(colors_py):
        with open(colors_py, 'r', encoding='utf-8') as f:
            content = f.read()
        matches = re.findall(
            r'\(([\d\.]+)\s*,\s*\'#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})',
            content
        )
        for factor_str, r_hex, g_hex, b_hex in matches:
            factor = float(factor_str)
            r = int(r_hex, 16)
            g = int(g_hex, 16)
            b = int(b_hex, 16)
            temp = -90.0 + factor * 140.0
            stops.append((temp, r, g, b))
    return stops


def build_default_family(dest_dir=None):
    """
    Builds the default calibrated family (Oklahoma C13, WV C09, Grayscale C01, RAMMB/CIRA others).
    """
    if dest_dir is None:
        dest_dir = os.path.join(COLORS_DIR, "default")
    os.makedirs(dest_dir, exist_ok=True)

    # CH01: Grayscale reflective
    shutil.copyfile(os.path.join(COLORS_DIR, "grey255.cpt"), os.path.join(dest_dir, "ch01.cpt"))

    # CH02: Grayscale reflective
    shutil.copyfile(os.path.join(COLORS_DIR, "grey255.cpt"), os.path.join(dest_dir, "ch02.cpt"))

    # CH03: Veggie Near-IR (0.86 µm)
    ch03_pts = [
        (0.00, 0, 0, 0), (0.10, 50, 35, 20), (0.25, 70, 50, 25), (0.40, 30, 110, 35),
        (0.60, 60, 165, 50), (0.75, 130, 205, 95), (0.90, 210, 240, 200), (1.00, 255, 255, 255)
    ]
    create_interpolated_cpt(ch03_pts, "ch03.cpt", target_dir=dest_dir)

    # CH04: Cirrus (1.37 µm)
    ch04_pts = [
        (0.00, 5, 5, 15), (0.10, 25, 10, 45), (0.25, 65, 20, 95), (0.45, 125, 45, 150),
        (0.70, 190, 110, 215), (0.88, 235, 195, 245), (1.00, 255, 255, 255)
    ]
    create_interpolated_cpt(ch04_pts, "ch04.cpt", target_dir=dest_dir)

    # CH05: Snow/Ice (1.61 µm)
    ch05_pts = [
        (0.00, 0, 10, 25), (0.15, 0, 45, 75), (0.35, 0, 100, 140), (0.60, 50, 160, 195),
        (0.80, 140, 215, 235), (0.95, 220, 245, 250), (1.00, 255, 255, 255)
    ]
    create_interpolated_cpt(ch05_pts, "ch05.cpt", target_dir=dest_dir)

    # CH06: Cloud Particle Size (2.25 µm)
    ch06_pts = [
        (0.00, 15, 15, 15), (0.15, 60, 35, 10), (0.35, 135, 80, 15), (0.60, 215, 145, 25),
        (0.80, 250, 205, 70), (0.95, 255, 240, 175), (1.00, 255, 255, 255)
    ]
    create_interpolated_cpt(ch06_pts, "ch06.cpt", target_dir=dest_dir)

    # CH07: Shortwave IR (thermal.cpt)
    shutil.copyfile(os.path.join(COLORS_DIR, "thermal.cpt"), os.path.join(dest_dir, "ch07.cpt"))

    # CH08: Upper WV (SVGAWVX_TEMP.cpt)
    shutil.copyfile(os.path.join(COLORS_DIR, "SVGAWVX_TEMP.cpt"), os.path.join(dest_dir, "ch08.cpt"))

    # CH09: Mid WV (WV_red_black.cpt)
    shutil.copyfile(os.path.join(COLORS_DIR, "WV_red_black.cpt"), os.path.join(dest_dir, "ch09.cpt"))

    # CH10: Lower WV (WV.cpt)
    shutil.copyfile(os.path.join(COLORS_DIR, "WV.cpt"), os.path.join(dest_dir, "ch10.cpt"))

    # CH11: Cloud-Top Phase
    ch11_pts = [
        (-90.0, 250, 225, 255), (-70.0, 210, 150, 235), (-50.0, 120, 70, 160), (-30.0, 35, 105, 135),
        (-10.0, 40, 145, 115), (10.0, 110, 150, 95), (30.0, 115, 115, 115), (50.0, 20, 20, 20)
    ]
    create_interpolated_cpt(ch11_pts, "ch11.cpt", target_dir=dest_dir)

    # CH12: Ozone
    ch12_pts = [
        (-90.0, 185, 25, 145), (-65.0, 30, 55, 175), (-40.0, 15, 125, 150), (-15.0, 25, 165, 95),
        (10.0, 165, 155, 35), (30.0, 125, 65, 20), (50.0, 30, 30, 30)
    ]
    create_interpolated_cpt(ch12_pts, "ch12.cpt", target_dir=dest_dir)

    # CH13: Realce Oklahoma
    ok_pts = get_oklahoma_points()
    if ok_pts:
        create_interpolated_cpt(ok_pts, "ch13.cpt", target_dir=dest_dir)
        create_interpolated_cpt(ok_pts, "oklahoma.cpt", target_dir=COLORS_DIR)
    else:
        shutil.copyfile(os.path.join(COLORS_DIR, "thermal.cpt"), os.path.join(dest_dir, "ch13.cpt"))

    # CH14: Traditional IR
    shutil.copyfile(os.path.join(COLORS_DIR, "IR4AVHRR6.cpt"), os.path.join(dest_dir, "ch14.cpt"))

    # CH15: Dirty Longwave IR
    ch15_pts = [
        (-90.0, 245, 245, 255), (-60.0, 75, 95, 145), (-30.0, 125, 115, 90), (0.0, 185, 155, 95),
        (25.0, 170, 120, 60), (50.0, 30, 25, 20)
    ]
    create_interpolated_cpt(ch15_pts, "ch15.cpt", target_dir=dest_dir)

    # CH16: CO2
    ch16_pts = [
        (-90.0, 145, 45, 165), (-65.0, 35, 115, 165), (-40.0, 30, 155, 140), (-15.0, 65, 165, 95),
        (10.0, 175, 145, 45), (30.0, 95, 65, 45), (50.0, 25, 25, 25)
    ]
    create_interpolated_cpt(ch16_pts, "ch16.cpt", target_dir=dest_dir)

    # Also mirror into root colors directory for backward compatibility
    for band in range(1, 17):
        src = os.path.join(dest_dir, f"ch{band:02d}.cpt")
        dst = os.path.join(COLORS_DIR, f"ch{band:02d}.cpt")
        if os.path.exists(src) and src != dst:
            shutil.copyfile(src, dst)


def build_noaa_family(dest_dir=None):
    """
    Builds the official NOAA / NESDIS operational full-disk family (goes.noaa.gov).
    """
    if dest_dir is None:
        dest_dir = os.path.join(COLORS_DIR, "noaa")
    os.makedirs(dest_dir, exist_ok=True)

    # CH01 - CH06: Linear solar reflectance (grayscale 0.0 to 1.0)
    for band in range(1, 7):
        shutil.copyfile(os.path.join(COLORS_DIR, "grey255.cpt"), os.path.join(dest_dir, f"ch{band:02d}.cpt"))

    # CH07: NOAA Shortwave IR / Fire
    create_interpolated_cpt(NOAA_STOPS_B07, "ch07.cpt", target_dir=dest_dir)

    # CH08 - CH10: NOAA Water Vapor
    for band in range(8, 11):
        create_interpolated_cpt(NOAA_STOPS_B08_10, f"ch{band:02d}.cpt", target_dir=dest_dir)

    # CH11 - CH15: NOAA Longwave IR Window (BD/NHC curve)
    for band in range(11, 16):
        create_interpolated_cpt(NOAA_STOPS_B11_15, f"ch{band:02d}.cpt", target_dir=dest_dir)

    # CH16: NOAA CO2 Longwave
    create_interpolated_cpt(NOAA_STOPS_B16, "ch16.cpt", target_dir=dest_dir)

    # Also mirror with suffix into root colors directory (e.g. ch13_noaa.cpt) for hybrid lookups
    for band in range(1, 17):
        src = os.path.join(dest_dir, f"ch{band:02d}.cpt")
        dst = os.path.join(COLORS_DIR, f"ch{band:02d}_noaa.cpt")
        if os.path.exists(src):
            shutil.copyfile(src, dst)


def build_all_palettes():
    """Generates all color families and mirrors files for both subfolder and suffix lookup."""
    build_default_family()
    build_noaa_family()
    print("All palette families ('default' and 'noaa') generated successfully in", COLORS_DIR)


if __name__ == '__main__':
    build_all_palettes()
