import os
import requests

# 1. GENERATE A FRESH CODE IN ZOHO CONSOLE BEFORE RUNNING
GRANT_CODE = "PASTE_YOUR_NEW_1000_CODE_HERE"

# 2. Your credentials (Keep as is)
CLIENT_ID = os.getenv("ZOHO_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET", "")

# 3. CHANGED TO .IN (Crucial for Indian Accounts)
url = "https://accounts.zoho.in/oauth/v2/token"

data = {
    "code": GRANT_CODE,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "grant_type": "authorization_code"
}

print(f"Connecting to Zoho INDIA servers ({url})...")

try:
    response = requests.post(url, data=data)
    json_data = response.json()

    if response.status_code == 200 and "access_token" in json_data:
        print("✅ SUCCESS! Access and Refresh tokens received.")
        print("-" * 30)
        print(f"REFRESH_TOKEN: {json_data.get('refresh_token')}")
        print(f"ACCESS_TOKEN: {json_data.get('access_token')}")
        print("-" * 30)
        print("COPY THE REFRESH_TOKEN. You will use it in your ingestion script.")
    else:
        print(f"❌ ERROR: {json_data.get('error', 'Unknown Error')}")
        print(f"Details: {json_data}")

except Exception as e:
    print(f"❌ Failed to connect: {e}")


    