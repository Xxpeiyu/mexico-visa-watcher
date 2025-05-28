import time
import os
import smtplib
from email.mime.text import MIMEText
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# 建立 Chrome driver（適用於 Render）
def create_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 無頭模式
    chrome_options.add_argument("--no-sandbox")  # 為避免 Docker 環境問題
    chrome_options.add_argument("--disable-dev-shm-usage")  # 防止共享記憶體問題

    # 在 Render 上指定 Chromium 路徑
    chrome_binary = "/usr/bin/google-chrome"  # Render 支援 google-chrome
    if os.path.exists(chrome_binary):
        chrome_options.binary_location = chrome_binary

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

# 實際執行網頁爬蟲檢查
def check_appointments():
    driver = create_driver()
    url = "https://example.com/appointment"  # <-- 請替換為實際網址
    driver.get(url)

    time.sleep(3)  # 等待網頁載入
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # 根據實際網頁內容修改下列搜尋條件
    if "No appointments" not in soup.text:
        print("✅ 有空位")
        result = True
    else:
        print("❌ 無空位")
        result = False

    driver.quit()
    return result

# 發送 email 通知（選填）
def send_email_notification():
    sender = os.environ.get("EMAIL_SENDER")
    password = os.environ.get("EMAIL_PASSWORD")
    recipient = os.environ.get("EMAIL_RECIPIENT")

    msg = MIMEText("有簽證預約空位出現了！請馬上預約！")
    msg["Subject"] = "【簽證預約通知】有空位了！"
    msg["From"] = sender
    msg["To"] = recipient

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)
        print("📧 已發送通知 Email")

# 主流程
if __name__ == "__main__":
    if check_appointments():
        send_email_notification()
