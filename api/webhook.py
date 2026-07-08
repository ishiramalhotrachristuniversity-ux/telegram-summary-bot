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

def get_best_model():
    """یافتن هوشمند مدل در دسترس برای جلوگیری از خطای 404"""
    models = genai.list_models()
    for m in models:
        if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name:
            return genai.GenerativeModel(m.name)
    return genai.GenerativeModel('gemini-pro') # بازگشت به مدل پیش‌فرض در صورت عدم یافتن

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        update = json.loads(post_data)

        if 'message' in update and 'document' in update['message']:
            chat_id = update['message']['chat']['id']
            document = update['message']['document']
            
            if document.get('file_name', '').endswith('.docx'):
                self.send_telegram_message(chat_id, "فایل دریافت شد. در حال پردازش هوشمند... ⏳")
                
                try:
                    # دانلود فایل
                    file_id = document['file_id']
                    file_info = requests.get(f"{TELEGRAM_URL}/getFile?file_id={file_id}").json()
                    file_path = file_info['result']['file_path']
                    download_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
                    file_content = requests.get(download_url).content
                    
                    # استخراج متن
                    doc = Document(BytesIO(file_content))
                    text = '\n'.join([para.text for para in doc.paragraphs if para.text.strip()])
                    
                    # انتخاب و اجرای مدل
                    model = get_best_model()
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
                    self.send_telegram_message(chat_id, response.text)
                    
                except Exception as e:
                    self.send_telegram_message(chat_id, f"❌ خطای پردازش:\n{str(e)}")
            else:
                self.send_telegram_message(chat_id, "⚠️ لطفاً فقط فایل ورد (docx.) ارسال کنید.")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def send_telegram_message(self, chat_id, text):
        try:
            requests.post(f"{TELEGRAM_URL}/sendMessage", json={"chat_id": chat_id, "text": text[:4000]})
        except Exception:
            pass
