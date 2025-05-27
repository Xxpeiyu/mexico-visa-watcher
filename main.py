import os
import smtplib
import ssl
import requests
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

CHECK_URLS = os.getenv("CHECK_URLS", "").split(",")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")

STATE_FILE = "slot_state.json"  # 用來保存上次狀態

def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"slots_available": False}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def check_appointments():
    slots_available = False

    for url in CHECK_URLS:
        try:
            response = requests.get(url.strip(), timeout=10)
            if response.status_code == 200:
                page_text = response.content.decode('utf-8')
                print(f"--- Content preview from {url} ---")
                print(page_text[:1000])
                print(f"--- End of preview ---\n")
                if "在這些天中沒有可預約的時段" not in page_text:
                    slots_available = True
        except Exception as e:
            print(f"Error checking {url}: {e}")

    return slots_available

def send_email():
    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO
    msg["Subject"] = "📅 New Appointment Slot Detected"

    body = "There may be new slots available at the following URLs:\n\n"
    body += "\n".join(CHECK_URLS)

    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, EMAIL_TO, msg.as_string())
            print("✅ Email sent successfully.")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

if __name__ == "__main__":
    prev_state = load_state()
    current_slots_available = check_appointments()

    if current_slots_available and not prev_state.get("slots_available", False):
        print("📌 Detected new available slots, sending notification.")
        send_email()
    else:
        print("🔄 No new available slots detected or already notified.")

    # 更新狀態（不管是否發郵件，都更新狀態）
    save_state({"slots_available": current_slots_available})
