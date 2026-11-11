import numpy as np
import colorsys
import logging

# Configuración inicial de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def loadCPT(path):
    try:
        f = open(path)
    except FileNotFoundError:
        logging.info("File %s not found", path)
        return None

    lines = f.readlines()
    f.close()

    x = np.array([])
    r = np.array([])
    g = np.array([])
    b = np.array([])

    colorModel = 'RGB'

    for l in lines:
        # Ignorar líneas vacías o comentarios
        if l.strip() == '' or l.startswith('#'):
            continue

        ls = l.split()

        # Ignorar líneas que empiezan con B, F o N (colores especiales)
        if len(ls) >= 1 and ls[0] in ['B', 'F', 'N']:
            continue

        # Verificar si la línea tiene suficientes elementos
        if len(ls) < 4:
            continue  # Opcionalmente puedes dejar un print si quieres ver errores reales

        # Procesar el primer color
        try:
            x = np.append(x, float(ls[0]))
            r = np.append(r, float(ls[1]))
            g = np.append(g, float(ls[2]))
            b = np.append(b, float(ls[3]))
        except ValueError:
            continue  # Saltar línea no numérica

        # Procesar el segundo color (si está presente)
        if len(ls) >= 8:
            try:
                x = np.append(x, float(ls[4]))
                r = np.append(r, float(ls[5]))
                g = np.append(g, float(ls[6]))
                b = np.append(b, float(ls[7]))
            except ValueError:
                continue  # Saltar línea no numérica

    # Conversión HSV a RGB si es necesario
    if colorModel == 'HSV':
        for i in range(len(r)):
            h = r[i] / 360.0
            s = g[i]
            v = b[i]
            rr, gg, bb = colorsys.hsv_to_rgb(h, s, v)
            r[i], g[i], b[i] = rr, gg, bb

    # Normalizar a [0,1] si es RGB con valores enteros
    if colorModel == 'RGB':
        r = r / 255.0
        g = g / 255.0
        b = b / 255.0

    xNorm = (x - x[0]) / (x[-1] - x[0])

    red = []
    green = []
    blue = []

    for i in range(len(x)):
        red.append([xNorm[i], r[i], r[i]])
        green.append([xNorm[i], g[i], g[i]])
        blue.append([xNorm[i], b[i], b[i]])

    colorDict = {'red': red, 'green': green, 'blue': blue}

    return colorDict