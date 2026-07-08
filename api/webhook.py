from http.server import BaseHTTPRequestHandler
import os
import json
import requests
import google.generativeai as genai
from io import BytesIO
from docx import Document

# تنظیمات کلاینت جمینای
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # دریافت پیام از تلگرام
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        update = json.loads(post_data)

        if 'message' in update and 'document' in update['message']:
            chat_id = update['message']['chat']['id']
            document = update['message']['document']
            
            # بررسی فرمت فایل
            if document.get('file_name', '').endswith('.docx'):
                self.send_telegram_message(chat_id, "فایل دریافت شد. در حال پردازش توسط ایجنت... ⏳")
                
                try:
                    # ۱. دانلود فایل
                    file_id = document['file_id']
                    file_info = requests.get(f"{TELEGRAM_URL}/getFile?file_id={file_id}").json()
                    file_path = file_info['result']['file_path']
                    download_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
                    file_content = requests.get(download_url).content
                    
                    # ۲. استخراج متن
                    doc = Document(BytesIO(file_content))
                    text = '\n'.join([para.text for para in doc.paragraphs if para.text.strip()])
                    
                    # ۳. استفاده از مدل جمینای (Flash بهینه شده)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    prompt = (
                        "شما یک دستیار ارشد هستید. یک خلاصه مدیریتی از گزارش زیر تهیه کنید "
                        "که شامل این سه بخش باشد:\n"
                        "۱. هدف اصلی گزارش\n"
                        "۲. نکات کلیدی و یافته‌ها\n"
                        "۳. اقدامات بعدی (Action Items)\n"
                        "لحن پاسخ کاملاً رسمی و حرفه‌ای باشد.\n\n"
                        f"متن گزارش:\n{text}"
                    )
                    
                    response = model.generate_content(prompt)
                    
                    # ۴. ارسال پاسخ
                    self.send_telegram_message(chat_id, response.text)
                    
                except Exception as e:
                    # ارسال خطای فنی به کاربر برای عیب‌یابی
                    self.send_telegram_message(chat_id, f"❌ خطای فنی رخ داد:\n{str(e)}")
            else:
                chat_id = update['message']['chat']['id']
                self.send_telegram_message(chat_id, "⚠️ لطفاً فقط فایل ورد (docx.) ارسال کنید.")

        # پاسخ به تلگرام برای تأیید دریافت درخواست
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def send_telegram_message(self, chat_id, text):
        try:
            # ارسال پیام به صورت تکه‌تکه اگر متن طولانی بود (برای جلوگیری از خطای ۴۰۰)
            requests.post(f"{TELEGRAM_URL}/sendMessage", json={"chat_id": chat_id, "text": text[:4000]})
        except Exception:
            pass
