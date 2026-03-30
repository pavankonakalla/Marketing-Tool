"""
daily_vectorize.py
Run this file once a day to:
  1) Fetch today's emails from ALL Zoho Mail folders (inbox, spam, newsletters, promotions)
  2) Skip replies/forwards — only keep fresh received emails
  3) Convert them into vector embeddings (local model, no API key needed)
  4) Store vectors locally in a JSONL file
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from sentence_transformers import SentenceTransformer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def _extract_email(sender: str) -> str:
    match = re.search(r"<([^>]+)>", sender)
    if match:
        return match.group(1)
    if "@" in sender:
        return sender.strip()
    return sender


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CLIENT_ID = os.getenv("ZOHO_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET", "")
REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN", "")
ZOHO_REGION = os.getenv("ZOHO_REGION", "in")
BASE_URL = f"https://mail.zoho.{ZOHO_REGION}/api/accounts"
VECTOR_DIR = Path("vectors")
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"

REPLY_PREFIX = re.compile(r"^(re:|fwd?:|fw:)\s*", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Zoho helpers
# ---------------------------------------------------------------------------

def get_access_token() -> str:
    url = f"https://accounts.zoho.{ZOHO_REGION}/oauth/v2/token"
    data = {
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
    }
    resp = requests.post(url, data=data)
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError(f"Token refresh failed: {resp.json()}")
    log.info("Access token refreshed successfully")
    return token


def _date_range(days_back: int = 10):
    """Return (start_ms, end_ms) covering the last N days."""
    now = datetime.now(timezone.utc)
    end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    start = (now - timedelta(days=days_back)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _get_all_folder_ids(account_id: str, headers: dict) -> list[dict]:
    """Fetch all mail folders so we can scan inbox, spam, newsletters, promotions."""
    url = f"{BASE_URL}/{account_id}/folders"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        log.warning("Could not fetch folders: %s", resp.text)
        return []
    folders = resp.json().get("data", [])
    log.info("Found %d mail folders: %s", len(folders), [f.get("folderName") for f in folders])
    return folders


def _is_reply(subject: str) -> bool:
    return bool(REPLY_PREFIX.match(subject.strip()))


def fetch_todays_emails() -> list[dict]:
    """Fetch today's emails from Zoho Mail, skip replies/forwards."""
    token = get_access_token()
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}

    acc_resp = requests.get(BASE_URL, headers=headers)
    if acc_resp.status_code != 200:
        raise RuntimeError(f"Account lookup failed: {acc_resp.text}")
    account_id = acc_resp.json()["data"][0]["accountId"]
    log.info("Account ID: %s", account_id)

    start_ms, _end_ms = _date_range(days_back=10)

    # Try folder-based scan first; fall back to default inbox view
    folders = _get_all_folder_ids(account_id, headers)
    if folders:
        all_messages = []
        for folder in folders:
            fid = folder.get("folderId")
            fname = folder.get("folderName", "unknown")
            url = f"{BASE_URL}/{account_id}/folders/{fid}/messages?status=all&limit=200"
            resp = requests.get(url, headers=headers)
            if resp.status_code != 200:
                log.warning("Skipping folder '%s' — error: %s", fname, resp.text)
                continue
            msgs = resp.json().get("data", [])
            for m in msgs:
                m["_folder"] = fname
            all_messages.extend(msgs)
            log.info("Folder '%s': %d messages", fname, len(msgs))
    else:
        log.info("Folder API unavailable, falling back to default inbox view")
        url = f"{BASE_URL}/{account_id}/messages/view?status=all&limit=200"
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"Message fetch failed: {resp.text}")
        all_messages = resp.json().get("data", [])
        for m in all_messages:
            m["_folder"] = "Inbox"
        log.info("Default view: %d messages", len(all_messages))

    seen_ids = set()
    emails = []
    skipped_replies = 0
    skipped_old = 0

    for msg in all_messages:
        msg_id = msg.get("messageId")
        if msg_id in seen_ids:
            continue
        seen_ids.add(msg_id)

        received_ms = int(msg.get("receivedTime", "0"))
        if received_ms < start_ms:
            skipped_old += 1
            continue

        subject = msg.get("subject", "")
        if _is_reply(subject):
            skipped_replies += 1
            continue

        emails.append({
            "id": msg_id,
            "sender_name": msg.get("sender", ""),
            "sender_email": msg.get("fromAddress") or _extract_email(msg.get("sender", "")),
            "subject": subject,
            "status": "UNREAD" if msg.get("status") == "0" else "READ",
            "body": msg.get("summary", ""),
            "received": received_ms,
            "folder": msg.get("_folder", ""),
        })

    log.info(
        "Total: %d emails kept, %d replies skipped, %d older emails skipped",
        len(emails), skipped_replies, skipped_old,
    )
    return emails


# ---------------------------------------------------------------------------
# Vectorisation
# ---------------------------------------------------------------------------

def email_to_text(email: dict) -> str:
    return (
        f"subject: {email['subject']}\n"
        f"sender: {email['sender_name']} ({email['sender_email']})\n"
        f"body: {email['body']}"
    )


def vectorize_emails(emails: list[dict], model: SentenceTransformer) -> list[dict]:
    texts = [email_to_text(e) for e in emails]
    vectors = model.encode(texts, show_progress_bar=True)

    records = []
    for email, vec in zip(emails, vectors):
        records.append({
            "email_id": email["id"],
            "sender_name": email["sender_name"],
            "sender_email": email["sender_email"],
            "subject": email["subject"],
            "status": email["status"],
            "body": email["body"],
            "received": email["received"],
            "folder": email.get("folder", ""),
            "vector": vec.tolist(),
        })
    return records


# ---------------------------------------------------------------------------
# Local storage
# ---------------------------------------------------------------------------

def save_vectors(records: list[dict], date_str: str):
    VECTOR_DIR.mkdir(exist_ok=True)
    out_file = VECTOR_DIR / f"vectors_{date_str}.jsonl"
    with out_file.open("w", encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(row) + "\n")
    log.info("Saved %d vectors to %s", len(records), out_file)
    return out_file


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run():
    today_str = datetime.now().strftime("%Y-%m-%d")
    log.info("[1/3] Fetching last 10 days of emails (%s) from Zoho...", today_str)
    emails = fetch_todays_emails()

    if not emails:
        log.info("No emails to vectorize. Done.")
        return

    log.info("[2/3] Loading embedding model (%s)...", EMBED_MODEL_NAME)
    model = SentenceTransformer(EMBED_MODEL_NAME)

    log.info("[3/3] Vectorizing %d email(s)...", len(emails))
    records = vectorize_emails(emails, model)

    save_vectors(records, today_str)

    sample = {k: v for k, v in records[0].items() if k != "vector"}
    sample["vector_dim"] = len(records[0]["vector"])
    log.info("Sample record:\n%s", json.dumps(sample, indent=2))


if __name__ == "__main__":
    run()
