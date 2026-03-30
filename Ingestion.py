import os
import requests
import time

CLIENT_ID = os.getenv("ZOHO_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET", "")
REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN", "")
BASE_URL = "https://mail.zoho.in/api/accounts"

def get_access_token():
    """Refreshes the short-lived access token using the refresh token."""
    url = "https://accounts.zoho.in/oauth/v2/token"
    data = {
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token"
    }
    response = requests.post(url, data=data)
    return response.json().get("access_token")

def fetch_zoho_emails():
    """Fetches the last 10 emails (Read OR Unread) from Zoho Mail."""
    token = get_access_token()
    if not token:
        print("❌ Could not get Access Token.")
        return []

    headers = {"Authorization": f"Zoho-oauthtoken {token}"}

    # 1. Get Account ID
    acc_resp = requests.get(BASE_URL, headers=headers)

    if acc_resp.status_code != 200:
        print(f"❌ Error fetching account info: {acc_resp.text}")
        return []

    account_info = acc_resp.json().get('data', [])
    account_id = account_info[0]['accountId']

    # 2. Fetch Messages (Removed status:unread to see ALL emails)
    # Adding 'status=all' ensures we see everything in the folder
    search_url = f"{BASE_URL}/{account_id}/messages/view?status=all"

    msg_resp = requests.get(search_url, headers=headers)

    emails = []
    if msg_resp.status_code == 200:
        messages = msg_resp.json().get('data', [])
        for msg in messages[:10]:
            # Status '0' is Unread, '1' is Read in Zoho
            status_label = "UNREAD" if msg.get('status') == "0" else "READ"

            emails.append({
                "id": msg['messageId'],
                "sender": msg['sender'],
                "subject": msg['subject'],
                "status": status_label,
                "body": msg['summary']
            })
    else:
        print(f"❌ Error fetching messages: {msg_resp.text}")

    return emails

# --- Run the Test ---
if __name__ == "__main__":
    print("Testing connection to Zoho India (All Emails)...")
    results = fetch_zoho_emails()

    if results:
        print(f"✅ Successfully found {len(results)} emails.")
        for e in results:
            print(f"[{e['status']}] {e['subject']} | From: {e['sender']}")
    else:
        print("❓ No emails found. Try sending a test email to your Zoho account.")