#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generates and organizes RAMMB/CIRA-inspired CPT colormaps for all 16 GOES ABI channels.
"""
import os
import shutil

COLORS_DIR = os.path.dirname(os.path.abspath(__file__))

def create_interpolated_cpt(points, filename):
    """
    points: list of (val, r, g, b)
    """
    path = os.path.join(COLORS_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write("# CPT Colormap for GOES ABI\n# COLOR_MODEL = RGB\n")
        for i in range(len(points) - 1):
            v1, r1, g1, b1 = points[i]
            v2, r2, g2, b2 = points[i + 1]
            f.write(f"{v1:<10.3f} {r1:<4d} {g1:<4d} {b1:<4d} {v2:<10.3f} {r2:<4d} {g2:<4d} {b2:<4d}\n")
    return path

def build_all_palettes():
    # CH01: Blue Visible (0.47 µm) - Grayscale reflective (from grey255.cpt, original active palette)
    shutil.copyfile(os.path.join(COLORS_DIR, "grey255.cpt"), os.path.join(COLORS_DIR, "ch01.cpt"))

    # CH02: Red Visible (0.64 µm) - Grayscale reflective (from grey255.cpt)
    shutil.copyfile(os.path.join(COLORS_DIR, "grey255.cpt"), os.path.join(COLORS_DIR, "ch02.cpt"))

    # CH03: Veggie Near-IR (0.86 µm) - Chlorophyll & Soil / Veggie enhancement
    ch03_pts = [
        (0.00,   0,   0,   0),
        (0.10,  50,  35,  20),
        (0.25,  70,  50,  25),
        (0.40,  30, 110,  35),
        (0.60,  60, 165,  50),
        (0.75, 130, 205,  95),
        (0.90, 210, 240, 200),
        (1.00, 255, 255, 255),
    ]
    create_interpolated_cpt(ch03_pts, "ch03.cpt")

    # CH04: Cirrus (1.37 µm) - Faint ice crystal cloud enhancement
    ch04_pts = [
        (0.00,   5,   5,  15),
        (0.10,  25,  10,  45),
        (0.25,  65,  20,  95),
        (0.45, 125,  45, 150),
        (0.70, 190, 110, 215),
        (0.88, 235, 195, 245),
        (1.00, 255, 255, 255),
    ]
    create_interpolated_cpt(ch04_pts, "ch04.cpt")

    # CH05: Snow/Ice (1.61 µm) - Cyan/Turquoise ice absorption enhancement
    ch05_pts = [
        (0.00,   0,  10,  25),
        (0.15,   0,  45,  75),
        (0.35,   0, 100, 140),
        (0.60,  50, 160, 195),
        (0.80, 140, 215, 235),
        (0.95, 220, 245, 250),
        (1.00, 255, 255, 255),
    ]
    create_interpolated_cpt(ch05_pts, "ch05.cpt")

    # CH06: Cloud Particle Size (2.25 µm) - Amber/Gold microphysics
    ch06_pts = [
        (0.00,  15,  15,  15),
        (0.15,  60,  35,  10),
        (0.35, 135,  80,  15),
        (0.60, 215, 145,  25),
        (0.80, 250, 205,  70),
        (0.95, 255, 240, 175),
        (1.00, 255, 255, 255),
    ]
    create_interpolated_cpt(ch06_pts, "ch06.cpt")

    # CH07: Shortwave IR (3.90 µm) - Wildfire / Thermal anomaly (from thermal.cpt)
    shutil.copyfile(os.path.join(COLORS_DIR, "thermal.cpt"), os.path.join(COLORS_DIR, "ch07.cpt"))

    # CH08: Upper-Level Water Vapor (6.19 µm) - From SVGAWVX_TEMP.cpt
    shutil.copyfile(os.path.join(COLORS_DIR, "SVGAWVX_TEMP.cpt"), os.path.join(COLORS_DIR, "ch08.cpt"))

    # CH09: Mid-Level Water Vapor (6.95 µm) - From WV_red_black.cpt
    shutil.copyfile(os.path.join(COLORS_DIR, "WV_red_black.cpt"), os.path.join(COLORS_DIR, "ch09.cpt"))

    # CH10: Lower-Level Water Vapor (7.34 µm) - From WV.cpt
    shutil.copyfile(os.path.join(COLORS_DIR, "WV.cpt"), os.path.join(COLORS_DIR, "ch10.cpt"))

    # CH11: Cloud-Top Phase / Microphysics (8.50 µm) - Soft lilac to teal/green
    ch11_pts = [
        (-90.0, 250, 225, 255),
        (-70.0, 210, 150, 235),
        (-50.0, 120,  70, 160),
        (-30.0,  35, 105, 135),
        (-10.0,  40, 145, 115),
        ( 10.0, 110, 150,  95),
        ( 30.0, 115, 115, 115),
        ( 50.0,  20,  20,  20),
    ]
    create_interpolated_cpt(ch11_pts, "ch11.cpt")

    # CH12: Total Column Ozone (9.61 µm) - Magenta / Cobalt blue / Emerald green
    ch12_pts = [
        (-90.0, 185,  25, 145),
        (-65.0,  30,  55, 175),
        (-40.0,  15, 125, 150),
        (-15.0,  25, 165,  95),
        ( 10.0, 165, 155,  35),
        ( 30.0, 125,  65,  20),
        ( 50.0,  30,  30,  30),
    ]
    create_interpolated_cpt(ch12_pts, "ch12.cpt")

    # CH13: Clean Longwave IR Window (10.35 µm) - Realce Oklahoma (original colors.rainbow)
    colors_py_path = os.path.join(COLORS_DIR, "colors.py")
    ch13_pts = []
    if os.path.exists(colors_py_path):
        import re
        with open(colors_py_path, 'r', encoding='utf-8') as f:
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
            ch13_pts.append((temp, r, g, b))

    if ch13_pts:
        create_interpolated_cpt(ch13_pts, "ch13.cpt")
        create_interpolated_cpt(ch13_pts, "oklahoma.cpt")
    else:
        # Fallback if colors.py not found
        shutil.copyfile(os.path.join(COLORS_DIR, "thermal.cpt"), os.path.join(COLORS_DIR, "ch13.cpt"))

    # CH14: Traditional Longwave IR (11.20 µm) - From IR4AVHRR6.cpt
    shutil.copyfile(os.path.join(COLORS_DIR, "IR4AVHRR6.cpt"), os.path.join(COLORS_DIR, "ch14.cpt"))

    # CH15: Dirty Longwave IR (12.30 µm) - Dust / Split-window difference
    ch15_pts = [
        (-90.0, 245, 245, 255),
        (-60.0,  75,  95, 145),
        (-30.0, 125, 115,  90),
        (  0.0, 185, 155,  95),
        ( 25.0, 170, 120,  60),
        ( 50.0,  30,  25,  20),
    ]
    create_interpolated_cpt(ch15_pts, "ch15.cpt")

    # CH16: CO2 Longwave IR (13.30 µm) - Cloud-top height & tropospheric cooling
    ch16_pts = [
        (-90.0, 145,  45, 165),
        (-65.0,  35, 115, 165),
        (-40.0,  30, 155, 140),
        (-15.0,  65, 165,  95),
        ( 10.0, 175, 145,  45),
        ( 30.0,  95,  65,  45),
        ( 50.0,  25,  25,  25),
    ]
    create_interpolated_cpt(ch16_pts, "ch16.cpt")

    print("All 16 CPT color palettes generated successfully in", COLORS_DIR)

if __name__ == '__main__':
    build_all_palettes()

