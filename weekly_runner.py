import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import requests

# Authenticate
creds = Credentials.from_service_account_file('service_account.json', scopes=[
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
])
gc = gspread.authorize(creds)

# Example placeholder: Open one of the sheets
state = "GA"
sh = gc.open(f"{state}_Tax_Delinquency_Tracker")
worksheet = sh.sheet1
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# Placeholder: Simulate a county update
df.loc[0, "Has List?"] = "Checked"
worksheet.update([df.columns.values.tolist()] + df.values.tolist())
print("Weekly update completed successfully")
