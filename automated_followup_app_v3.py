# automated_followup_app.py - Combined Automated Follow-up Email Application

import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from collections import Counter
import re
import requests
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import ssl
import getpass
import datetime

# --- EWS Fetching Imports ---
from exchangelib import DELEGATE, Account, Credentials, Configuration, Message, EWSTimeZone, EWSDateTime, HTMLBody
from exchangelib.properties import Mailbox
from bs4 import BeautifulSoup
# ----------------------------

# --- GLOBAL CONFIGURATIONS ---
SMTP_SERVER = "mail.mtnirancell.ir"
SMTP_PORT = 587

# LLM Configuration (OpenAI API)
LLM_API_ENDPOINT = "https://api.openai.com/v1/chat/completions"
LLM_MODEL_NAME = "gpt-3.5-turbo"

LLM_SIMULATION = False
# -----------------------------

# --- LLM API Call Function (UNCHANGED) ---
def call_llm(prompt_text, model_name, api_endpoint, api_key):
    # ... (unchanged)
    if LLM_SIMULATION:
        if "identify action items" in prompt_text:
            return """[
              {
                "action": "prepare a draft of the social media strategy",
                "responsible_person": "User B",
                "deadline": "Friday"
              },
              {
                "action": "schedule a follow-up meeting",
                "responsible_person": "User A",
                "deadline": "next week"
              },
              {
                "action": "share the strategy draft with User A and User C",
                "responsible_person": "User B",
                "deadline": null
              }
            ]"""
        elif "draft a follow-up email" in prompt_text:
            return """Subject: Follow-up: Q3 Marketing Plan & Social Media Strategy

Hi Team,

This email is a follow-up to our recent discussion regarding the Q3 marketing plan.

Here's a summary of the key points and action items:

* User B will prepare a draft of the social media strategy by Friday.
* User A will schedule a follow-up meeting next week to review the draft.
* User B will share the strategy draft with User A and User C.

Please let me know if you have any questions or require further clarification.

Best regards,
AI System"""
        else:
            return "This is a simulated summary of the conversation about the Q3 marketing plan and assigned tasks."

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.2,
        "max_tokens": 500
    }

    try:
        response = requests.post(api_endpoint, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        response_data = response.json()
        if response_data and response_data.get('choices') and response_data['choices'][0].get('message'):
            return response_data['choices'][0]['message']['content'].strip()
        else:
            print(f"Unexpected OpenAI API response structure: {response_data}")
            return "LLM_ERROR"
    except requests.exceptions.RequestException as e:
        print(f"Error calling OpenAI API: {e}")
        return "LLM_ERROR"

# --- EWS Fetching Functions (UNCHANGED) ---
def get_plain_text_body_ews(msg):
    # ... (unchanged)
    if msg.body:
        if msg.text_body:
            return msg.text_body
        elif msg.body.content_type == 'HTML' and msg.body.text:
            soup = BeautifulSoup(msg.body.text, 'html.parser')
            return soup.get_text(separator=' ', strip=True)
    return ""

def fetch_emails_by_subject_ews(email_address, password, search_subject):
    # ... (unchanged)
    fetched_messages = []
    try:
        credentials = Credentials(email_address, password)
        account = Account(primary_smtp_address=email_address, credentials=credentials, autodiscover=True, access_type=DELEGATE)

        print(f"Successfully connected to account: {account.primary_smtp_address}")

        messages = account.inbox.filter(subject__contains=search_subject).order_by('datetime_received')

        print(f"Found {messages.count()} emails with subject containing: '{search_subject}'")

        for msg in messages:
            sender_email = msg.sender.email_address if msg.sender else 'unknown'
            sender_name_display = msg.sender.name if msg.sender and msg.sender.name else sender_email.split('@')[0].replace('.', ' ').title()

            fetched_messages.append({
                "message_id": msg.message_id,
                "subject": msg.subject,
                "sender": sender_email,
                "sender_name_display": sender_name_display,
                "receivedDateTime": msg.datetime_received.isoformat(),
                "content": get_plain_text_body_ews(msg)
            })

        print("Successfully fetched emails via EWS.")
        return fetched_messages

    except Exception as e:
        print(f"An error occurred during EWS fetching: {e}")
        print("This could be due to authentication issues (check App Password if MFA is on),")
        print("incorrect EWS server URL (if autodiscover fails), or network problems.")
        return []

# --- SMTP Sending Function (UNCHANGED) ---
def send_email(subject, body_html, to_addresses, sender_email, sender_password, smtp_server, smtp_port):
    """
    Sends an HTML email using SMTP and returns the message object if successful.
    """
    print(f"\n--- Attempting to send email from: {sender_email} ---")
    print(f"To: {', '.join(to_addresses)}")
    print(f"Subject: {subject}")
    print("-" * 50)

    message = MIMEMultipart("alternative")
    message["From"] = sender_email
    message["To"] = ", ".join(to_addresses)
    message["Subject"] = subject

    html_part = MIMEText(body_html, "html")
    message.attach(html_part)

    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        if smtp_port == 587:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls(context=context)
        elif smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, context=context)
        else:
            print(f"Error: Unsupported SMTP port {smtp_port}. Please use 587 or 465.")
            return False, None

        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_addresses, message.as_string())
        server.quit()

        print("\nSUCCESS: Email sent successfully!")
        return True, message

    except smtplib.SMTPAuthenticationError:
        print("\nERROR: SMTP Authentication Failed. Check your email address and password.")
        print("If using Office 365, you might need an App Password if MFA is enabled.")
        return False, None
    except smtplib.SMTPConnectError as e:
        print(f"\nERROR: Could not connect to SMTP server. Check server address and port: {smtp_server}:{smtp_port}")
        print(f"Details: {e}")
        return False, None
    except smtplib.SMTPRecipientsRefused as e:
        print(f"\nERROR: Recipient refused: {e.recipients}")
        print("Check if recipient email addresses are correct and valid.")
        return False, None
    except Exception as e:
        print(f"\nAN UNEXPECTED ERROR OCCURRED during email sending: {e}")
        return False, None

# --- Save Email to Sent Items via EWS (UNCHANGED) ---
def save_email_to_sent_items_ews(sender_email, sender_password, subject, body_html, to_addresses):
    print("\n--- Attempting to save email to Sent Items via EWS ---")
    try:
        print("Connecting to EWS account for saving...")
        credentials = Credentials(sender_email, sender_password)
        account = Account(primary_smtp_address=sender_email, credentials=credentials, autodiscover=True, access_type=DELEGATE)
        print(f"EWS account connected: {account.primary_smtp_address}")

        print("Preparing EWS Message object...")
        ews_to_recipients = [Mailbox(email_address=addr) for addr in to_addresses]

        local_timezone = EWSTimeZone.localzone()

        m = Message(
            account=account,
            folder=account.sent,
            subject=subject,
            body=HTMLBody(body_html),
            to_recipients=ews_to_recipients,
            datetime_sent=EWSDateTime.now(local_timezone)
        )

        print("Saving message to Sent Items...")
        m.save()

        print("SUCCESS: Email saved to Sent Items folder via EWS!")
        return True
    except Exception as e:
        print(f"ERROR: Could not save email to Sent Items via EWS: {e}")
        print("Possible causes:")
        print("  - EWS Authentication Failure (check App Password if MFA is on)")
        print("  - Incorrect EWS server URL (if autodiscover fails)")
        print("  - Lack of permissions to create items in 'Sent Items' folder")
        print("  - Network issues or firewalls blocking EWS access")
        return False


# --- Main Application Logic (FIXED f-string error) ---
def run_automated_followup_app():
    print("="*60)
    print("  Automated Follow-up Email Generation Application  ")
    print("="*60)

    print("\nPlease enter your email details to fetch and send emails:")
    user_email = input("Your Company Email Address (e.g., your.name@mtnirancell.ir): ").strip()
    user_password = getpass.getpass("Your Email Password (will not be shown): ").strip()

    search_subject = input("Enter the EXACT Subject of the email thread to analyze: ").strip()
    recipient_emails_str = input("Enter recipient email(s) for the follow-up (comma-separated): ").strip()
    recipient_emails = [email.strip() for email in recipient_emails_str.split(',') if email.strip()]

    if not recipient_emails:
        print("WARNING: No recipient emails entered. Sending to your own email as fallback.")
        recipient_emails = [user_email]

    print("\nStarting Automated Follow-up Process...")

    # --- Step 0: Fetching Emails from Outlook (Ingestion Service via EWS) ---
    print("\n--- Step 0: Fetching Emails from Outlook (Ingestion Service via EWS) ---")
    fetched_emails = fetch_emails_by_subject_ews(
        user_email, user_password, search_subject
    )

    if not fetched_emails:
        print("ERROR: Could not fetch emails via EWS. Application cannot proceed.")
        return

    # --- Step 1: Reconstructing Conversation (Conversation Builder) ---
    print("\n--- Step 1: Reconstructing Conversation (Conversation Builder) ---")
    conversation_text_for_ai = ""
    for msg in fetched_emails:
        conversation_text_for_ai += f"{msg['sender_name_display']}: {msg['content']}\n"

    print("\n--- Reconstructed Conversation for AI Input ---")
    print(conversation_text_for_ai)
    print("="*50)

    # --- Step 2: Extracting Action Items and Responsibilities (via LLM) ---
    print("\n--- Step 2: Extracting Action Items and Responsibilities (via LLM) ---")
    action_prompt = f"""You are an AI assistant designed to identify action items and the person responsible for each from a conversation. For each action, also note any mentioned deadlines. Output your findings as a JSON array of objects, where each object has the keys "action", "responsible_person", and "deadline". If no responsible person is explicitly mentioned, use "unspecified". If no deadline is mentioned, use null.

Here is the conversation:
{conversation_text_for_ai}"""

    raw_actions_json = call_llm(action_prompt, LLM_MODEL_NAME, LLM_API_ENDPOINT, LLM_API_KEY)
    if raw_actions_json == "LLM_ERROR":
        print("ERROR: LLM failed to extract actions. Application cannot proceed.")
        return

    try:
        extracted_actions = json.loads(raw_actions_json)
        print("Extracted Actions:")
        for action in extracted_actions:
            print(f"- Action: {action.get('action')}, Responsible: {action.get('responsible_person')}, Deadline: {action.get('deadline')}")
    except json.JSONDecodeError:
        print(f"WARNING: LLM did not return valid JSON for actions. Raw response: {raw_actions_json}")
        extracted_actions = []
    print("-" * 40)

    # --- Step 3: Summarizing Conversation (via LLM) ---
    print("\n--- Step 3: Summarizing Conversation (via LLM) ---")
    summary_prompt = f"""Summarize the following conversation concisely, highlighting the main points and overall outcome.

Conversation:
{conversation_text_for_ai}"""
    ai_summary = call_llm(summary_prompt, LLM_MODEL_NAME, LLM_API_ENDPOINT, LLM_API_KEY)
    if ai_summary == "LLM_ERROR":
        print("ERROR: LLM failed to generate summary. Application cannot proceed.")
        return
    print(f"Generated Summary:\n{ai_summary}\n")
    print("-" * 40)

    # --- Step 4: Recipient Identification (LLM-driven or inferred) ---
    print("\n--- Step 4: Identifying Recipients ---")
    all_participants_from_fetched = set()
    for msg in fetched_emails:
        all_participants_from_fetched.add(msg['sender'])

    final_recipients = list(set(recipient_emails + list(all_participants_from_fetched)))

    print(f"Suggested Recipients from conversation: {', '.join(list(all_participants_from_fetched))}")
    print(f"Final Recipients (User-provided + Inferred): {', '.join(final_recipients)}\n")
    print("-" * 40)


    # --- Step 5: Generating Draft Email (via LLM) ---
    print("\n--- Step 5: Generating Draft Email (via LLM) ---")
    actions_formatted_for_email_prompt = "\n".join([
        f"- {item.get('action')} (Responsible: {item.get('responsible_person')}, Due: {item.get('deadline') if item.get('deadline') else 'N/A'})"
        for item in extracted_actions
    ])

    email_generation_prompt = f"""You are an AI assistant tasked with drafting a professional follow-up email based on the following conversation summary and action items.

Conversation Summary:
{ai_summary}

Action Items:
{actions_formatted_for_email_prompt}

Key Participants (who should receive this email): {', '.join(final_recipients)}

Draft the follow-up email, including a suitable subject line. Start with "Subject: " for the subject line."""

    generated_email_raw = call_llm(email_generation_prompt, LLM_MODEL_NAME, LLM_API_ENDPOINT, LLM_API_KEY)
    if generated_email_raw == "LLM_ERROR":
        print("ERROR: LLM failed to generate email. Application cannot proceed.")
        return

    subject_match = re.search(r"Subject: (.+?)\n\n(.+)", generated_email_raw, re.DOTALL)
    if subject_match:
        generated_subject = subject_match.group(1).strip()
        generated_body_raw = subject_match.group(2).strip()
    else:
        generated_subject = f"Follow-up on: {search_subject}"
        generated_body_raw = generated_email_raw.strip()

    # --- NEWLINE FIX: Convert plain text newlines to HTML <br> tags ---
    # Using .format() for multiline HTML to avoid f-string backslash issues
    generated_body_content_with_breaks = generated_body_raw.replace('\n', '<br>')
    generated_body_html = """
<html>
<head></head>
<body>
<p>
{}
</p>
</body>
</html>
""".format(generated_body_content_with_breaks)


    print("\n" + "="*50)
    print("--- AI GENERATED DRAFT EMAIL ---")
    print(f"To: {', '.join(final_recipients)}")
    print(f"Subject: {generated_subject}")
    # Print the raw HTML body to console for debugging, if desired, but usually not needed for presentation
    # print("\n" + generated_body_html)
    print("\n(Email body generated with proper line breaks)") # Indicate success without printing full HTML
    print("="*50)

    # --- User Review and Send ---
    send_confirmation = input("\nDo you want to send this email? (yes/no): ").strip().lower()
    if send_confirmation == 'yes':
        sent_success, sent_message_obj = send_email(generated_subject, generated_body_html, final_recipients, user_email, user_password, SMTP_SERVER, SMTP_PORT)
        if sent_success:
            save_email_to_sent_items_ews(user_email, user_password, generated_subject, generated_body_html, final_recipients)
    else:
        print("Email not sent. You can copy the draft from above.")

    print("\nApplication finished.")
    if LLM_SIMULATION:
        print("\nNOTE: LLM responses were simulated. For real AI, ensure LLM_SIMULATION = False and correct API key.")

if __name__ == "__main__":
    run_automated_followup_app()