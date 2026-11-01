# alarms_gui.py - Serviço Alarms com interface gráfica (Tkinter).
# Escuta os alertas publicados pelo CAT e mostra cada um numa janela,
# com cores diferentes para cada tipo de alerta.

import json              # ler as mensagens JSON
import queue             # fila para passar mensagens do MQTT para a janela
import time              # converter a hora do alerta para texto legível
import tkinter as tk     # biblioteca de janelas (já vem com o Python)
from tkinter import ttk  # versão "moderna" dos botões e rótulos

import paho.mqtt.client as mqtt

BROKER = "localhost"
PORTA = 1883
TOPICO_ALERTAS = "caldeira/alertas"

# Para cada tipo de alerta: (título, detalhe, cor de fundo, cor do texto)
TIPOS = {
    "aumento_repentino": ("AUMENTO REPENTINO", "variação de {valor} °C", "#fff3cd", "#7a5200"),
    "temperatura_alta": ("TEMPERATURA ALTA", "média em {valor} °C", "#f8d7da", "#842029"),
}

# O MQTT roda em outra "linha de execução" (thread). O Tkinter só pode ser
# mexido pela linha principal. Por isso o MQTT coloca os eventos nesta fila
# e a janela vai buscando de lá.
fila = queue.Queue()


# ---------- Parte MQTT ----------

def ao_conectar(cliente, userdata, flags, codigo, propriedades):
    # Chamada quando a conexão com o broker é feita (ou falha)
    if codigo.is_failure:
        fila.put(("status", False))
        return
    cliente.subscribe(TOPICO_ALERTAS)    # assina de novo, também depois de reconectar
    fila.put(("status", True))


def ao_desconectar(cliente, userdata, flags, codigo, propriedades):
    # Chamada quando a conexão com o broker cai
    fila.put(("status", False))


def ao_receber(cliente, userdata, mensagem):
    # Chamada toda vez que chega um alerta
    try:
        alerta = json.loads(mensagem.payload.decode())
        if "tipo" in alerta and "valor" in alerta and "timestamp" in alerta:
            fila.put(("alerta", alerta))
    except json.JSONDecodeError:
        pass    # mensagem inválida: ignora


# ---------- Parte da janela ----------

class App:
    def __init__(self, root):
        self.root = root
        self.total = 0                       # quantidade de alertas recebidos
        root.title("Alarms - Monitoramento da Caldeira")
        root.geometry("700x440")

        # Barra do topo: status da conexão, contador e botão de limpar
        topo = ttk.Frame(root, padding=10)
        topo.pack(fill="x")
        self.lbl_status = tk.Label(topo, text="● Desconectado", fg="#b02a37",
                                   font=("Segoe UI", 10, "bold"))
        self.lbl_status.pack(side="left")
        ttk.Button(topo, text="Limpar", command=self.limpar).pack(side="right")
        self.lbl_total = ttk.Label(topo, text="Alertas: 0")
        self.lbl_total.pack(side="right", padx=10)

        # Lista de alertas, com barra de rolagem
        corpo = ttk.Frame(root, padding=(10, 0, 10, 10))
        corpo.pack(fill="both", expand=True)
        barra = ttk.Scrollbar(corpo)
        barra.pack(side="right", fill="y")
        self.lista = tk.Listbox(corpo, font=("Consolas", 11), activestyle="none",
                                yscrollcommand=barra.set)
        self.lista.pack(side="left", fill="both", expand=True)
        barra.config(command=self.lista.yview)

        self.processar_fila()                # começa a checar a fila

    def processar_fila(self):
        # Pega tudo o que o MQTT colocou na fila e mostra na janela
        while not fila.empty():
            tipo_evento, dado = fila.get()
            if tipo_evento == "status":
                self.mostrar_status(dado)
            else:
                self.mostrar_alerta(dado)
        self.root.after(200, self.processar_fila)   # repete daqui a 200 ms

    def mostrar_status(self, conectado):
        if conectado:
            self.lbl_status.config(text="● Conectado ao broker", fg="#146c43")
        else:
            self.lbl_status.config(text="● Desconectado (tentando reconectar...)", fg="#b02a37")

    def mostrar_alerta(self, alerta):
        hora = time.strftime("%H:%M:%S", time.localtime(alerta["timestamp"]))
        titulo, detalhe, fundo, letra = TIPOS.get(
            alerta["tipo"], ("ALERTA DESCONHECIDO", "valor {valor}", "#e2e3e5", "#41464b"))
        texto = f"[{hora}]  {titulo}  -  {detalhe.format(valor=alerta['valor'])}"

        self.lista.insert(0, texto)                        # o mais novo fica no topo
        self.lista.itemconfig(0, bg=fundo, fg=letra)       # cor conforme o tipo
        self.total += 1
        self.lbl_total.config(text=f"Alertas: {self.total}")
        self.root.bell()                                   # som de aviso do sistema

    def limpar(self):
        self.lista.delete(0, "end")
        self.total = 0
        self.lbl_total.config(text="Alertas: 0")


# ---------- Início do programa ----------

cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="alarms_gui")
cliente.on_connect = ao_conectar
cliente.on_disconnect = ao_desconectar
cliente.on_message = ao_receber

# connect_async não trava nem dá erro se o Mosquitto estiver desligado:
# o programa abre a janela e fica tentando conectar sozinho.
cliente.connect_async(BROKER, PORTA)
cliente.loop_start()

root = tk.Tk()
app = App(root)


def fechar():
    # Ao fechar a janela, encerra a conexão MQTT também
    cliente.loop_stop()
    cliente.disconnect()
    root.destroy()


root.protocol("WM_DELETE_WINDOW", fechar)
root.mainloop()