#!/usr/bin/env python3
import os, io, re, time, json, requests
import pandas as pd
from urllib.parse import urljoin
from datetime import datetime, timezone
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import gspread
from bs4 import BeautifulSoup
from pdf_utils import pdf_to_csv

USER_AGENT = "Mozilla/5.0 (compatible; CountyAuditBot/0.3; +https://example.com/bot)"

def auth_clients():
    sa_json = os.environ["GCP_SA_KEY"]
    data = json.loads(sa_json)
    scopes = ["https://www.googleapis.com/auth/drive","https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(data, scopes=scopes)
    drive = build("drive", "v3", credentials=creds)
    sheets = gspread.authorize(creds)
    return drive, sheets

def get_ws(sheets, sheet_id, name):
    sh = sheets.open_by_key(sheet_id)
    try:
        return sh.worksheet(name)
    except:
        sh.add_worksheet(title=name, rows=100, cols=20)
        return sh.worksheet(name)

def list_folder(drive, folder_id):
    resp = drive.files().list(q=f"'{folder_id}' in parents and trashed=false", fields="files(id,name,mimeType)").execute()
    return resp.get("files", [])

def ensure_path_folders(drive, root_folder_id, parts):
    parent = root_folder_id
    for p in parts:
        found = None
        for f in list_folder(drive, parent):
            if f["name"] == p and f["mimeType"] == "application/vnd.google-apps.folder":
                found = f["id"]; break
        if not found:
            meta = {"name": p, "mimeType": "application/vnd.google-apps.folder", "parents": [parent]}
            found = drive.files().create(body=meta, fields="id").execute()["id"]
        parent = found
    return parent

def upload_file(drive, folder_id, filename, mimetype=None):
    media = MediaFileUpload(filename, mimetype=mimetype, resumable=False)
    meta = {"name": os.path.basename(filename), "parents": [folder_id]}
    return drive.files().create(body=meta, media_body=media, fields="id, webViewLink, webContentLink").execute()

def discover_links(url):
    out = []
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
    except Exception:
        return out
    ct = r.headers.get("Content-Type","").lower()
    if "pdf" in ct or url.lower().endswith(".pdf"):
        out.append(("FILE", url))
        return out
    soup = BeautifulSoup(r.text, "lxml")
    for a in soup.select("a[href]"):
        href = a["href"]
        full = urljoin(url, href)
        label = a.get_text(" ", strip=True).lower()
        if any(k in label for k in ["delinquent", "tax sale", "tax list", "taxes", "tax"]):
            out.append(("PAGE", full))
        if any(full.lower().endswith(ext) for ext in [".pdf", ".csv", ".xlsx", ".xls"]):
            out.append(("FILE", full))
    return out

def infer_status(links):
    requires_login = "N"
    evidence = [u for _,u in links]
    fmts = set()
    for k,u in links:
        if k=="FILE":
            if u.lower().endswith(".csv"): fmts.add("CSV")
            if u.lower().endswith(".xlsx") or u.lower().endswith(".xls"): fmts.add("XLSX")
            if u.lower().endswith(".pdf"): fmts.add("PDF")
    flat = " ".join(evidence).lower()
    status = None
    if any(p in flat for p in ["govease","zeusauction","civicsource","realauction"]):
        status = "PORTAL_ONLY"; requires_login = "Y"
    if any(p in flat for p in ["ledger","herald","newspaper"]):
        status = "NEWSPAPER_ONLY"
    if not status and fmts:
        status = "FOUND"
    if not status:
        status = "NO_LIST"
    return status, evidence, sorted(fmts), requires_login

def post_slack(message):
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url: return
    try:
        requests.post(url, json={"text": message}, timeout=10)
    except Exception:
        pass

def send_email(subject, body):
    # Optional SMTP: set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_TO, EMAIL_FROM
    host = os.environ.get("SMTP_HOST")
    if not host: return
    import smtplib
    from email.mime.text import MIMEText
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = os.environ.get("EMAIL_FROM","noreply@example.com")
    msg["To"] = os.environ.get("EMAIL_TO","")
    try:
        with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT","587"))) as s:
            s.starttls()
            user = os.environ.get("SMTP_USER"); pwd = os.environ.get("SMTP_PASS")
            if user and pwd: s.login(user, pwd)
            s.send_message(msg)
    except Exception:
        pass

def process_county(drive, root_folder_id, state, county, seeds):
    target = ensure_path_folders(drive, root_folder_id, ["downloads", state, county])
    candidates = []
    for s in seeds:
        candidates += discover_links(s)
        time.sleep(1)
    status, evidence, fmts, requires_login = infer_status(candidates)
    downloaded = []
    for kind, url in candidates:
        if kind != "FILE": continue
        try:
            r = requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
            r.raise_for_status()
            fname = url.split("/")[-1] or "download"
            local = f"/tmp/{fname}"
            with open(local, "wb") as f: f.write(r.content)
            meta = upload_file(drive, target, local, None)
            link = meta.get("webViewLink") or meta.get("webContentLink") or ""
            downloaded.append(link)
            if fname.lower().endswith(".pdf"):
                csv_path, _ = pdf_to_csv(local, "/tmp")
                if os.path.exists(csv_path):
                    up = upload_file(drive, target, csv_path, "text/csv")
                    downloaded.append(up.get("webViewLink") or up.get("webContentLink") or "")
        except Exception:
            continue
    return status, evidence, fmts, requires_login, downloaded

def main():
    drive, sheets = auth_clients()
    sheet_id = os.environ["SHEET_ID"]
    root_folder_id = os.environ["DRIVE_FOLDER_ID"]
    polite = float(os.environ.get("POLITE_DELAY_SECONDS","1"))
    allowed_states = [s.strip().upper() for s in os.environ.get("STATES","TN,GA,KY,FL,AL,ME,OH,MI,WI").split(",") if s.strip()]

    master = get_ws(sheets, sheet_id, "Master_Audit")
    queue = get_ws(sheets, sheet_id, "OnDemand_Queue")

    q_rows = queue.get_all_records()
    processed = []
    for idx, row in enumerate(q_rows, start=2):
        status = (row.get("Status (PENDING|FOUND|NO_LIST|PORTAL_ONLY|NEWSPAPER_ONLY|ERROR)") or "").strip().upper()
        county = (row.get("County") or "").strip()
        state = (row.get("State") or "").strip().upper()
        if status != "PENDING" or not county or not state:
            continue
        if state not in allowed_states:
            continue

        seeds = []
        lname = county.lower()
        if state == "TN":
            if lname == "shelby":
                seeds = ["https://www.shelbycountytrustee.com/259/Delinquent-Realty-Lawsuit-List",
                         "https://shelbycountytn.gov/330/Tax-Sale-Information"]
            elif lname == "davidson":
                seeds = ["https://chanceryclerkandmaster.nashville.gov/fees/delinquent-tax-sales/"]
        if not seeds:
            # placeholder generic; recommend replacing with a search API
            seeds = [f"https://www.{county.lower()}county.{state.lower()}.gov",
                     f"https://www.google.com/search?q={county}+County+{state}+delinquent+tax"]

        new_status, evidence, fmts, requires_login, downloaded = process_county(drive, root_folder_id, state, county, seeds)

        # Update row
        queue.update_acell(f"E{idx}", new_status)
        queue.update_acell(f"F{idx}", " ".join(evidence))
        queue.update_acell(f"G{idx}", ", ".join(fmts))
        queue.update_acell(f"H{idx}", requires_login)
        queue.update_acell(f"J{idx}", " | ".join([d for d in downloaded if d]))
        queue.update_acell(f"K{idx}", datetime.now(timezone.utc).isoformat(timespec="seconds"))

        processed.append((state, county, new_status))
        time.sleep(polite)

    # Slack/email summary
    if processed:
        lines = [f"{s} - {c}: {st}" for s,c,st in processed]
        summary = "*Weekly County Scan Results:*\n" + "\n".join(lines)
    else:
        summary = "Weekly scan finished: no PENDING rows found."

    post_slack(summary)
    send_email("Weekly County Scan Results", summary)

if __name__ == "__main__":
    main()
