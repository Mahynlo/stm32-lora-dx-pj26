#include <Arduino.h>
#include <RadioLib.h>

#define MODO_TX 0   // 1 = transmisor, 0 = receptor

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