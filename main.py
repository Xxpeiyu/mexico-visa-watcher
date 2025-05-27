import os
import smtplib
import requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def check_calendar(urls):
    for url in urls:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                if "No appointments available" not in soup.text:
                    return url
        except Exception as e:
            print(f"Error checking {url}: {e}")
    return None

def send_email(subject, body, to_email):
    email_user = os.environ.get("EMAIL_USER")
    email_pass = os.environ.get("EMAIL_PASS")

    msg = MIMEMultipart()
    msg["From"] = email_user
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(email_user, email_pass)
            server.send_message(msg)
        print("Email sent!")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    urls = os.environ.get("CHECK_URLS", "").split(",")
    notify_to = os.environ.get("EMAIL_TO")

    available_url = check_calendar(urls)
    if available_url:
        send_email(
            "🎉 Mexico Visa Slot Available!",
            f"New slot available! Check this link: {available_url}",
            notify_to,
        )
    else:
        print("No slot available.")
