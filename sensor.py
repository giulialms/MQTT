# sensor.py - Sensor de temperatura simulado da caldeira.
# Publica uma leitura de temperatura no broker MQTT a cada X segundos.

import argparse          # para ler opções da linha de comando (--id, --intervalo...)
import json              # para transformar a leitura em texto JSON
import random            # para inventar variações de temperatura
import sys               # para encerrar o programa em caso de erro
import time              # para esperar entre leituras e pegar a hora

import paho.mqtt.client as mqtt   # biblioteca MQTT

BROKER = "localhost"               # o Mosquitto está rodando no seu computador
PORTA = 1883                       # porta padrão do MQTT (sem criptografia)
TOPICO = "caldeira/temperatura"    # "assunto" onde os sensores publicam

# --- Opções que você pode passar ao rodar o programa ---
parser = argparse.ArgumentParser(description="Sensor de temperatura simulado")
parser.add_argument("--id", default="sensor1", help="nome do sensor (ex: s1, s2)")
parser.add_argument("--intervalo", type=float, default=60,
                    help="segundos entre leituras (padrão 60, como no enunciado)")
parser.add_argument("--aquecer", action="store_true",
                    help="faz a temperatura subir sem parar, para disparar os alarmes")
args = parser.parse_args()

# --- Conecta ao broker ---
cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=args.id)
try:
    cliente.connect(BROKER, PORTA)
except ConnectionRefusedError:
    print("Não consegui conectar. O Mosquitto está rodando?")
    sys.exit(1)
cliente.loop_start()   # cuida da comunicação com o broker em segundo plano

# Temperatura inicial aleatória entre 80 e 100 graus
temperatura = random.uniform(80, 100)
print(f"Sensor {args.id} iniciado. Publicando em '{TOPICO}'. Ctrl+C para parar.")

try:
    while True:
        if args.aquecer:
            temperatura += random.uniform(8, 15)    # sobe bastante a cada leitura
        else:
            temperatura += random.uniform(-1, 1)    # varia só um pouquinho

        # Monta a mensagem com os dados da leitura
        leitura = {
            "sensor_id": args.id,
            "temperatura": round(temperatura, 2),
            "timestamp": time.time(),               # hora atual em segundos
        }

        # Publica a mensagem (json.dumps converte o dicionário em texto)
        cliente.publish(TOPICO, json.dumps(leitura))
        print(f"[{args.id}] enviou {leitura['temperatura']} °C")

        time.sleep(args.intervalo)                  # espera até a próxima leitura
except KeyboardInterrupt:
    print("\nSensor encerrado.")
finally:
    cliente.loop_stop()
    cliente.disconnect()