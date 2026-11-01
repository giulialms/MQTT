# alarms.py - Serviço Alarms.
# Escuta os alertas publicados pelo CAT e mostra um aviso para o operador.

import json              # ler as mensagens JSON
import sys               # encerrar o programa em caso de erro
import time              # converter a hora do alerta para texto legível

import paho.mqtt.client as mqtt

BROKER = "localhost"
PORTA = 1883
TOPICO_ALERTAS = "caldeira/alertas"

# Texto que será mostrado para cada tipo de alerta
MENSAGENS = {
    "aumento_repentino": "AUMENTO REPENTINO de temperatura! Variação de {valor} °C",
    "temperatura_alta": "TEMPERATURA ALTA! Média em {valor} °C",
}


def ao_conectar(cliente, userdata, flags, codigo, propriedades):
    # Ao conectar, assina o tópico de alertas
    print("Conectado ao broker. Aguardando alertas em", TOPICO_ALERTAS)
    cliente.subscribe(TOPICO_ALERTAS)


def ao_receber(cliente, userdata, mensagem):
    # Chamada toda vez que chega um alerta
    try:
        alerta = json.loads(mensagem.payload.decode())
        hora = time.strftime("%H:%M:%S", time.localtime(alerta["timestamp"]))
        texto = MENSAGENS.get(alerta["tipo"], "Alerta desconhecido: {valor}")
        print("\n" + "!" * 50)
        print(f"[{hora}] {texto.format(valor=alerta['valor'])}")
        print("!" * 50)
    except (json.JSONDecodeError, KeyError):
        print("Mensagem inválida ignorada.")


cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="alarms_service")
cliente.on_connect = ao_conectar
cliente.on_message = ao_receber

try:
    cliente.connect(BROKER, PORTA)
except ConnectionRefusedError:
    print("Não consegui conectar. O Mosquitto está rodando?")
    sys.exit(1)

try:
    cliente.loop_forever()   # fica escutando até apertar Ctrl+C
except KeyboardInterrupt:
    print("\nAlarms encerrado.")
    cliente.disconnect()