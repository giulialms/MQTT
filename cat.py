# cat.py - Serviço CAT (Compute Average Temperature).
# Escuta as temperaturas dos sensores, calcula a média dos últimos 120 s
# e publica alertas quando algo anormal acontece.

import argparse          # opções da linha de comando
import json              # ler e montar mensagens JSON
import sys               # encerrar o programa em caso de erro
import threading         # Lock, para evitar conflito entre duas partes do programa
import time              # hora atual e espera

import paho.mqtt.client as mqtt

BROKER = "localhost"
PORTA = 1883
TOPICO_LEITURA = "caldeira/temperatura"   # de onde vêm as temperaturas
TOPICO_ALERTAS = "caldeira/alertas"       # para onde vão os alertas

LIMITE_VARIACAO = 5      # alerta se as duas últimas médias diferirem mais que 5 graus
LIMITE_ALTA = 200        # alerta se a média passar de 200 graus

parser = argparse.ArgumentParser(description="Serviço CAT")
parser.add_argument("--janela", type=float, default=120,
                    help="quantos segundos de leituras entram na média (padrão 120)")
parser.add_argument("--calculo", type=float, default=60,
                    help="de quantos em quantos segundos calcula a média (padrão 60)")
args = parser.parse_args()

leituras = []            # lista de (hora, temperatura) recebidas
media_anterior = None    # guarda a última média para comparar com a nova
lock = threading.Lock()  # protege a lista, pois duas partes do programa mexem nela


def ao_conectar(cliente, userdata, flags, codigo, propriedades):
    # Chamada quando conecta ao broker: assina o tópico das temperaturas
    print("Conectado ao broker. Assinando", TOPICO_LEITURA)
    cliente.subscribe(TOPICO_LEITURA)


def ao_receber(cliente, userdata, mensagem):
    # Chamada toda vez que chega uma temperatura nova
    try:
        dados = json.loads(mensagem.payload.decode())   # texto -> dicionário
        with lock:
            leituras.append((time.time(), dados["temperatura"]))
        print(f"Recebido de {dados['sensor_id']}: {dados['temperatura']} °C")
    except (json.JSONDecodeError, KeyError):
        print("Mensagem inválida ignorada.")


def publicar_alerta(cliente, tipo, valor):
    # Monta e publica um alerta no tópico de alertas
    alerta = {"tipo": tipo, "valor": round(valor, 2), "timestamp": time.time()}
    cliente.publish(TOPICO_ALERTAS, json.dumps(alerta))
    print(f"-> ALERTA publicado: {tipo} ({alerta['valor']})")


def calcular_media(cliente):
    global media_anterior
    agora = time.time()

    with lock:
        # Mantém só as leituras dentro da janela (ex.: últimos 120 s)
        leituras[:] = [(t, v) for (t, v) in leituras if agora - t <= args.janela]
        valores = [v for (_, v) in leituras]

    if not valores:
        print("Sem leituras na janela.")
        return

    media = sum(valores) / len(valores)
    print(f"Média dos últimos {args.janela:.0f}s: {media:.2f} °C ({len(valores)} leituras)")

    # Alerta 1: subida (ou queda) repentina entre as duas últimas médias
    if media_anterior is not None and abs(media - media_anterior) > LIMITE_VARIACAO:
        publicar_alerta(cliente, "aumento_repentino", abs(media - media_anterior))

    # Alerta 2: temperatura alta
    if media > LIMITE_ALTA:
        publicar_alerta(cliente, "temperatura_alta", media)

    media_anterior = media   # guarda para a próxima comparação


cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="cat_service")
cliente.on_connect = ao_conectar
cliente.on_message = ao_receber

try:
    cliente.connect(BROKER, PORTA)
except ConnectionRefusedError:
    print("Não consegui conectar. O Mosquitto está rodando?")
    sys.exit(1)

cliente.loop_start()   # recebe mensagens em segundo plano

print(f"CAT iniciado. Calculando a média a cada {args.calculo:.0f}s. Ctrl+C para parar.")
try:
    while True:
        time.sleep(args.calculo)
        calcular_media(cliente)
except KeyboardInterrupt:
    print("\nCAT encerrado.")
finally:
    cliente.loop_stop()
    cliente.disconnect()