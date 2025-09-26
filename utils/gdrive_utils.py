import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Se a modificação dessas APIs for feita, as credenciais de autenticação
# devem ser deletadas e criadas novamente.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/calendar']

def list_finance_data(spreadsheet_id, range_name='Sheet1!A2:E'):
    """
    Retorna os dados da planilha.
    """
    creds = get_google_creds()
    service = build('sheets', 'v4', credentials=creds)

    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=range_name).execute()
        rows = result.get('values', [])
        return rows
    except HttpError as error:
        print(f"Ocorreu um erro ao listar os dados: {error}")
        return []

def get_google_sheets_service():
    """Mostra como usar o Google Sheets API
    A função pega o token e cria uma sessão autorizada
    """
    creds = None
    # O arquivo token.json armazena o token de acesso e
    # as credenciais de refresh, e é criado automaticamente
    # quando a autenticação é concluída pela primeira vez.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # Se não há credenciais válidas, permite que o usuário faça o login.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                os.getenv("GOOGLE_CREDENTIALS_JSON"), SCOPES)
            creds = flow.run_local_server(port=0)
        # Salva as credenciais para as próximas execuções.
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('sheets', 'v4', credentials=creds)

def get_google_calendar_service():
    """Mostra como usar o Google Calendar API
    A função pega o token e cria uma sessão autorizada
    """
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                os.getenv("GOOGLE_CREDENTIALS_JSON"), SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('calendar', 'v3', credentials=creds)

def add_finance_entry(spreadsheet_id, values):
    """Adiciona uma nova linha com os dados financeiros na planilha"""
    service = get_google_sheets_service()
    body = {
        'values': values
    }
    result = service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id, 
        range='A1', 
        valueInputOption='RAW', 
        body=body
    ).execute()
    return result

def add_calendar_event(calendar_id, summary, description, start_time, end_time):
    """Cria um novo evento no Google Calendar"""
    service = get_google_calendar_service()
    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time,
            'timeZone': 'America/Sao_Paulo', # Ajuste para seu fuso horário
        },
        'end': {
            'dateTime': end_time,
            'timeZone': 'America/Sao_Paulo',
        },
    }
    result = service.events().insert(calendarId=calendar_id, body=event).execute()
    return result