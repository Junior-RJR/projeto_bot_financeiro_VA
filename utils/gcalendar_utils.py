import os.path
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# A função get_google_creds precisa ser importada ou definida aqui.
# Como ela está no seu main.py, é melhor importá-la.
# Se preferir, pode copiar e colar a função get_google_creds() aqui.
# Vamos assumir que ela será importada.

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Se você não quiser mover a função get_google_creds do seu main.py
# para cá, você pode importá-la.
# from main import get_google_creds

# Ou, a melhor prática: copie a função para este arquivo
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

def update_calendar_event(event_id, new_body):
    """Atualiza um evento existente no Google Calendar."""
    creds = get_google_creds()
    service = build("calendar", "v3", credentials=creds)
    
    try:
        updated_event = service.events().update(
            calendarId='primary',
            eventId=event_id,
            body=new_body
        ).execute()
        return updated_event
    except HttpError as error:
        print(f"Ocorreu um erro ao atualizar o evento: {error}")
        return None
    
def create_calendar_event(summary, start_time, duration):
    """Cria um novo evento no Google Calendar"""
    creds = get_google_creds()
    service = build('calendar', 'v3', credentials=creds)

    event = {
        'summary': summary,
        'start': {
            'dateTime': start_time,
            'timeZone': 'America/Sao_Paulo',
        },
        'end': {
            'dateTime': (datetime.datetime.fromisoformat(start_time) + datetime.timedelta(hours=1)).isoformat(),
            'timeZone': 'America/Sao_Paulo',
        },
    }

    event = service.events().insert(calendarId='primary', body=event).execute()
    return event

def delete_calendar_event(event_id):
    """Exclui um evento do Google Calendar pelo ID"""
    creds = get_google_creds()
    service = build("calendar", "v3", credentials=creds)
    try:
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return True
    except HttpError as error:
        print(f"Ocorreu um erro ao excluir o evento: {error}")
        return False

def list_calendar_events(query=None, time_min=None, time_max=None):
    """Lista eventos do Google Calendar com base em uma consulta ou período de tempo"""
    creds = get_google_creds()
    service = build('calendar', 'v3', credentials=creds)

    # Adiciona a consulta (query) para encontrar eventos por nome
    events_result = service.events().list(
        calendarId='primary',
        q=query,
        timeMin=time_min,
        timeMax=time_max,
        maxResults=10,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    return events