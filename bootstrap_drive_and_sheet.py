#!/usr/bin/env python3
import os, json, time
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import gspread

def load_sa_creds():
    sa_json = os.environ.get("GCP_SA_KEY")
    if not sa_json:
        raise RuntimeError("GCP_SA_KEY env var (service account JSON) is required")
    data = json.loads(sa_json)
    scopes = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    creds = Credentials.from_service_account_info(data, scopes=scopes)
    return creds, data.get("client_email")

def ensure_folder(drive, folder_id=None, name="County Delinquent Tax Audit", parent_id=None):
    if folder_id:
        try:
            drive.files().get(fileId=folder_id, fields="id,name").execute()
            return folder_id
        except Exception as e:
            raise RuntimeError(f"Provided DRIVE_FOLDER_ID not accessible: {e}")
    body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        body["parents"] = [parent_id]
    resp = drive.files().create(body=body, fields="id").execute()
    return resp["id"]

def create_subfolder(drive, parent_id, name):
    body = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
    return drive.files().create(body=body, fields="id").execute()["id"]

def create_sheet(sheets_client, drive, folder_id, title):
    sh = sheets_client.create(title)
    drive.files().update(fileId=sh.id, addParents=folder_id, removeParents=[], fields="id, parents").execute()
    ws = sh.get_worksheet(0)
    ws.update_title("Master_Audit")
    ws.append_row(["County","State","Status","Primary Evidence URL(s)","Data Format","Requires Login? (Y/N)","Notes","Last Checked (ISO)","Scrape Queue (Next URL or Action)"])
    sh.add_worksheet(title="OnDemand_Queue", rows=100, cols=11)
    q = sh.worksheet("OnDemand_Queue")
    q.update("A1:K1", [["Request ID","Requested At (ISO)","County","State","Status (PENDING|FOUND|NO_LIST|PORTAL_ONLY|NEWSPAPER_ONLY|ERROR)","Evidence URL(s)","Data Format (CSV/XLSX/PDF/HTML Portal)","Requires Login? (Y/N)","Notes","Downloaded File Path (if any)","Last Checked (ISO)"]])
    return sh

def main():
    creds, sa_email = load_sa_creds()
    drive = build("drive", "v3", credentials=creds)
    sheets_client = gspread.authorize(creds)

    folder_id = os.environ.get("DRIVE_FOLDER_ID")
    folder_name = os.environ.get("FOLDER_NAME", "County Delinquent Tax Audit")
    sheet_title = os.environ.get("SHEET_TITLE", "County Tax Master Audit")
    share_email = os.environ.get("SHARE_EMAIL", os.environ.get("DEFAULT_SHARE_EMAIL","acquisitions.cclg@gmail.com"))

    folder_id = ensure_folder(drive, folder_id=folder_id, name=folder_name, parent_id=None)
    downloads_id = create_subfolder(drive, folder_id, "downloads")
    scripts_id = create_subfolder(drive, folder_id, "scripts")
    sheet = create_sheet(sheets_client, drive, folder_id, sheet_title)

    if share_email:
        drive.permissions().create(
            fileId=sheet.id,
            body={"type":"user","role":"writer","emailAddress": share_email},
            fields="id",
            sendNotificationEmail=True
        ).execute()

    print(f"FOLDER_ID={folder_id}")
    print(f"DOWNLOADS_FOLDER_ID={downloads_id}")
    print(f"SCRIPTS_FOLDER_ID={scripts_id}")
    print(f"SHEET_ID={sheet.id}")
    print(f"SHEET_URL={sheet.url}")
    print(f"SERVICE_ACCOUNT_EMAIL={sa_email}")

if __name__ == "__main__":
    main()
