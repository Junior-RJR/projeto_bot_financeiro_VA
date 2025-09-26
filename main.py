import logging
import os.path
import datetime
import re

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, 
    ContextTypes, 
    CommandHandler,
    MessageHandler, 
    filters
)

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from utils.gdrive_utils import add_finance_entry
from utils.gcalendar_utils import create_calendar_event, list_calendar_events, delete_calendar_event, update_calendar_event 

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/calendar"]

# The ID and range of a sample spreadsheet.
SAMPLE_SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# --- Google Authentication Setup ---
def get_google_creds():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(os.getenv("GOOGLE_CREDENTIALS_JSON"), SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

# --- Telegram Bot Functions ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Olá {user_name}! Sou seu bot financeiro e de agenda. Digite /ajuda para saber o que posso fazer."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="""
        *Comandos Financeiros:*
        - Para registrar um gasto, digite algo como: `gasto 15 reais coxinha`
        - Para registrar uma receita, digite: `ganhei 100 reais de bico`

        *Comandos de Agenda:*
        - Para agendar um evento, digite: `agendar reunião amanhã às 10h`
        - Para listar eventos, digite: `eventos de hoje` ou `eventos de amanhã`
        - Para editar um evento, digite: `mudar nome do evento reunião para time meeting`
        - Para excluir um evento, digite: `excluir evento reunião de amanhã`

        *Outros Comandos:*
        - /start: Inicia a conversa com o bot.
        - /ajuda: Mostra este menu de ajuda.
        """,
        parse_mode="Markdown"
    )

# Novo handler para processar a mensagem do usuário
async def processar_mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text.lower()
    
    # Lógica para registrar gastos ou receitas
    if "gasto" in user_message or "ganhei" in user_message:
        try:
            # Padrão para encontrar valor e descrição
            match_gasto = re.search(r'(gasto|ganhei)\s(\d+)\sreais\s(.+)', user_message)
            if match_gasto:
                valor = float(match_gasto.group(2))
                descricao_completa = match_gasto.group(3)
                tipo = "Despesa" if "gasto" in user_message else "Receita"
                
                # Assume que a primeira palavra da descrição é a categoria
                categoria = descricao_completa.split()[0].capitalize()
                descricao = ' '.join(descricao_completa.split()[1:])
                
                # Adiciona a entrada na planilha
                values = [[
                    datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    descricao,
                    valor,
                    tipo,
                    categoria
                ]]
                add_finance_entry(SAMPLE_SPREADSHEET_ID, values)
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"{tipo} de R${valor:.2f} com '{descricao}' na categoria '{categoria}' registrado com sucesso!"
                )
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Não entendi o formato. Tente 'gasto 15 reais coxinha'."
                )
        except Exception as e:
            logging.error(f"Erro ao processar mensagem de gasto: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Ocorreu um erro ao registrar seu gasto. Por favor, tente novamente."
            )
    
    # Lógica para agendar eventos
    elif "agendar" in user_message:
        # Padrão flexível para capturar o evento e a hora (com ou sem 'h', com ou sem 'amanhã')
        match_agendar = re.search(r'agendar\s(.+?)\s(?:(hoje|amanh[aã])\s)?(?:às|as)\s(\d{1,2})h?', user_message)

        if match_agendar:
            title = match_agendar.group(1).strip()
            day_str = match_agendar.group(2)
            hour_str = match_agendar.group(3)

            now = datetime.datetime.now()
            event_date = now

            if day_str and 'amanhã' in day_str:
                event_date += datetime.timedelta(days=1)

            try:
                hour = int(hour_str)
                # Lógica para converter o horário para o formato correto (12h/24h)
                event_hour = hour
                if hour >= 1 and hour <= 11 and (now.hour >= 12 or hour < now.hour):
                    event_hour += 12
                
                event_datetime = event_date.replace(hour=event_hour, minute=0, second=0, microsecond=0)

                create_calendar_event(
                    summary=title,
                    start_time=event_datetime.isoformat(),
                    duration="1h"
                )
                
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Evento '{title}' agendado para {event_datetime.strftime('%d/%m/%Y às %Hh')}."
                )

            except ValueError:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Não consegui entender a hora. Tente um formato como '14h'."
                )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Não entendi o formato. Tente `agendar nome do evento amanhã às 14h`."
            )
    
   # Lógica para listar eventos
    elif "eventos" in user_message:
        target_date = datetime.datetime.now().date()
        date_text = "hoje"
        
        if "amanha" in user_message:
            target_date += datetime.timedelta(days=1)
            date_text = "amanhã"
        
        # Converte a data para um formato que a API do Google entenda
        time_min = datetime.datetime.combine(target_date, datetime.time.min).isoformat() + 'Z'
        time_max = datetime.datetime.combine(target_date, datetime.time.max).isoformat() + 'Z'
        
        events = list_calendar_events(time_min=time_min, time_max=time_max)
        
        if not events:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Nenhum evento encontrado para {date_text}."
            )
            return

        response_text = f"Seus eventos para {date_text}:\n"
        for i, event in enumerate(events):
            # Formata a data e hora para ficar mais bonita
            start_time_obj = datetime.datetime.fromisoformat(event['start'].get('dateTime'))
            formatted_time = start_time_obj.strftime('%d/%m às %Hh:%M')
            response_text += f"*{i+1}. {event['summary']}* - {formatted_time}\n"
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=response_text,
            parse_mode="Markdown"
        )

    # Lógica para excluir eventos
    elif "excluir evento" in user_message:
        match_delete = re.search(r'excluir evento (.+)', user_message)
        if match_delete:
            event_title = match_delete.group(1).strip()
            
            events = list_calendar_events(query=event_title)
            
            if not events:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Não encontrei nenhum evento com o nome '{event_title}' para excluir."
                )
                return
            
            event_id_to_delete = events[0]['id']
            
            if delete_calendar_event(event_id_to_delete):
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Evento '{events[0]['summary']}' excluído com sucesso!"
                )
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Ocorreu um erro ao tentar excluir o evento."
                )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Não entendi qual evento excluir. Tente 'excluir evento reunião de amanhã'."
            )

    # Abaixo da lógica de "excluir evento"
    
    # Lógica para editar eventos
    elif "mudar nome do evento" in user_message:
        # Padrão para extrair o nome antigo e o novo nome do evento
        match_edit = re.search(r'mudar nome do evento (.+) para (.+)', user_message)
        if match_edit:
            old_title = match_edit.group(1).strip()
            new_title = match_edit.group(2).strip()
            
            # Encontra o evento pelo título antigo
            events = list_calendar_events(query=old_title)
            
            if not events:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Não encontrei nenhum evento com o nome '{old_title}'."
                )
                return
            
            # Pega o primeiro evento encontrado e seu ID
            event_to_update = events[0]
            event_id = event_to_update['id']
            
            # Cria o corpo da requisição com o novo título
            updated_body = event_to_update
            updated_body['summary'] = new_title
            
            # Tenta atualizar o evento
            updated_event = update_calendar_event(event_id, updated_body)
            
            if updated_event:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Nome do evento alterado de '{old_title}' para '{new_title}' com sucesso!"
                )
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Ocorreu um erro ao tentar editar o evento."
                )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Não entendi o formato para editar. Tente `mudar nome do evento reunião para time meeting`."
            )

    # Abaixo da lógica de "excluir evento"

    # Lógica para mostrar totais financeiros
    elif "total do mes" in user_message or "gastos do mes" in user_message:
        # Pega os dados do Google Sheets
        rows = list_finance_data(SAMPLE_SPREADSHEET_ID)

        if not rows:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Não consegui encontrar dados na sua planilha."
            )
            return

        total_despesas = 0
        total_receitas = 0

        # Filtra os dados pelo mês atual
        current_month = datetime.datetime.now().month

        for row in rows:
            try:
                # O formato da data na planilha é 26/09/2025
                entry_date = datetime.datetime.strptime(row[0], '%d/%m/%Y %H:%M:%S').month
                if entry_date == current_month:
                    valor = float(row[2])
                    tipo = row[3]
                    if tipo == "Despesa":
                        total_despesas += valor
                    elif tipo == "Receita":
                        total_receitas += valor
            except (ValueError, IndexError):
                continue

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Resumo do Mês:"
                    "Total de Despesas: R${total_despesas:.2f}"
                    "Total de Receitas: R${total_receitas:.2f}"
                    "Saldo: R${total_receitas - total_despesas:.2f}"
                    ,
                    parse_mode="Markdown"
                    )


    
            
# --- Main Bot Logic ---
def main():
    try:
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO
        )

        # Autentica com o Google
        get_google_creds()

        # Configura o bot do Telegram
        application = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()

        # Handlers
        start_handler = CommandHandler('start', start)
        help_handler = CommandHandler('ajuda', help_command)
        message_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), processar_mensagem)

        application.add_handler(start_handler)
        application.add_handler(help_handler)
        application.add_handler(message_handler)

        application.run_polling()
        
    except Exception as e:
        logging.error(f"Erro na execução principal: {e}")

if __name__ == '__main__':
    main()