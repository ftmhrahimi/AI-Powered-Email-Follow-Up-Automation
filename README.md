# Automated Follow-up Email Generator

A command-line tool that reads an email thread from an Outlook/Exchange mailbox, uses an LLM to summarize the conversation and extract action items, drafts a follow-up email, and (optionally) sends it and saves a copy to Sent Items.

> This script is one part of a larger project — this README covers only this module.

## What it does

1. **Fetch** — Connects to your mailbox via EWS (Exchange Web Services) and retrieves all emails whose subject contains a given search string.
2. **Reconstruct** — Stitches the fetched messages into a single conversation transcript.
3. **Extract action items** — Sends the transcript to an LLM, which returns a JSON list of actions, responsible people, and deadlines.
4. **Summarize** — Sends the transcript to the LLM again to get a concise summary.
5. **Identify recipients** — Combines the recipients you typed in with the senders found in the thread.
6. **Draft email** — Asks the LLM to write a professional follow-up email (subject + HTML body) from the summary and action items.
7. **Review & send** — Shows you the draft and asks for confirmation before sending via SMTP. If sent, a copy is also saved to the mailbox's Sent Items folder via EWS.

## Requirements

- Python 3.9+
- An Exchange/Outlook mailbox reachable via EWS (autodiscover must work, or you'll need to adjust the connection code)
- An OpenAI API key (unless running in simulation mode)
- SMTP access on the same mail server (used for sending, separate from EWS which is used for fetching/saving)

### Python packages

```
nltk
requests
exchangelib
beautifulsoup4
```

Install with:

```bash
pip install nltk requests exchangelib beautifulsoup4
```

## Configuration

Before running, set the following in the script (or, better, move them to environment variables — see **Security** below):

| Variable | Description |
|---|---|
| `SMTP_SERVER` | Your outgoing mail server, e.g. `mail.example.com` |
| `SMTP_PORT` | `587` (STARTTLS) or `465` (SSL) |
| `LLM_API_ENDPOINT` | OpenAI chat completions endpoint |
| `LLM_MODEL_NAME` | e.g. `gpt-3.5-turbo` |
| `LLM_API_KEY` | Your OpenAI API key |
| `LLM_SIMULATION` | Set to `True` to test the flow without calling the real API (returns canned responses) |

## Usage

Run the script:

```bash
python automated_followup_app_v2.py
```

You'll be prompted for:

1. **Your company email address** — used to log in to EWS and SMTP.
2. **Your email password** — entered securely (hidden input), not stored.
3. **The exact subject** of the email thread you want summarized.
4. **Recipient email(s)** for the follow-up, comma-separated.

The script will then fetch the thread, print the reconstructed conversation, extract action items, generate a summary, draft the follow-up email, and ask **yes/no** before actually sending it.

## Security notes

⚠️ **Do not commit real credentials or API keys to this repository.**

- The current version has a hardcoded OpenAI API key in the source. Before pushing this to git, remove it and load it from an environment variable instead, e.g.:

  ```python
  import os
  LLM_API_KEY = os.environ["OPENAI_API_KEY"]
  ```

- The mailbox password is entered at runtime via `getpass` and is not written to disk, but it is held in memory in plain text for the duration of the run.
- SSL certificate verification is disabled for the SMTP connection (`context.check_hostname = False`, `context.verify_mode = ssl.CERT_NONE`). This is convenient for internal mail servers with self-signed certs, but it removes protection against man-in-the-middle attacks — only do this on a trusted network.
- If your account has MFA enabled, you'll likely need an app-specific password for EWS/SMTP to work.

## Known limitations

- The recipient/subject search relies on an **exact** subject string; partial thread matches with modified subjects (e.g. "Re: ...") may be missed or need adjusting.
- If the LLM does not return valid JSON for action items, the script continues with an empty action list rather than failing.
- Email parsing (`Subject: ... \n\n ...` regex) assumes the LLM follows the requested format; unexpected formatting falls back to a generic subject line.

## Project structure

```
.
└── automated_followup_app_v2.py   # main script (fetch → summarize → draft → send)
```
