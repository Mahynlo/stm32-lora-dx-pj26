import serial, time

PORT = "COM3"

for rts in (False, True):
    for dtr in (False, True):
        ser = serial.Serial()
        ser.port = PORT
        ser.baudrate = 115200
        ser.timeout = 0.2
        ser.rts = rts
        ser.dtr = dtr
        ser.open()
        input(f"\nRTS={rts} DTR={dtr} -> presiona y suelta RST, luego Enter...")
        ser.reset_input_buffer()
        datos = b""
        fin = time.time() + 3
        while time.time() < fin:
            datos += ser.read(100)
        print("Recibido:", datos[:200] if datos else "nada")
        ser.close()
        time.sleep(0.3)