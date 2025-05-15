from flask import Flask, request
import requests
import os
from datetime import datetime

app = Flask(__name__)

# Configurações da API do WhatsApp
WHATSAPP_API_URL = "https://graph.facebook.com/v17.0/579112278612275/messages"
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

# Estrutura para armazenar dados dos funcionários
employees = {}  # {nome: {"valor_semanal": float, "pix": str}}
payments = {}   # {nome: [float]}

def cadastrar_funcionario(nome, valor_semanal, pix=None):
    employees[nome] = {"valor_semanal": valor_semanal, "pix": pix}
    payments[nome] = []
    pix_text = f"\n🔑 Chave PIX: {pix}" if pix else ""
    return f"Funcionário {nome} cadastrado com R${valor_semanal:.2f} semanal.{pix_text}"

def excluir_funcionario(nome):
    if nome not in employees:
        return f"Funcionário {nome} não encontrado."
    del employees[nome]
    if nome in payments:
        del payments[nome]
    return f"Funcionário {nome} excluído com sucesso."

def registrar_pagamento(nome, valor):
    if nome not in employees:
        return f"Funcionário {nome} não encontrado."
    payments[nome].append(valor)
    return f"Pagamento de R${valor:.2f} registrado para {nome}."

def gerar_relatorio():
    if not employees:
        return "Nenhum funcionário cadastrado."
    
    relatorio = "📊 *Relatório Semanal*\n"
    total_pendente = 0
    
    for nome, dados in employees.items():
        valor_semanal = dados["valor_semanal"]
        pix = dados["pix"]
        pago = sum(payments.get(nome, []))
        restante = valor_semanal - pago
        total_pendente += restante
        pix_text = f"\n  🔑 Chave PIX: {pix}" if pix else ""
        relatorio += f"👤 {nome}:\n  Valor semanal: R${valor_semanal:.2f}\n  Pago: R${pago:.2f}\n  Restante: R${restante:.2f}{pix_text}\n"
    
    relatorio += f"💰 Total pendente: R${total_pendente:.2f}"
    return relatorio

def reset_payments():
    for nome in payments:
        payments[nome] = []

def send_whatsapp_message(to, message):
    if not WHATSAPP_TOKEN:
        print("Erro: WHATSAPP_TOKEN não configurado")
        return False
    if not to.startswith('+'):
        to = '+' + to
    headers = {
        'Authorization': f'Bearer {WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    print(f"Enviando mensagem para {to}: {data}")
    try:
        response = requests.post(WHATSAPP_API_URL, json=data, headers=headers)
        print(f"Resposta da API: {response.status_code} - {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Erro na requisição à API: {str(e)}")
        return False

@app.route('/whatsapp', methods=['GET', 'POST'])
def whatsapp():
    if request.method == 'GET':
        verify_token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        print(f"GET /whatsapp - Verify Token: {verify_token}, Challenge: {challenge}")
        if not VERIFY_TOKEN:
            print("Erro: VERIFY_TOKEN não configurado")
            return "Verification failed", 403
        if verify_token == VERIFY_TOKEN:
            return challenge, 200
        print("GET /whatsapp - Verification failed")
        return "Verification failed", 403
    
    if request.method == 'POST':
        data = request.get_json()
        print(f"POST /whatsapp - Payload recebido: {data}")
        
        if not data:
            print("POST /whatsapp - Payload vazio")
            return '', 200
        
        try:
            entries = data.get('entry', [])
            if not entries:
                print("POST /whatsapp - Sem 'entry' no payload")
                return '', 200
            
            for entry in entries:
                changes = entry.get('changes', [])
                if not changes:
                    print("POST /whatsapp - Sem 'changes' no entry")
                    continue
                
                for change in changes:
                    value = change.get('value', {})
                    messages = value.get('messages', [])
                    if not messages:
                        print("POST /whatsapp - Sem 'messages' no value")
                        continue
                    
                    for message in messages:
                        from_number = message.get('from')
                        msg_body = message.get('text', {}).get('body', '').strip().lower()
                        if not from_number or not msg_body:
                            print("POST /whatsapp - Mensagem sem 'from' ou 'body'")
                            continue
                        
                        print(f"Mensagem recebida de {from_number}: {msg_body}")
                        
                        response_msg = ""
                        
                        if msg_body.startswith('!cadastrar'):
                            try:
                                parts = msg_body.split(maxsplit=3)
                                if len(parts) < 3:
                                    raise ValueError("Formato inválido")
                                _, nome, valor = parts[:3]
                                pix = parts[3] if len(parts) == 4 else None
                                response_msg = cadastrar_funcionario(nome, float(valor), pix)
                            except Exception as e:
                                print(f"Erro ao processar !cadastrar: {str(e)}")
                                response_msg = "Use: !cadastrar <nome> <valor_semanal> [<chave_pix>] (ex.: !cadastrar Manoel Junior 750 12345678900)"
                        
                        elif msg_body.startswith('!excluir'):
                            try:
                                parts = msg_body.split(maxsplit=2)
                                if len(parts) != 2:
                                    raise ValueError("Formato inválido")
                                _, nome = parts
                                response_msg = excluir_funcionario(nome)
                            except Exception as e:
                                print(f"Erro ao processar !excluir: {str(e)}")
                                response_msg = "Use: !excluir <nome> (ex.: !excluir Manoel Junior)"
                        
                        elif msg_body.startswith('!pagar'):
                            try:
                                parts = msg_body.split(maxsplit=2)
                                if len(parts) != 3:
                                    raise ValueError("Formato inválido")
                                _, nome, valor = parts
                                response_msg = registrar_pagamento(nome, float(valor))
                            except Exception as e:
                                print(f"Erro ao processar !pagar: {str(e)}")
                                response_msg = "Use: !pagar <nome> <valor> (ex.: !pagar Manoel Junior 200)"
                        
                        elif msg_body == '!relatorio':
                            response_msg = gerar_relatorio()
                        
                        elif msg_body == '!resetar':
                            reset_payments()
                            response_msg = "Pagamentos resetados."
                        
                        else:
                            response_msg = "Comandos:\n!cadastrar <nome> <valor_semanal> [<chave_pix>]\n!excluir <nome>\n!pagar <nome> <valor>\n!relatorio\n!resetar"
                        
                        success = send_whatsapp_message(from_number, response_msg)
                        print(f"Envio de resposta para {from_number}: {response_msg} - Sucesso: {success}")
            
            return '', 200
        
        except Exception as e:
            print(f"Erro ao processar mensagem: {str(e)}")
            return '', 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
