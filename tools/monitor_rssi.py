# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyserial>=3.5",
#     "matplotlib>=3.8",
# ]
# ///
"""
Monitor serie del receptor LoRa (DX-PJ26 + SX1262).

Muestra en tiempo real los mensajes del puerto serie y grafica la
intensidad de señal (RSSI) y la relación señal/ruido (SNR) de cada
paquete recibido. Opcionalmente guarda los datos en un CSV.

Uso (uv instala las dependencias automáticamente):
    uv run tools/monitor_rssi.py                 # COM3 a 115200
    uv run tools/monitor_rssi.py --port COM5
    uv run tools/monitor_rssi.py --csv datos.csv
    uv run tools/monitor_rssi.py --list          # lista los puertos

El firmware RX imprime líneas como:
    Recibido: Hola #12  | RSSI: -35.00 dBm  | SNR: 9.75 dB
"""

import argparse
import csv
import queue
import re
import sys
import threading
import time
from collections import deque
from datetime import datetime

import serial
import serial.tools.list_ports
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

PATRON = re.compile(
    r"Recibido:\s*(?P<msg>.*?)\s*\|\s*RSSI:\s*(?P<rssi>-?\d+(?:\.\d+)?)\s*dBm"
    r"\s*\|\s*SNR:\s*(?P<snr>-?\d+(?:\.\d+)?)\s*dB"
)
PATRON_CONTADOR = re.compile(r"#(\d+)")

MAX_PUNTOS = 200   # paquetes visibles en la gráfica
MAX_LINEAS = 12    # líneas visibles en el panel de mensajes


def calidad(rssi):
    if rssi >= -70:
        return "Excelente"
    if rssi >= -90:
        return "Buena"
    if rssi >= -110:
        return "Regular"
    return "Débil"


# -----------------------------serie ------------------------------------- 

def abrir_puerto(port, baud):
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.timeout = 0.2
    # RTS/DTR inactivos: con RTS activo la placa pone BOOT0 en alto
    # y al reiniciarse entraría al bootloader (ver docs/guia.md §3).
    ser.rts = False
    ser.dtr = False
    ser.open()
    return ser


def lector(ser, cola, parar):
    buffer = b""
    while not parar.is_set():
        try:
            buffer += ser.read(256)
        except serial.SerialException as e:
            cola.put(("error", str(e)))
            return
        while b"\n" in buffer:
            linea, buffer = buffer.split(b"\n", 1)
            texto = linea.decode("utf-8", errors="replace").strip()
            if texto:
                cola.put(("linea", texto))


# --------------------------- datos --------------------------------------

class Estado:
    def __init__(self, archivo_csv):
        self.n = deque(maxlen=MAX_PUNTOS)
        self.rssi = deque(maxlen=MAX_PUNTOS)
        self.snr = deque(maxlen=MAX_PUNTOS)
        self.lineas = deque(maxlen=MAX_LINEAS)
        self.recibidos = 0
        self.errores_crc = 0
        self.perdidos = 0
        self.ultimo_contador = None
        self.rssi_min = None
        self.rssi_max = None
        self.rssi_suma = 0.0

        self.csv = None
        if archivo_csv:
            f = open(archivo_csv, "w", newline="", encoding="utf-8")
            self.csv = (f, csv.writer(f))
            self.csv[1].writerow(["fecha_hora", "paquete", "mensaje", "rssi_dbm", "snr_db"])

    def procesar(self, texto):
        hora = datetime.now().strftime("%H:%M:%S")
        print(f"[{hora}] {texto}")
        self.lineas.append(f"[{hora}] {texto}")

        if "error de CRC" in texto:
            self.errores_crc += 1
            return

        m = PATRON.search(texto)
        if not m:
            return

        msg = m["msg"]
        rssi = float(m["rssi"])
        snr = float(m["snr"])
        self.recibidos += 1

        c = PATRON_CONTADOR.search(msg)
        if c:
            contador = int(c[1])
            if self.ultimo_contador is not None and contador > self.ultimo_contador + 1:
                self.perdidos += contador - self.ultimo_contador - 1
            self.ultimo_contador = contador

        self.n.append(self.recibidos)
        self.rssi.append(rssi)
        self.snr.append(snr)
        self.rssi_min = rssi if self.rssi_min is None else min(self.rssi_min, rssi)
        self.rssi_max = rssi if self.rssi_max is None else max(self.rssi_max, rssi)
        self.rssi_suma += rssi

        if self.csv:
            self.csv[1].writerow([datetime.now().isoformat(timespec="seconds"), self.recibidos, msg, rssi, snr])
            self.csv[0].flush()

    def resumen(self):
        if not self.recibidos:
            return "Esperando paquetes..."
        total = self.recibidos + self.perdidos
        perdida = 100 * self.perdidos / total if total else 0
        return (
            f"Último RSSI: {self.rssi[-1]:.1f} dBm ({calidad(self.rssi[-1])})   "
            f"SNR: {self.snr[-1]:.1f} dB\n"
            f"RSSI mín/prom/máx: {self.rssi_min:.1f} / "
            f"{self.rssi_suma / self.recibidos:.1f} / {self.rssi_max:.1f} dBm\n"
            f"Recibidos: {self.recibidos}   Perdidos: {self.perdidos} ({perdida:.1f} %)   "
            f"Errores CRC: {self.errores_crc}"
        )

    def cerrar(self):
        if self.csv:
            self.csv[0].close()


# ---------------------------------- gráfica -----------------------------

def main():
    ap = argparse.ArgumentParser(description="Monitor de RSSI/SNR del receptor LoRa")
    ap.add_argument("--port", default="COM3", help="puerto serie (por defecto COM3)")
    ap.add_argument("--baud", type=int, default=115200, help="baudios (por defecto 115200)")
    ap.add_argument("--csv", help="guardar los paquetes recibidos en este archivo CSV")
    ap.add_argument("--list", action="store_true", help="listar puertos disponibles y salir")
    args = ap.parse_args()

    # El primer carácter basura al arrancar la placa rompe la consola cp1252
    sys.stdout.reconfigure(errors="replace")

    if args.list:
        for p in serial.tools.list_ports.comports():
            print(f"{p.device:8} {p.description}")
        return

    try:
        ser = abrir_puerto(args.port, args.baud)
    except serial.SerialException as e:
        print(f"No se pudo abrir {args.port}: {e}")
        print("¿Está cerrado el monitor de PlatformIO? Usa --list para ver los puertos.")
        sys.exit(1)

    print(f"Conectado a {args.port} @ {args.baud}. Presiona RST si no aparece nada.")
    estado = Estado(args.csv)
    cola = queue.Queue()
    parar = threading.Event()
    threading.Thread(target=lector, args=(ser, cola, parar), daemon=True).start()

    fig = plt.figure(f"Monitor LoRa — {args.port}", figsize=(11, 8))
    gs = fig.add_gridspec(4, 1, height_ratios=[3, 2, 0.9, 2.2], hspace=0.45)
    ax_rssi = fig.add_subplot(gs[0])
    ax_snr = fig.add_subplot(gs[1], sharex=ax_rssi)
    ax_stats = fig.add_subplot(gs[2])
    ax_log = fig.add_subplot(gs[3])

    # Franjas de calidad de señal de fondo
    for lo, hi, color in [(-70, 0, "#c8e6c9"), (-90, -70, "#fff9c4"),
                          (-110, -90, "#ffe0b2"), (-140, -110, "#ffcdd2")]:
        ax_rssi.axhspan(lo, hi, color=color, alpha=0.6, zorder=0)
    (l_rssi,) = ax_rssi.plot([], [], "o-", color="#1565c0", ms=3, lw=1.5)
    ax_rssi.set_title("Intensidad de señal (RSSI)")
    ax_rssi.set_ylabel("dBm")
    ax_rssi.grid(alpha=0.3)

    ax_snr.axhline(0, color="gray", lw=0.8)
    (l_snr,) = ax_snr.plot([], [], "o-", color="#6a1b9a", ms=3, lw=1.5)
    ax_snr.set_title("Relación señal/ruido (SNR)")
    ax_snr.set_ylabel("dB")
    ax_snr.set_xlabel("Paquete")
    ax_snr.grid(alpha=0.3)

    for ax in (ax_stats, ax_log):
        ax.axis("off")
    t_stats = ax_stats.text(0, 1, "", va="top", family="monospace", fontsize=10, weight="bold")
    t_log = ax_log.text(0, 1, "", va="top", family="monospace", fontsize=8.5)
    ax_log.set_title("Mensajes del puerto serie", loc="left", fontsize=10)

    def actualizar(_):
        while True:
            try:
                tipo, texto = cola.get_nowait()
            except queue.Empty:
                break
            if tipo == "error":
                estado.lineas.append(f"!! Puerto desconectado: {texto}")
            else:
                estado.procesar(texto)

        if estado.n:
            l_rssi.set_data(estado.n, estado.rssi)
            l_snr.set_data(estado.n, estado.snr)
            x0, x1 = estado.n[0], max(estado.n[-1], estado.n[0] + 10)
            ax_rssi.set_xlim(x0, x1)
            ax_rssi.set_ylim(min(min(estado.rssi) - 10, -120), max(max(estado.rssi) + 10, -20))
            ax_snr.set_ylim(min(min(estado.snr) - 3, -20), max(max(estado.snr) + 3, 15))

        t_stats.set_text(estado.resumen())
        t_log.set_text("\n".join(estado.lineas))
        return l_rssi, l_snr, t_stats, t_log

    anim = FuncAnimation(fig, actualizar, interval=200, cache_frame_data=False)  # noqa: F841
    try:
        plt.show()
    finally:
        parar.set()
        ser.close()
        estado.cerrar()


if __name__ == "__main__":
    main()
