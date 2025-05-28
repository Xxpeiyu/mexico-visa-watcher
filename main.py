import time
import os
import smtplib
from email.mime.text import MIMEText
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
# 移除 webdriver_manager，因為在 Render 上直接指定 Chrome 路徑更穩定
# from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import json # 用於儲存狀態

# 要監控的 Google Calendar 網址
CALENDAR_URLS = [
    "https://calendar.app.google/8rh8qZ6tpgcPF7hM9",
    "https://calendar.app.google/VWmMf4vxR8Hz3yxW9"
]

# Email 設定 (從環境變數讀取)
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT")

# 用於儲存上次已知空位資訊的檔案，避免重複通知
# 在 Render 的 Cron Job 環境中，這個檔案不會持久化。
# 如果您使用 Cron Job 且需要避免重複通知，請考慮使用外部持久化儲存，
# 例如 Render 的 Disk (需付費) 或雲端儲存服務 (如 S3, Google Cloud Storage)。
# 對於 Web Service (即使會休眠)，它會嘗試保持檔案。
LAST_SLOTS_FILE = "last_slots.json"

# 建立 Chrome driver（適用於 Render 部署環境）
def create_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-popup-blocking")

    # *** 關鍵修改：直接指定 Render 環境中的 Chromium 路徑 ***
    # Render 通常會在 /usr/bin/chromium 或 /usr/bin/google-chrome 提供 Chromium
    # 根據 Render 的文件和常見部署經驗，/usr/bin/chromium 是更可靠的選擇
    # 如果這個路徑仍然失敗，您可能需要查閱 Render 的最新文件或嘗試其他常見路徑
    chrome_binary_path = "/usr/bin/chromium"
    if os.path.exists(chrome_binary_path):
        chrome_options.binary_location = chrome_binary_path
        print(f"找到 Chrome Binary：{chrome_binary_path}")
    else:
        # 如果 /usr/bin/chromium 不存在，嘗試 /usr/bin/google-chrome (舊版 Render 或特定環境)
        chrome_binary_path = "/usr/bin/google-chrome"
        if os.path.exists(chrome_binary_path):
            chrome_options.binary_location = chrome_binary_path
            print(f"找到 Chrome Binary (備用路徑)：{chrome_binary_path}")
        else:
            print(f"錯誤：在預設路徑 '{chrome_binary_path}' 和 '/usr/bin/chromium' 都找不到 Chrome。")
            print("請檢查 Render 環境中的 Chrome 路徑，或考慮使用 Docker 部署。")
            # 如果找不到 Chrome，直接拋出錯誤，讓服務部署失敗，以便您能及時發現問題
            raise FileNotFoundError("無法找到 Chrome Binary，請檢查 Render 環境配置。")

    # 移除 ChromeDriverManager().install()，因為我們直接指定了 Chrome Binary
    # 並且 Render 環境中通常已經有 ChromeDriver，不需要額外安裝
    # 這裡我們需要一個 ChromeDriver 的路徑，Render 通常會提供
    # Render 預設的 ChromeDriver 路徑通常與 Chromium 在同一目錄或類似位置
    # 嘗試使用一個常見的 Render ChromeDriver 路徑
    chromedriver_path = "/usr/bin/chromedriver" # Render 環境中常見的 ChromeDriver 路徑
    if not os.path.exists(chromedriver_path):
        # 如果上述路徑不對，嘗試其他常見路徑，或者這一步可能需要您手動確認 Render 環境
        # 或者考慮在 build command 中手動下載 ChromeDriver 到一個已知路徑
        print(f"警告：在預設路徑 '{chromedriver_path}' 找不到 ChromeDriver。")
        print("如果服務失敗，請檢查 Render 環境中的 ChromeDriver 路徑。")
        # 這裡我們仍會嘗試創建服務，但如果 ChromeDriver 不存在，會報錯
        # 為了讓程式碼能繼續運行，我們暫時不在此處拋出錯誤，讓 Selenium 自己去報錯
        # 但理想情況下，如果 ChromeDriver 確定不存在，應該在此處停止
    
    # 創建 Service 實例，直接指定 ChromeDriver 的路徑
    service = Service(executable_path=chromedriver_path)
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

# 載入上次已知的空位資訊，用於判斷是否有新的空位出現
def load_last_slots():
    if os.path.exists(LAST_SLOTS_FILE):
        try:
            with open(LAST_SLOTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"警告：無法解析 {LAST_SLOTS_FILE}，可能是檔案損壞。將重新開始。")
            return []
    return []

# 儲存目前發現的空位資訊
def save_current_slots(slots):
    with open(LAST_SLOTS_FILE, "w", encoding="utf-8") as f:
        json.dump(slots, f, ensure_ascii=False, indent=4)

# 實際執行網頁爬蟲檢查，判斷是否有空位
def check_appointments():
    driver = None
    all_found_slots = [] # 儲存本次檢查發現的所有空位
    try:
        driver = create_driver()
        for url in CALENDAR_URLS:
            print(f"正在檢查網址：{url}")
            driver.get(url)
            # 給予足夠時間讓網頁載入和 JavaScript 執行，特別是 Google Calendar 這種動態頁面
            time.sleep(5)

            # 滾動頁面到底部，確保所有內容（包括動態載入的事件）都已載入
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2) # 等待滾動後的內容載入

            soup = BeautifulSoup(driver.page_source, 'html.parser')

            # --- 針對 Google Calendar 的特定元素搜尋 ---
            # 這是最關鍵且最容易出錯的部分。
            # Google Calendar 的事件通常會顯示為 `div` 元素，其中包含事件標題、時間等。
            # 您需要使用瀏覽器開發者工具 (按 F12) 檢查實際頁面，
            # 找到代表「可預約空位」的 HTML 元素及其獨特的 `class` 或其他屬性。
            #
            # 常見的 Google Calendar 事件元素可能包含以下 class：
            # 'event-chip', 'event-container', 'event-title', 'event-summary'
            # 這裡我嘗試尋找所有 `div` 元素，它們的 `class` 包含 'event' 或 'chip'。
            # 並且，這些事件的文本內容不能是空的。
            
            # 尋找所有可能代表日曆事件的元素
            # lambda 函數用於檢查 class 屬性，即使它為 None 或不包含特定字串
            event_elements = soup.find_all('div', class_=lambda x: x and ('event' in x or 'chip' in x))
            
            current_url_slots = []
            for event_el in event_elements:
                event_text = event_el.get_text(separator=" ", strip=True)
                # 確保事件文本不為空，且不包含明顯的「無活動」或「已預約」等關鍵字
                # 您可能需要根據實際頁面顯示的「無空位」文字進行調整
                if event_text and "No events" not in event_text and "已預約" not in event_text and "booked" not in event_text:
                    # 使用 URL 和事件文本作為唯一識別符，確保跨運行的一致性
                    current_url_slots.append(f"{url}-{event_text}")
            
            all_found_slots.extend(current_url_slots)

            if current_url_slots:
                print(f"✅ 在 {url} 發現潛在空位：{len(current_url_slots)} 個")
            else:
                print(f"❌ 在 {url} 未發現空位")

    except Exception as e:
        print(f"檢查預約時發生錯誤：{e}")
        # 發生錯誤時，不發送通知，並返回 False
        return False

    finally:
        if driver:
            driver.quit() # 確保瀏覽器驅動程式關閉

    # 載入上次已知的空位資訊
    last_known_slots = load_last_slots()
    
    # 找出本次檢查中新發現的空位 (上次沒有，這次有的)
    new_slots = [slot for slot in all_found_slots if slot not in last_known_slots]

    if new_slots:
        print(f"✨ 發現新空位！共 {len(new_slots)} 個")
        # 有新空位時，更新上次已知的空位列表
        save_current_slots(all_found_slots)
        return True # 有新空位，需要發送通知
    else:
        print("沒有發現新空位或空位已通知過。")
        # 如果沒有新空位，但本次檢查仍有空位（只是已通知過），也更新一下狀態
        # 以防某些空位被移除後又重新出現，或者頁面內容有微小變化
        if all_found_slots:
             save_current_slots(all_found_slots)
        return False # 沒有新空位，不需要發送通知

# 發送 email 通知
def send_email_notification():
    # 檢查環境變數是否已設定
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECIPIENT:
        print("錯誤：Email 設定不完整，無法發送通知。請檢查環境變數 EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT。")
        return

    msg = MIMEText("有簽證預約空位出現了！請馬上預約！\n\n請檢查以下網址：\n" + "\n".join(CALENDAR_URLS))
    msg["Subject"] = "【簽證預約通知】有空位了！"
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECIPIENT

    try:
        # 使用 SSL 加密連線到 Gmail SMTP 伺服器
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_SENDER, EMAIL_PASSWORD) # 登入您的 Gmail 帳戶
            smtp.send_message(msg) # 發送郵件
            print("📧 已發送通知 Email")
    except Exception as e:
        print(f"發送 Email 失敗：{e}")
        print("請檢查您的 Gmail 帳戶是否開啟了「應用程式密碼」，以及寄件者、密碼和收件者是否正確。")

# 主流程
if __name__ == "__main__":
    print("--- 開始檢查簽證預約空位 ---")
    if check_appointments(): # 如果有發現新的空位
        send_email_notification() # 就發送通知
    print("--- 檢查結束 ---")


