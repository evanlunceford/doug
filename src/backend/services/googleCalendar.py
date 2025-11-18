from __future__ import annotations
import os, datetime as dt
from dateutil.tz import gettz
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

def _get_oauth_service():
    creds = None
    # token.json stores the user’s access/refresh tokens
    if os.path.exists("./token.json"):
        creds = Credentials.from_authorized_user_file("./token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("./credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)

def list_events_for_days(days: int, calendar_id: str = "primary", tz: str = "America/Phoenix"):

    if days < 0:
        raise ValueError("days must be >= 0")

    service = _get_oauth_service()

    tzinfo = gettz(tz)
    now_local = dt.datetime.now(tzinfo)
    end_local = now_local + dt.timedelta(days=days)

    time_min = now_local.isoformat()
    time_max = end_local.isoformat()

    events = []
    page_token = None
    while True:
        resp = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            pageToken=page_token,
            timeZone=tz,
            maxResults=2500,
        ).execute()
        events.extend(resp.get("items", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return events

if __name__ == "__main__":
    items = list_events_for_days(7)
    for e in items:
        start = e["start"].get("dateTime") or e["start"].get("date")
        end = e["end"].get("dateTime") or e["end"].get("date")
        print(f"{start} — {end} | {e.get('summary','(no title)')}")
