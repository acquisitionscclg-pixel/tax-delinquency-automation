import gspread
from google.oauth2.service_account import Credentials

# Authenticate
creds = Credentials.from_service_account_file('service_account.json', scopes=[
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
])
gc = gspread.authorize(creds)

# States to set up
states = ["GA", "KY", "FL", "AL", "ME", "OH", "MI", "WI"]

# Create Google Sheets for each state
for state in states:
    sh = gc.create(f"{state}_Tax_Delinquency_Tracker")
    sh.share('acquisitions.cclg@gmail.com', perm_type='user', role='writer')
    worksheet = sh.sheet1
    worksheet.update('A1:E1', [["County", "State", "Has List?", "Download Link", "Last Checked"]])
print("Bootstrap completed successfully")
