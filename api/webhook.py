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
    """یافتن هوشمند مدل برای جلوگیری از خطای 404"""
    models = genai.list_models()
    for m in models:
        if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name:
            return genai.GenerativeModel(m.name)
    return genai.GenerativeModel('gemini-pro')

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        update = json.loads(post_data)

        if 'message' in update and 'document' in update['message']:
            chat_id = update['message']['chat']['id']
            document = update['message']['document']
            
            if document.get('file_name', '').endswith('.docx'):
                self.send_telegram_message(chat_id, "در حال بازنویسی با قلم شیوا عاشوری... ✍️")
                
                try:
                    # دانلود و استخراج متن
                    file_id = document['file_id']
                    file_info = requests.get(f"{TELEGRAM_URL}/getFile?file_id={file_id}").json()
                    file_path = file_info['result']['file_path']
                    download_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
                    file_content = requests.get(download_url).content
                    
                    doc = Document(BytesIO(file_content))
                    text = '\n'.join([para.text for para in doc.paragraphs if para.text.strip()])
                    
                    # تحلیل با قلم شیوا
                    model = get_best_model()
                    prompt = (
                        "شما دستیار ارشدِ شیوا عاشوری هستید. گزارش زیر را تحلیل کرده و در قالب فایل ورد بازنویسی کنید.\n"
                        "لحن و قلم شما باید دقیقاً مطابق با سبک رواییِ شیوا باشد: توصیفی، شاعرانه، عمیق، و جامعه‌نگر.\n"
                        "از ترکیباتِ استعاری استفاده کنید، به احساساتِ انسانی در رویدادها بها بدهید و فضا را همانند یک تابلو نقاشیِ کلامی تصویر کنید.\n\n"
                        "ساختار گزارش ورد باید شامل موارد زیر باشد:\n"
                        "۱. شناسنامه رویداد (عنوان، مکان، تنظیم‌کننده)\n"
                        "۲. خلاصه مدیریتی (با قلمِ رواییِ شیوا - توصیفی و عمیق)\n"
                        "۳. ارزش محوری (تحلیلی و بنیادین)\n"
                        "۴. اقدام (خروجیِ کلیدی)\n\n"
                        f"متن اصلی گزارش:\n{text}"
                    )
                    
                    response = model.generate_content(prompt)
                    
                    # ایجاد فایل ورد
                    new_doc = Document()
                    new_doc.add_heading('گزارش تحلیلی با قلم شیوا', 0)
                    new_doc.add_paragraph(response.text)
                    
                    output = BytesIO()
                    new_doc.save(output)
                    output.seek(0)
                    
                    # ارسال فایل به تلگرام
                    files = {'document': ('Report_ShivaStyle.docx', output, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')}
                    requests.post(f"{TELEGRAM_URL}/sendDocument", data={'chat_id': chat_id}, files=files)
                    
                except Exception as e:
                    self.send_telegram_message(chat_id, f"❌ خطا در پردازش: {str(e)}")
            
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def send_telegram_message(self, chat_id, text):
        try:
            requests.post(f"{TELEGRAM_URL}/sendMessage", json={"chat_id": chat_id, "text": text})
        except Exception:
            pass
