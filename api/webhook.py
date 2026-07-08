from http.server import BaseHTTPRequestHandler
import os
import json
import requests
import google.generativeai as genai
from io import BytesIO
from docx import Document

# خواندن کلیدها از تنظیمات امن ورسل
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
            
            # بررسی اینکه آیا فایل ورد است؟
            if document['file_name'].endswith('.docx'):
                self.send_telegram_message(chat_id, "فایل دریافت شد. در حال تحلیل و خلاصه‌سازی... ⏳")
                
                try:
                    # ۱. دانلود فایل از سرور تلگرام
                    file_id = document['file_id']
                    file_info = requests.get(f"{TELEGRAM_URL}/getFile?file_id={file_id}").json()
                    file_path = file_info['result']['file_path']
                    download_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
                    file_content = requests.get(download_url).content
                    
                    # ۲. استخراج متن از فایل ورد
                    doc = Document(BytesIO(file_content))
                    text = '\n'.join([para.text for para in doc.paragraphs if para.text.strip()])
                    
                    # ۳. ارسال به جمینای
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    prompt = f"شما یک دستیار ارشد هستید. یک خلاصه مدیریتی از گزارش زیر تهیه کنید که شامل ۱. هدف اصلی ۲. نکات کلیدی ۳. اقدامات بعدی (Action Items) باشد. لحن رسمی باشد.\n\nمتن گزارش:\n{text}"
                    response = model.generate_content(prompt)
                    
                    # ۴. ارسال نتیجه به کاربر در تلگرام
                    self.send_telegram_message(chat_id, response.text)
                    
                except Exception as e:
                    self.send_telegram_message(chat_id, f"متاسفانه خطایی رخ داد: {str(e)}")
            else:
                chat_id = update['message']['chat']['id']
                self.send_telegram_message(chat_id, "لطفاً فقط فایل ورد با فرمت docx. ارسال کنید.")

        # پاسخ موفقیت‌آمیز به سرور تلگرام برای بسته شدن کانکشن
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def send_telegram_message(self, chat_id, text):
        requests.post(f"{TELEGRAM_URL}/sendMessage", json={"chat_id": chat_id, "text": text})
