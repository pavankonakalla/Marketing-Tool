# Job Matching Tool

Match resumes against job emails from Zoho Mail. Upload a ZIP of resumes organized by tech stack and get an Excel sheet with ranked matches, missing skills, and draft reply messages.

## Setup (One-time)

### 1. Install Python 3.11+

Download from https://www.python.org/downloads/

### 2. Clone the repo

```bash
git clone <repo-url>
cd "Marketing Tool"
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Get your Zoho credentials

1. Go to https://api-console.zoho.in/ (use .com/.eu based on your region)
2. Create a **Self Client** or **Server-based** app
3. Generate an authorization code with scope: `ZohoMail.messages.READ`
4. Run `python Api.py` with your fresh code to get a refresh token
5. Note down: `CLIENT_ID`, `CLIENT_SECRET`, `REFRESH_TOKEN`

### 5. Set environment variables

Open PowerShell and run:

```powershell
$env:ZOHO_CLIENT_ID="your_client_id"
$env:ZOHO_CLIENT_SECRET="your_client_secret"
$env:ZOHO_REFRESH_TOKEN="your_refresh_token"
$env:ZOHO_REGION="in"
```

> Use `in` for India, `com` for US, `eu` for EU, `com.au` for Australia.

## Daily Usage

### Step 1: Fetch and vectorize emails

Run this once a day (or whenever you want fresh data):

```bash
python daily_vectorize.py
```

This fetches the last 10 days of emails from your Zoho inbox, skips replies/forwards, and saves vectors locally in the `vectors/` folder.

### Step 2: Launch the matching UI

```bash
python -m streamlit run generate_op.py
```

This opens a web UI in your browser.

### Step 3: Upload resumes

Prepare a ZIP file with this structure:

```
resumes.zip
├── Java/
│   ├── john_doe.pdf
│   ├── jane_smith.pdf
├── Python/
│   ├── alice.docx
└── .NET/
    └── bob.pdf
```

Each folder name = tech stack. Each file inside = a resume (PDF or DOCX).

### Step 4: Download results

Click **"Download Full Results (Excel)"** to get one Excel file with:
- One sheet per tech stack folder
- Ranked job matches with similarity scores
- Which resumes match each job
- Resume match summary (e.g. "7/10 in 80-90%")
- Missing skills per resume
- Draft reply message ready to copy-paste

## Files

| File | Purpose |
|---|---|
| `daily_vectorize.py` | Fetches Zoho emails and creates vectors |
| `generate_op.py` | Streamlit UI for resume matching |
| `Api.py` | Helper to get initial Zoho refresh token |
| `Ingestion.py` | Original email fetch test script |
| `requirements.txt` | Python dependencies |

## Notes

- Never commit credentials to the repo
- Vectors are stored locally in `vectors/` (excluded from git)
- Each team member uses their own Zoho credentials
