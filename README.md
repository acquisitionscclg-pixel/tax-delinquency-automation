# County Delinquent Tax Automation (Cloud Kit, Enhanced)

**No local installs required.** This runs fully in the cloud via GitHub Actions.

## Features
- One-click bootstrap to create a Google Sheet and Drive subfolders inside your owned folder
- Weekly county scan over states: TN, GA, KY, FL, AL, ME, OH, MI, WI
- Dynamic **OnDemand_Queue**: add any County/State with `Status=PENDING` and it will run
- **PDF → CSV** conversion with OCR for scanned PDFs (Tesseract)
- **Slack notifications** (via webhook) and **optional email summaries**

## Setup (once)
1. **Create Drive folder** you own (e.g. "County Delinquent Tax Audit") and share it with your service account email as **Editor**.
2. **Create a private GitHub repo** and upload these files.
3. **Add repo secrets** (Settings → Secrets and variables → Actions):
   - `GCP_SA_KEY` → paste the entire service account JSON
   - `DRIVE_FOLDER_ID` → the folder ID from your Drive folder URL
4. **Run the Bootstrap workflow** (Actions → Bootstrap → Run). Copy the printed `SHEET_ID` and add it as a secret:
   - `SHEET_ID` → your Google Sheet ID
5. (Optional) **Slack**: add `SLACK_WEBHOOK_URL` secret to get a summary after each run.
6. (Optional) **Email**: add SMTP secrets (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_FROM`, `EMAIL_TO`).

## Daily Use
- Open the Google Sheet → `OnDemand_Queue`
- Add a row with **County**, **State**, and set **Status** to `PENDING`
- The weekly job will process it (or run it on-demand via Actions)

## Notes
- Ownership transfer via API is often blocked. Files are created in your folder; you can **Make a copy** to own a specific file if needed.
- Improve accuracy by adding state/county seed URLs in `weekly_runner.py`.
