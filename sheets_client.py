import os, json
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def get_client():
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise RuntimeError("Faltou a env var GOOGLE_SERVICE_ACCOUNT_JSON.")
    info = json.loads(raw)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)

def open_sheet_by_id(client, sheet_id: str):
    return client.open_by_key(sheet_id)

def get_or_create_ws(ss, title: str, rows=2000, cols=80):
    try:
        return ss.worksheet(title)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=title, rows=rows, cols=cols)

def clear_and_write_df(ws, df):
    ws.clear()
    if df is None or df.empty:
        ws.update("A1", [["SEM DADOS"]])
        return

    df2 = df.copy().fillna("")
    df2.columns = [str(c) for c in df2.columns]
    values = [df2.columns.tolist()] + df2.astype(str).values.tolist()

    ws.resize(rows=max(len(values), 10), cols=max(len(values[0]), 5))
    ws.update("A1", values)
    ws.freeze(rows=1)
    ws.set_basic_filter()
