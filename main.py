import os
import smtplib
import ssl
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

CHECK_URLS = os.getenv("CHECK_URLS", "").split(",")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")

def check_appointments():
    slots_available = False

    for url in CHECK_URLS:
        try:
            response = requests.get(url.strip(), timeout=10)
            if response.status_code == 200:
                page_text = response.content.decode('utf-8')  # 用utf-8解碼
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
    slots_available = check_appointments()

    if slots_available:
        print("📌 Detected available slots, sending notification.")
        send_email()
    else:
        print("🔄 No available slots detected.")
