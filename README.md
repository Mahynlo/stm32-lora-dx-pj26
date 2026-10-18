# STM32 LoRa — DX-PJ26 V1.2 + DX-LR30 (SX1262)

![STM32F103](https://img.shields.io/badge/MCU-STM32F103C8-03234B?logo=stmicroelectronics&logoColor=white)
![SX1262](https://img.shields.io/badge/LoRa-SX1262%20%2F%20DX--LR30-1E88E5)
![915 MHz](https://img.shields.io/badge/banda-915%20MHz-43A047)
![PlatformIO](https://img.shields.io/badge/PlatformIO-ststm32-F5822A?logo=platformio&logoColor=white)
![Arduino](https://img.shields.io/badge/framework-Arduino-00878F?logo=arduino&logoColor=white)
![RadioLib](https://img.shields.io/badge/RadioLib-%5E7.4.0-6A1B9A)

Enlace LoRa punto a punto entre dos placas **DX-SMART DX-PJ26 V1.2** (STM32F103C8T6) con módulo **DX-LR30-900M22S** (Semtech SX1262), usando **PlatformIO**, el framework **Arduino (stm32duino)** y la librería **[RadioLib](https://github.com/jgromes/RadioLib)**.

El mismo firmware sirve como transmisor o receptor: el TX envía `Hola #N` cada 2 s y el RX muestra el mensaje con su RSSI y SNR por el puerto serie.

> 📖 La guía completa con todo lo investigado (hardware, pinout, por qué falla `stm32flash`, errores y soluciones) está en **[docs/guia.md](docs/guia.md)**.

---

## Hardware

| Elemento | Detalle |
|---|---|
| Placa base | DX-SMART **DX-PJ26 V1.2** |
| MCU | STM32F103C8T6 (cristal de 8 MHz) |
| USB-serial | CH340C en USART1 (PA9 TX / PA10 RX) → `Serial1` |
| Módulo LoRa | DX-LR30-900M22S (SX1262, 850–930 MHz, SPI, **cristal, sin TCXO**) |
| LED de usuario | **PB11** (no PC13) |
| Antena | Obligatoria antes de transmitir |

### Pinout del SX1262 (confirmado en la V1.2)

| Señal | Pin STM32 |
|---|---|
| NSS | PA4 |
| SCK / MISO / MOSI | PA5 / PA6 / PA7 (SPI1) |
| RESET | PA3 |
| BUSY | PA2 |
| DIO1 | PC15 |
| TXEN | PA0 |
| RXEN | PA1 |

## Parámetros de radio

| Parámetro | Valor |
|---|---|
| Frecuencia | 915 MHz (banda ISM 902–928 MHz) |
| Ancho de banda | 125 kHz |
| Spreading factor | SF9 |
| Coding rate | 4/7 |
| Potencia | 10 dBm (hasta 22 dBm) |
| Preámbulo | 8 símbolos |
| Sync word | Privado (`RADIOLIB_SX126X_SYNC_WORD_PRIVATE`) |
| TCXO | `0.0` V (el módulo usa cristal) |

---

## Requisitos

- [VS Code](https://code.visualstudio.com/) + extensión [PlatformIO IDE](https://platformio.org/install/ide?install=vscode)
- [STM32CubeProgrammer](https://www.st.com/en/development-tools/stm32cubeprog.html) instalado en la ruta por defecto (probado con v2.23.0)
- Driver del CH340 (Windows)
- Dos placas DX-PJ26 V1.2 con antena

Las dependencias (`RadioLib ^7.4.0`, `SPI`) las descarga PlatformIO automáticamente.

## Estructura

```
├── docs/guia.md        # Guía detallada: hallazgos, pinout, errores y diagnóstico
├── src/main.cpp        # Firmware TX/RX con RadioLib
├── probar_app.py       # Prueba el arranque con distintas combinaciones RTS/DTR
├── platformio.ini      # Configuración del proyecto (upload con CubeProgrammer)
├── include/ lib/ test/ # Carpetas estándar de PlatformIO
```

---

## Uso

### 1. Elegir el modo

En [src/main.cpp](src/main.cpp):

```cpp
#define MODO_TX 1   // 1 = transmisor, 0 = receptor
```

### 2. Ajustar el puerto COM

En [platformio.ini](platformio.ini), cambia `COM3` por el puerto de tu placa (Administrador de dispositivos → "USB-SERIAL CH340") tanto en `upload_command` como en `monitor_port`.

### 3. Compilar y subir

```bash
pio run -t upload
```

1. Cierra el monitor serie y la GUI de CubeProgrammer.
2. Lanza el upload.
3. **Cuando aparezca el encabezado de STM32CubeProgrammer en la terminal, presiona y suelta RST** en la placa.
4. Al terminar (`Download verified successfully`) el programa arranca solo.

> ⚠️ El método por defecto de PlatformIO (`stm32flash`) **no funciona** en esta placa: la línea DTR no resetea el micro y el botón KEY no es BOOT0. Por eso se usa la CLI de CubeProgrammer con `rts=low dtr=low` + reset manual. Detalles en la [sección 2 de la guía](docs/guia.md#2-programación-subir-firmware).

### 4. Monitor serie

```bash
pio device monitor
```

115200 baudios. Si no aparece nada, presiona **RST** con el monitor abierto.

Salida esperada en el receptor:

```
--- LoRa RX ---
Radio OK
Escuchando...
Recibido: Hola #12  | RSSI: -35.00 dBm  | SNR: 9.75 dB
```

### Dos placas

1. Placa A con `MODO_TX 1` → subir.
2. Cambiar el COM al de la placa B.
3. Placa B con `MODO_TX 0` → subir.
4. Separarlas al menos ~1 m (a 10 dBm el receptor puede saturarse si están pegadas).

---

## Notas importantes

- Usa **`Serial1`** en todo el código; **no** agregues `-D SERIAL_UART_INSTANCE=1` (el programa se cuelga al arrancar).
- `tcxoVoltage = 0.0` en `radio.begin()` es obligatorio: el valor por defecto de RadioLib asume TCXO y hace que `begin()` falle.
- No muevas el jumper **VCC / 3V3**: con 5 V se puede dañar el módulo LoRa.
- **Nunca transmitas sin antena.**

## Pendientes

- [ ] Prueba de alcance (~300 m) subiendo la potencia hacia 22 dBm y ajustando SF/BW.
- [ ] Diseñar un protocolo propio sobre el enlace.
- [ ] Programación/depuración por SWD con ST-Link (header `V G D C`).

## Referencias

- [RadioLib](https://github.com/jgromes/RadioLib)
- [stm32duino Issue #2777 — STM32F103C8T6 with DX-LR30 or DX-LR20](https://github.com/stm32duino/Arduino_Core_STM32/issues/2777)
- [NeutralSystem/STM32_DX-LR20_LORA](https://github.com/NeutralSystem/STM32_DX-LR20_LORA)
- [scsrat/STM32_DX-LR30-SX1262_Lora](https://github.com/scsrat/STM32_DX-LR30-SX1262_Lora)
- [DX-SMART/LoRaModule](https://github.com/DX-SMART/LORAMODULE)
