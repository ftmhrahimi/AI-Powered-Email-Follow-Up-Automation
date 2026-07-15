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

Configuration is read from environment variables so no operator-specific host or secret is hardcoded in the source:

| Environment variable | Description |
|---|---|
| `SMTP_SERVER` | Your outgoing mail server, e.g. `smtp.example.com` (required) |
| `SMTP_PORT` | `587` (STARTTLS) or `465` (SSL). Defaults to `587` |
| `SMTP_VERIFY_TLS` | `true` (default) verifies the server's TLS certificate. Set to `false` only for internal servers with self-signed certs on a trusted network |
| `OPENAI_API_KEY` | Your OpenAI API key (required unless `LLM_SIMULATION` is on) |

`LLM_API_ENDPOINT`, `LLM_MODEL_NAME`, and `LLM_SIMULATION` remain in-script settings (set `LLM_SIMULATION = True` to test the flow without calling the real API).

Example:

```bash
export SMTP_SERVER="smtp.example.com"
export OPENAI_API_KEY="sk-..."
```

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


- The OpenAI API key and mail server host are loaded from environment variables (`OPENAI_API_KEY`, `SMTP_SERVER`); nothing operator-specific or secret is hardcoded in the source.
- User-supplied email addresses are validated before use; malformed recipients are skipped and an invalid sender aborts the run.
- The mailbox password is entered at runtime via `getpass` and is not written to disk, but it is held in memory in plain text for the duration of the run.
- SSL certificate verification is **enabled by default** for the SMTP connection. It can be disabled with `SMTP_VERIFY_TLS=false` for internal mail servers with self-signed certs, but doing so removes protection against man-in-the-middle attacks — only do this on a trusted network.
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
