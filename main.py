import os
import smtplib
import ssl
import requests
import hashlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

CHECK_URLS = os.getenv("CHECK_URLS", "").split(",")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")

HASH_STORE_FILE = "last_hash.txt"

def get_hash(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def check_appointments():
    combined_content = ""
    for url in CHECK_URLS:
        try:
            response = requests.get(url.strip(), timeout=10)
            if response.status_code == 200:
                combined_content += response.text
        except Exception as e:
            print(f"Error checking {url}: {e}")
    return combined_content

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
    content = check_appointments()
    current_hash = get_hash(content)

    last_hash = ""
    if os.path.exists(HASH_STORE_FILE):
        with open(HASH_STORE_FILE, "r") as f:
            last_hash = f.read().strip()

    if current_hash != last_hash:
        print("📌 Change detected! Sending notification.")
        send_email()
        with open(HASH_STORE_FILE, "w") as f:
            f.write(current_hash)
    else:
        print("🔄 No changes detected.")
