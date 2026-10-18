# Placa DX-PJ26 V1.2 (DX-SMART) + DX-LR30-900M22S — Hallazgos y guía de uso

Documento de referencia con todo lo descubierto al poner en marcha la placa base **DX-PJ26 V1.2** de DX-SMART (STM32F103C8T6 + módulo LoRa **DX-LR30-900M22S** / SX1262) usando **PlatformIO** en Windows.

> **Resumen rápido**
> - **Subir firmware:** STM32CubeProgrammer (CLI o GUI) por UART con **RTS = Low, DTR = Low** y presionando **RST** justo después de iniciar la conexión. `stm32flash` (el método por defecto de PlatformIO) **no funciona** en esta placa.
> - **Serial:** usar `Serial1` (USART1, PA9/PA10). **No** usar el flag `-D SERIAL_UART_INSTANCE=1`: provoca que el programa se cuelgue.
> - **LED de usuario:** **PB11** ✅ confirmado (no PC13 como dice la documentación de la familia).
> - **Botón KEY:** no es BOOT0. Mantenerlo presionado no sirve para entrar al bootloader.
> - **Módulo LR30 (SX1262):** NSS PA4 · SPI1 PA5/PA6/PA7 · RESET PA3 · BUSY PA2 · **DIO1 PC15** · TXEN PA0 · RXEN PA1 — todos confirmados. Usa **cristal (sin TCXO)**: en RadioLib, `tcxoVoltage = 0.0`.
> - **Enlace LoRa TX/RX entre dos placas con RadioLib: funcionando** (sección 6).

---

## 1. Hardware identificado

| Elemento | Detalle |
|---|---|
| Placa base | DX-PJ26 **V1.2** (DX-SMART) |
| MCU | **STM32F103C8T6 original** (logo ST, marcado "MYS" = Malasia). CubeProgrammer reporta Chip ID `0x410`, Medium-density, bootloader v2.2, **128 KB de flash** (normal en muchos C8 originales; oficialmente se garantizan 64 KB) |
| Cristal principal | **8.000 MHz** (correcto para la configuración por defecto de `genericSTM32F103C8`) |
| Cristal RTC | 32.768 kHz (en PC14/PC15) |
| USB-serial | CH340C, conectado a **USART1 (PA9 = TX, PA10 = RX)**. En Windows aparece como "USB-SERIAL CH340" (en este equipo: **COM3**) |
| Conector | USB-C (alimentación + serial) |
| Botones | **RST** (reset real del MCU) y **KEY** (botón de usuario, **no** controla BOOT0) |
| LEDs | **POW** (rojo, encendido fijo) y **LED** de usuario junto a RST → **PB11** |
| Jumper superior izquierdo | Serigrafía **VCC / 3V3**: selector de alimentación. **No moverlo** (con 5 V podría dañar el LR30, que es de 3.3 V) |
| Header de 4 pines "V G D C" | Puerto **SWD** (VCC, GND, SWDIO, SWCLK). Permite programar/depurar con un ST-Link |
| Módulo LoRa | **DX-LR30-900M22S** (Semtech **SX1262**, 850–930 MHz, interfaz **SPI**), montado sobre un adaptador azul de 2×6 pines |
| Serigrafía del header | `MOSI MISO SCK NSS NRST BUSY RXEN TXEN` — la placa saca las señales del módulo a los pines |

---

## 2. Programación (subir firmware)

### 2.1 Por qué fallaba `stm32flash`

El método `upload_protocol = serial` de PlatformIO usa `stm32flash`. Siempre terminaba en:

```
Failed to init device, timeout.
```

Se probó todo lo siguiente **sin éxito**:

- Secuencia del fabricante `-i rts,-dtr,dtr:-rts,-dtr,dtr` (con y sin script de Python previo).
- Sostener KEY + presionar RST, soltando KEY antes/durante/después del upload.
- Velocidades 115200 y 9600.

**Causas encontradas:**

1. **KEY no es BOOT0.** En el esquemático de la placa hermana (LR20-SP) KEY va a **PB12** y el manual del fabricante lo define como "User-defined". Por eso KEY+RST solo reseteaba el micro en modo normal.
2. **Circuito de auto-descarga con transistores.** Según el esquemático (LR20-SP):
   - **RTS activo** → enciende un PNP (S8550) → **BOOT0 en alto** (BOOT0 tiene pull-down de 10 kΩ).
   - **RTS activo + DTR inactivo** → enciende un NPN (S8050) → **mantiene NRST en bajo** (micro en reset).
   - **RTS activo + DTR activo** → sale del reset con BOOT0 alto → **bootloader**.
3. En esta placa la parte de **DTR → reset no funciona** (confirmado también por otros usuarios), así que ninguna secuencia automática de `stm32flash` logra entrar al bootloader. Lo que sí funciona es **dejar RTS fijo** (BOOT0 alto) y **dar el reset con el botón RST**.

### 2.2 Método que funciona: STM32CubeProgrammer (GUI)

1. Cerrar cualquier monitor serial que use COM3.
2. En CubeProgrammer, arriba a la derecha, cambiar **ST-LINK → UART**.
3. Configurar:
   - Port: **COM3**
   - Baudrate: **115200**
   - Parity: **Even**
   - Data bits: 8 · Stop bits: 1.0 · Flow control: Off
   - **RTS: Low** · **DTR: Low**
4. Dar **Connect** e **inmediatamente** (menos de 1 s) presionar y soltar **RST** en la placa.
   - ⚠️ El orden importa: CubeProgrammer aplica RTS/DTR **al dar Connect**. Si se presiona RST antes, el micro arranca sin BOOT0 alto y sale `Timeout error occured while waiting for acknowledgement`.
5. Si conecta: estado "Connected", Chip ID 0x410 en *Target information*.
6. En **Erasing & Programming**:
   - File path: `.pio\build\genericSTM32F103C8\firmware.bin`
   - Start address: **`0x08000000`** (obligatorio con `.bin`)
   - Marcar **Verify programming** y **Run after programming**
   - **Start Programming** → "Download verified successfully".

### 2.3 Método que funciona: desde PlatformIO (CLI de CubeProgrammer)

Requiere STM32CubeProgrammer instalado (probado con v2.23.0) en la ruta por defecto.

```ini
upload_protocol = custom
upload_command = "C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe" -c port=COM3 br=115200 rts=low dtr=low -w $SOURCE 0x08000000 -v -s 0x08000000
```

Uso:

1. Cerrar el monitor serial y la GUI de CubeProgrammer (o darle Disconnect).
2. **Upload** en PlatformIO.
3. Cuando en la terminal aparezca el encabezado de **STM32CubeProgrammer**, presionar **RST**.
4. `-v` verifica y `-s 0x08000000` arranca el programa al terminar (no hace falta otro reset).

Salida esperada (resumen):

```
Activating device: OK
Chip ID: 0x410
BootLoader protocol version: 2.2
RTS: Low
Dtr: Low
...
Download verified successfully
RUNNING Program ...
Start operation achieved successfully
```

### 2.4 Alternativa: ST-Link por SWD

El header **V G D C** es SWD. Con un ST-Link V2 (V→3.3V, G→GND, D→SWDIO, C→SWCLK) se puede usar `upload_protocol = stlink` y `debug_tool = stlink`, sin depender de BOOT0 ni del CH340, y con depuración paso a paso. **No se probó** (no se tenía ST-Link), pero es la ruta más robusta si el método serial diera problemas.

---

## 3. Serial (monitor)

- El CH340 está en **USART1 → `Serial1`** (PA9/PA10).
- ❌ **No usar `-D SERIAL_UART_INSTANCE=1`.** Con ese flag el programa compilaba y se grababa bien, pero **no arrancaba** (ni serial ni LED). Al quitarlo y dejar solo `HAL_UART_MODULE_ENABLED` + `ENABLE_HWSERIAL1` (configuración del proyecto NeutralSystem, probada en esta familia de placas) todo funcionó.
- Usar `Serial1` en **todo** el código (no mezclar `Serial` y `Serial1`).
- `monitor_dtr = 0` y `monitor_rts = 0` para que el monitor deje RTS/DTR inactivos (BOOT0 bajo, sin reset).
- Si al abrir el monitor no sale nada, **presionar RST** con el monitor ya abierto.
- El primer carácter basura (`�`) al arrancar es normal.
- El firmware de fábrica manda datos a **9600** baudios.

---

## 4. Configuración final que funciona

### `platformio.ini`

```ini
[env:genericSTM32F103C8]
platform = ststm32
board = genericSTM32F103C8
framework = arduino

upload_protocol = custom
upload_command = "C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe" -c port=COM3 br=115200 rts=low dtr=low -w $SOURCE 0x08000000 -v -s 0x08000000

monitor_port = COM3
monitor_speed = 115200
monitor_dtr = 0
monitor_rts = 0

build_flags =
    -D HAL_UART_MODULE_ENABLED
    -D ENABLE_HWSERIAL1

; lib_deps =
;     SPI
;     jgromes/RadioLib @ ^7.4.0
```

### `src/main.cpp` (prueba de LED + serial)

```cpp
#include <Arduino.h>

#define LED_PIN PB11   // LED de usuario en la DX-PJ26 V1.2

void setup() {
  pinMode(LED_PIN, OUTPUT);

  // Serial1 = USART1 (PA9/PA10), conectado al CH340 de la placa
  Serial1.begin(115200);
  delay(200);
  Serial1.println("--- Sistema STM32 Iniciado ---");
}

void loop() {
  digitalWrite(LED_PIN, HIGH);
  Serial1.println("LED HIGH");
  delay(1000);

  digitalWrite(LED_PIN, LOW);
  Serial1.println("LED LOW");
  delay(1000);
}
```

> Pendiente de anotar: si el LED de PB11 enciende con **HIGH** o con **LOW**.

---

## 5. Pines

### 5.1 LED de usuario

| Fuente | Pin |
|---|---|
| Documentación / esquemático LR20-SP / proyecto NeutralSystem | PC13 |
| **DX-PJ26 V1.2 (medido y confirmado en esta placa)** | **PB11** ✅ — el LED enciende controlándolo desde PB11 |

Se encontró con un programa que hace parpadear uno por uno los pines candidatos y reporta por serial cuál está probando (ver sección 7.2). Esto demuestra que **la V1.2 tiene diferencias de cableado** respecto al esquemático de la LR20-SP: el resto del pinout debe verificarse antes de darlo por bueno.

### 5.2 Módulo LR30 (SX1262) — pinout CONFIRMADO en la V1.2 ✅

Verificado en esta placa con pruebas por software (ver sección 7.3 y 7.4) y con un enlace TX/RX funcionando entre dos placas.

| Señal del módulo | Pin STM32 | Cómo se confirmó |
|---|---|---|
| NSS | **PA4** | Lectura SPI del sync word por defecto (`0x14 0x24`) |
| SCK / MISO / MOSI | **PA5 / PA6 / PA7** (SPI1) | Ídem |
| RESET | **PA3** | BUSY baja después del reset |
| BUSY | **PA2** | Ídem |
| DIO1 | **PC15** | Se forzó un IRQ de timeout de RX y PC15 pasó a alto |
| TXEN | **PA0** | Enlace TX/RX funcionando con `setRfSwitchPins(PA1, PA0)` |
| RXEN | **PA1** | Ídem |

Otros datos confirmados:

- **El módulo usa cristal, no TCXO.** Entra en recepción sin configurar `SetDIO3AsTCXOCtrl`. En RadioLib hay que pasar **`tcxoVoltage = 0.0`** en `begin()`; el valor por defecto asume TCXO y es la causa típica de que `begin()` falle o "se cuelgue" en estas placas.
- **DIO1 sí está conectado** en la V1.2 (también aparece en la serigrafía del header). Algunos proyectos de la LR20-SP dicen lo contrario y usan *polling*; no aplica a esta placa.
- Serigrafía del conector del módulo (2×6, ▲ = VCC):

  | | |
  |---|---|
  | GND | VCC ▲ |
  | NRST | NSS |
  | SCK | MOSI |
  | MISO | DIO1 |
  | BUSY | DIO2 |
  | TXEN | RXEN |

- Al montar el adaptador del módulo: **USB desconectado**, VCC del lado del triángulo ▲ y los **12 pines dentro de los 12 agujeros** (si queda corrido una fila, VCC/GND caen en pines equivocados).

### 5.3 Pines a evitar en usos generales

| Pines | Motivo |
|---|---|
| PA9 / PA10 | USART1 ↔ CH340 (serial y bootloader) |
| PA11 / PA12 | Comparten las líneas D−/D+ del USB con el CH340 (un firmware que los use, p. ej. CAN o USB, puede impedir que Windows detecte el puerto) |
| PA13 / PA14 | SWD (header V G D C) |
| PA0–PA7 | Módulo LoRa |
| PC14 / PC15 | Cristal de 32.768 kHz (PC15 posiblemente DIO1) |

---

## 6. LoRa con RadioLib — FUNCIONANDO ✅

Enlace probado entre dos DX-PJ26 V1.2 a ~1 m en la mesa: 915 MHz, BW 125 kHz, SF9, CR 4/7, 10 dBm.

Resultado en el receptor: **RSSI entre −16 y −29 dBm, SNR ≈ 10–11 dB**, paquetes recibidos en secuencia. Apareció un único error de CRC aislado, normal en una prueba así (más aún con las placas tan cerca o si el transmisor se reinicia a media transmisión).

### `platformio.ini`

Igual al de la sección 4, agregando:

```ini
lib_deps =
    jgromes/RadioLib @ ^7.4.0
```

### `src/main.cpp` (mismo código para TX y RX, cambia `MODO_TX`)

```cpp
#include <Arduino.h>
#include <RadioLib.h>

#define MODO_TX 1   // 1 = transmisor, 0 = receptor

#define LED_PIN   PB11
#define LORA_NSS  PA4
#define LORA_DIO1 PC15
#define LORA_RST  PA3
#define LORA_BUSY PA2
#define LORA_TXEN PA0
#define LORA_RXEN PA1

SX1262 radio = new Module(LORA_NSS, LORA_DIO1, LORA_RST, LORA_BUSY);

volatile bool llegoPaquete = false;
void alRecibir() { llegoPaquete = true; }

void setup() {
  pinMode(LED_PIN, OUTPUT);
  Serial1.begin(115200);
  delay(300);
  Serial1.println(MODO_TX ? "\n--- LoRa TX ---" : "\n--- LoRa RX ---");

  // 915 MHz, BW 125 kHz, SF9, CR 4/7, sync word privado, 10 dBm,
  // preambulo 8, TCXO 0.0 V (el modulo usa cristal, no TCXO)
  int estado = radio.begin(915.0, 125.0, 9, 7,
                           RADIOLIB_SX126X_SYNC_WORD_PRIVATE, 10, 8, 0.0);
  if (estado != RADIOLIB_ERR_NONE) {
    Serial1.print("Error en begin(): ");
    Serial1.println(estado);
    while (true) { digitalWrite(LED_PIN, !digitalRead(LED_PIN)); delay(100); }
  }
  radio.setRfSwitchPins(LORA_RXEN, LORA_TXEN);
  Serial1.println("Radio OK");

#if !MODO_TX
  radio.setPacketReceivedAction(alRecibir);
  radio.startReceive();
  Serial1.println("Escuchando...");
#endif
}

void loop() {
#if MODO_TX
  static uint32_t contador = 0;
  String msg = "Hola #" + String(contador++);

  digitalWrite(LED_PIN, HIGH);
  int estado = radio.transmit(msg);
  digitalWrite(LED_PIN, LOW);

  if (estado == RADIOLIB_ERR_NONE) {
    Serial1.print("Enviado: ");
    Serial1.println(msg);
  } else {
    Serial1.print("Error al transmitir: ");
    Serial1.println(estado);
  }
  delay(2000);

#else
  if (llegoPaquete) {
    llegoPaquete = false;
    String msg;
    int estado = radio.readData(msg);

    if (estado == RADIOLIB_ERR_NONE) {
      Serial1.print("Recibido: ");
      Serial1.print(msg);
      Serial1.print("  | RSSI: ");
      Serial1.print(radio.getRSSI());
      Serial1.print(" dBm  | SNR: ");
      Serial1.print(radio.getSNR());
      Serial1.println(" dB");
      digitalWrite(LED_PIN, HIGH); delay(50); digitalWrite(LED_PIN, LOW);
    } else if (estado == RADIOLIB_ERR_CRC_MISMATCH) {
      Serial1.println("Paquete con error de CRC");
    } else {
      Serial1.print("Error al leer: ");
      Serial1.println(estado);
    }
    radio.startReceive();
  }
#endif
}
```

### Subir a dos placas

1. Placa A con `MODO_TX 1`.
2. Conectar la placa B, ver su COM en el Administrador de dispositivos y cambiar `COM3` por ese número en `upload_command` y `monitor_port`.
3. Placa B con `MODO_TX 0`.

### Notas

- **Siempre con antena** antes de transmitir; transmitir sin antena puede dañar el módulo.
- En la mesa, separar las placas al menos ~1 m a 10 dBm para no saturar el receptor.
- 915 MHz está dentro de la banda ISM de 902–928 MHz usada en México. Para pruebas de alcance se puede subir la potencia hasta 22 dBm.
- Referencia alternativa: **NeutralSystem/STM32_DX-LR20_LORA** usa un driver SX1262 propio (sin RadioLib) basado en el código del fabricante.

---

## 7. Herramientas de diagnóstico usadas

### 7.1 Probar el arranque del programa con distintos RTS/DTR (`probar_app.py`)

Abre COM3 con cada combinación de RTS/DTR, pide presionar RST y escucha 3 s. Se ejecuta con el Python de PlatformIO (que trae `pyserial`):

```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\python.exe" .\probar_app.py
```

```python
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
```

(Con el python del sistema falla con `ModuleNotFoundError: No module named 'serial'` → usar el de PlatformIO o `pip install pyserial`.)

### 7.2 Buscador del pin del LED

```cpp
#include <Arduino.h>

// Se excluyen PA9/PA10 (serial), PA11/PA12 (USB), PA13/PA14 (SWD),
// PA0-PA7 (módulo LoRa) y PC14/PC15 (cristal)
struct PinInfo { uint32_t pin; const char* nombre; };
PinInfo pines[] = {
  {PC13, "PC13"}, {PB0, "PB0"}, {PB1, "PB1"}, {PB2, "PB2"},
  {PB3, "PB3"},   {PB4, "PB4"}, {PB5, "PB5"}, {PB6, "PB6"},
  {PB7, "PB7"},   {PB8, "PB8"}, {PB9, "PB9"}, {PB10, "PB10"},
  {PB11, "PB11"}, {PB12, "PB12"}, {PB13, "PB13"}, {PB14, "PB14"},
  {PB15, "PB15"}, {PA8, "PA8"}, {PA15, "PA15"}
};
const int N = sizeof(pines) / sizeof(pines[0]);

void setup() {
  Serial1.begin(115200);
  delay(500);
  Serial1.println("--- Buscando el pin del LED ---");
}

void loop() {
  for (int i = 0; i < N; i++) {
    Serial1.print("Probando ");
    Serial1.println(pines[i].nombre);
    pinMode(pines[i].pin, OUTPUT);
    for (int k = 0; k < 5; k++) {
      digitalWrite(pines[i].pin, LOW);  delay(200);
      digitalWrite(pines[i].pin, HIGH); delay(200);
    }
    pinMode(pines[i].pin, INPUT);
  }
  Serial1.println("--- Vuelta completa, reiniciando ---");
}
```

Resultado en esta placa: **PB11**.

### 7.3 Prueba SPI del SX1262 (sin transmitir)

Resetea el módulo, espera BUSY y lee el registro del sync word (0x0740/0x0741), cuyo valor de fábrica es `0x14 0x24`. Confirma NSS, RESET, BUSY y SPI1.

```cpp
#include <Arduino.h>
#include <SPI.h>

#define LED_PIN   PB11
#define LORA_NSS  PA4
#define LORA_RST  PA3
#define LORA_BUSY PA2
#define LORA_TXEN PA0
#define LORA_RXEN PA1

bool esperarBusy(uint32_t ms) {
  uint32_t t = millis();
  while (digitalRead(LORA_BUSY) == HIGH) {
    if (millis() - t > ms) return false;
  }
  return true;
}

uint8_t leerStatus() {
  esperarBusy(100);
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(LORA_NSS, LOW);
  SPI.transfer(0xC0);                 // GetStatus
  uint8_t s = SPI.transfer(0x00);
  digitalWrite(LORA_NSS, HIGH);
  SPI.endTransaction();
  return s;
}

uint8_t leerRegistro(uint16_t addr) {
  esperarBusy(100);
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(LORA_NSS, LOW);
  SPI.transfer(0x1D);                 // ReadRegister
  SPI.transfer(addr >> 8);
  SPI.transfer(addr & 0xFF);
  SPI.transfer(0x00);                 // byte de status
  uint8_t v = SPI.transfer(0x00);
  digitalWrite(LORA_NSS, HIGH);
  SPI.endTransaction();
  return v;
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  pinMode(LORA_NSS, OUTPUT);   digitalWrite(LORA_NSS, HIGH);
  pinMode(LORA_RST, OUTPUT);   digitalWrite(LORA_RST, HIGH);
  pinMode(LORA_TXEN, OUTPUT);  digitalWrite(LORA_TXEN, LOW);
  pinMode(LORA_RXEN, OUTPUT);  digitalWrite(LORA_RXEN, LOW);
  pinMode(LORA_BUSY, INPUT);

  Serial1.begin(115200);
  delay(300);
  Serial1.println("\n--- Prueba SPI del SX1262 ---");
  SPI.begin();   // SPI1: PA5 SCK, PA6 MISO, PA7 MOSI

  digitalWrite(LORA_RST, LOW);  delay(2);
  digitalWrite(LORA_RST, HIGH); delay(10);

  if (esperarBusy(500)) Serial1.println("BUSY: OK (bajo después del reset)");
  else                  Serial1.println("BUSY: TIMEOUT (sigue en alto)");

  uint8_t st = leerStatus();
  Serial1.print("Status: 0x"); Serial1.println(st, HEX);

  uint8_t sw1 = leerRegistro(0x0740);
  uint8_t sw2 = leerRegistro(0x0741);
  Serial1.print("Sync word: 0x"); Serial1.print(sw1, HEX);
  Serial1.print(" 0x");           Serial1.println(sw2, HEX);

  if (sw1 == 0x14 && sw2 == 0x24) Serial1.println(">>> SX1262 detectado: pinout correcto");
  else                            Serial1.println(">>> No coincide: revisar pines");
}

void loop() {
  digitalWrite(LED_PIN, HIGH); delay(500);
  digitalWrite(LED_PIN, LOW);  delay(500);
}
```

Resultado en esta placa:

```
BUSY: OK (bajo después del reset)
Status: 0x22
Sync word: 0x14 0x24
>>> SX1262 detectado: pinout correcto
```

### 7.4 Buscador del pin de DIO1 (sin transmitir)

Configura el SX1262 para que el IRQ de *timeout* de RX salga por DIO1, lo pone a recibir 25 ms y revisa qué pin candidato del STM32 pasó de bajo a alto (los candidatos con `INPUT_PULLDOWN` para evitar falsos positivos).

```cpp
#include <Arduino.h>
#include <SPI.h>

#define LED_PIN   PB11
#define LORA_NSS  PA4
#define LORA_RST  PA3
#define LORA_BUSY PA2
#define LORA_TXEN PA0
#define LORA_RXEN PA1

struct PinInfo { uint32_t pin; const char* nombre; };
PinInfo cand[] = {
  {PC13,"PC13"}, {PC14,"PC14"}, {PC15,"PC15"}, {PB0,"PB0"}, {PB1,"PB1"},
  {PB2,"PB2"}, {PB3,"PB3"}, {PB4,"PB4"}, {PB5,"PB5"}, {PB6,"PB6"},
  {PB7,"PB7"}, {PB8,"PB8"}, {PB9,"PB9"}, {PB10,"PB10"}, {PB12,"PB12"},
  {PB13,"PB13"}, {PB14,"PB14"}, {PB15,"PB15"}, {PA8,"PA8"}, {PA15,"PA15"}
};
const int N = sizeof(cand) / sizeof(cand[0]);

void esperarBusy() {
  uint32_t t = millis();
  while (digitalRead(LORA_BUSY) == HIGH && millis() - t < 100) {}
}

void comando(const uint8_t* buf, uint8_t n, uint8_t* resp = nullptr) {
  esperarBusy();
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(LORA_NSS, LOW);
  for (uint8_t i = 0; i < n; i++) {
    uint8_t r = SPI.transfer(buf[i]);
    if (resp) resp[i] = r;
  }
  digitalWrite(LORA_NSS, HIGH);
  SPI.endTransaction();
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  pinMode(LORA_NSS, OUTPUT);  digitalWrite(LORA_NSS, HIGH);
  pinMode(LORA_RST, OUTPUT);  digitalWrite(LORA_RST, HIGH);
  pinMode(LORA_TXEN, OUTPUT); digitalWrite(LORA_TXEN, LOW);
  pinMode(LORA_RXEN, OUTPUT); digitalWrite(LORA_RXEN, LOW);
  pinMode(LORA_BUSY, INPUT);
  for (int i = 0; i < N; i++) pinMode(cand[i].pin, INPUT_PULLDOWN);

  Serial1.begin(115200);
  delay(300);
  Serial1.println("\n--- Buscando el pin de DIO1 ---");
  SPI.begin();

  digitalWrite(LORA_RST, LOW);  delay(2);
  digitalWrite(LORA_RST, HIGH); delay(10);
  esperarBusy();

  const uint8_t standby[]  = {0x80, 0x00};                           // SetStandby RC
  const uint8_t tipoLoRa[] = {0x8A, 0x01};                           // SetPacketType LoRa
  const uint8_t freq[]     = {0x86, 0x39, 0x30, 0x00, 0x00};         // 915 MHz
  const uint8_t irqCfg[]   = {0x08, 0x02,0x00, 0x02,0x00, 0,0, 0,0}; // Timeout -> DIO1
  const uint8_t limpiar[]  = {0x02, 0xFF, 0xFF};                     // ClearIrqStatus
  const uint8_t rx25ms[]   = {0x82, 0x00, 0x06, 0x40};               // SetRx, timeout 25 ms

  comando(standby, 2);
  comando(tipoLoRa, 2);
  comando(freq, 5);
  comando(irqCfg, 9);
  comando(limpiar, 3);

  bool antes[N];
  for (int i = 0; i < N; i++) antes[i] = digitalRead(cand[i].pin);

  digitalWrite(LORA_RXEN, HIGH);
  comando(rx25ms, 4);
  delay(60);

  uint8_t pedirIrq[] = {0x12, 0x00, 0x00, 0x00};                     // GetIrqStatus
  uint8_t resp[4];
  comando(pedirIrq, 4, resp);
  uint16_t irq = (resp[2] << 8) | resp[3];
  Serial1.print("IRQ status: 0x"); Serial1.println(irq, HEX);
  if (irq & 0x0200) Serial1.println("Timeout disparado (correcto)");
  else              Serial1.println("No se disparo el timeout");

  bool encontrado = false;
  for (int i = 0; i < N; i++) {
    bool ahora = digitalRead(cand[i].pin);
    if (!antes[i] && ahora) {
      Serial1.print(">>> DIO1 esta en: ");
      Serial1.println(cand[i].nombre);
      encontrado = true;
    }
  }
  if (!encontrado) Serial1.println(">>> Ningun candidato cambio");

  digitalWrite(LORA_RXEN, LOW);
  comando(limpiar, 3);
  comando(standby, 2);
}

void loop() {
  digitalWrite(LED_PIN, HIGH); delay(500);
  digitalWrite(LED_PIN, LOW);  delay(500);
}
```

Resultado en esta placa:

```
IRQ status: 0x200
Timeout disparado (correcto)
>>> DIO1 esta en: PC15
```

Que el timeout se disparara sin configurar TCXO es lo que confirma que el módulo usa **cristal**.

---

## 8. Tabla de errores encontrados

| Síntoma / mensaje | Causa | Solución |
|---|---|---|
| `Failed to init device, timeout.` (stm32flash) | El micro nunca entra al bootloader: DTR no resetea y KEY no es BOOT0 | Usar CubeProgrammer con RTS Low / DTR Low + RST |
| `Timeout error occured while waiting for acknowledgement` (CubeProgrammer) | RST presionado **antes** de Connect | Dar Connect primero y RST inmediatamente después |
| Puerto "No CO..." en CubeProgrammer | COM3 ocupado o placa desconectada | Cerrar monitores, refrescar puerto |
| `STM32CubeProgrammer not found (STM32_Programmer_CLI.exe)` (Arduino IDE) | CubeProgrammer no instalado / no está en el PATH | Instalar y agregar `C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin` al PATH |
| Upload "Download verified successfully" pero no hay LED ni serial | Flag `-D SERIAL_UART_INSTANCE=1` | Quitar el flag; dejar `HAL_UART_MODULE_ENABLED` + `ENABLE_HWSERIAL1` |
| Serial funciona pero el LED no parpadea | El LED de la V1.2 no está en PC13 | Usar **PB11** |
| Monitor abierto sin mensajes | El micro quedó en bootloader / no se reinició | Presionar RST con el monitor abierto |
| `ModuleNotFoundError: No module named 'serial'` | Python del sistema sin pyserial | Usar el Python de PlatformIO |
| `radio.begin()` falla o se cuelga (reportado por otros usuarios) | RadioLib asume TCXO por defecto; esta placa usa cristal | Pasar `tcxoVoltage = 0.0` en `begin()` y el pinout de la sección 5.2 |
| Un "Paquete con error de CRC" aislado | Normal en pruebas muy cercanas o si el TX se reinicia a media transmisión | Ignorar si es esporádico; si es frecuente, separar las placas o bajar potencia |

---

## 9. Cosas descartadas

- **Reloj / cristal:** el cristal es de 8 MHz (correcto). La prueba con el oscilador interno (HSI) no fue necesaria para la solución final.
- **Chip clon:** el chip es STM32 original; los 128 KB reportados son normales.
- **Script `reset_sequence.py` y flags `-i` de stm32flash:** no funcionan en esta placa; ya no se usan.
- **Jumper VCC/3V3:** es de alimentación, no de BOOT0.

---

## 10. Pendientes

- [x] Confirmar el pin del LED de usuario → **PB11**.
- [ ] Anotar si el LED de PB11 enciende con HIGH o con LOW.
- [x] Verificar en la V1.2 el pinout del LR30 → confirmado (sección 5.2), DIO1 en **PC15**.
- [x] Prueba del LR30 con RadioLib con antena → **enlace TX/RX funcionando** (sección 6).
- [ ] Prueba de alcance (~300 m con árboles y ~2 m de desnivel), subiendo potencia hacia 22 dBm y ajustando SF/BW si hace falta.
- [ ] Diseñar el protocolo propio sobre el enlace.
- [ ] (Opcional) Conseguir un ST-Link para programar/depurar por SWD.

---

## 11. Referencias

- [stm32duino Issue #2777 — STM32F103C8T6 with DX-LR30 or DX-LR20](https://github.com/stm32duino/Arduino_Core_STM32/issues/2777) (esquemático LR20-SP, manuales, experiencias de flasheo)
- [Manual de la placa de desarrollo DX-LR20-900M22SP (DX-SMART)](https://github.com/user-attachments/files/21432367/DX-LR20-900M22SP.Development.board.user_s.manual.pdf)
- [Esquemático PCBA LR20-SP](https://github.com/user-attachments/files/21432463/LR20-SP.PCBA.schematic.diagram.pdf)
- [NeutralSystem/STM32_DX-LR20_LORA](https://github.com/NeutralSystem/STM32_DX-LR20_LORA) — proyecto PlatformIO funcional en esta familia de placas (configuración de serial, driver SX1262 propio)
- [scsrat/STM32_DX-LR30-SX1262_Lora](https://github.com/scsrat/STM32_DX-LR30-SX1262_Lora) — repetidor compatible con Meshtastic para STM32F103 + DX-LR30
- [DX-SMART/LoRaModule](https://github.com/DX-SMART/LORAMODULE) — paquetes de desarrollo del fabricante (incluye DX-LR30-900Mhz)
- [STM32CubeProgrammer (ST)](https://www.st.com/en/development-tools/stm32cubeprog.html)