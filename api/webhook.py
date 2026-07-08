from http.server import BaseHTTPRequestHandler
import os
import json
import requests
import google.generativeai as genai
from io import BytesIO
from docx import Document

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def get_best_model():
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
                try:
                    file_id = document['file_id']
                    file_info = requests.get(f"{TELEGRAM_URL}/getFile?file_id={file_id}").json()
                    file_path = file_info['result']['file_path']
                    download_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
                    file_content = requests.get(download_url).content
                    
                    doc = Document(BytesIO(file_content))
                    text = '\n'.join([para.text for para in doc.paragraphs if para.text.strip()])
                    
                    model = get_best_model()
                    
                    # پرامپت اصلاح‌شده برای استخراج دقیق ساختار
                    prompt = (
                        "گزارش زیر را در قالب یک فایل ورد با فرمت دقیق زیر خلاصه کن.\n\n"
                        "قوانین اجباری:\n"
                        "1. نام رویداد را دقیقاً از متن استخراج کن.\n"
                        "2. اگر تاریخ رویداد در متن وجود داشت، همان را دقیقاً استخراج کن و روبروی بخش تاریخ رویداد بنویس.\n"
                        "3. کل بخش «خلاصه رویداد» باید بین 5 تا 7 خط باشد.\n"
                        "4. لحن روایی گزارش حفظ شود.\n"
                        "5. چیزی از خودت اضافه نکن و فقط از اطلاعات موجود در متن استفاده کن.\n\n"
                        "فرمت خروجی (دقیقاً به همین شکل شروع شود):\n"
                        "نام رویداد: [عنوان دقیق رویداد]\n"
                        "تاریخ رویداد: [تاریخ رویداد یا عبارت ذکر نشده]\n"
                        "خلاصه رویداد:\n"
                        "[خلاصه‌ای توصیفی و روایی در 5 تا 7 خط]\n\n"
                        "ارزش محوری: [یک جمله کوتاه]\n\n"
                        f"متن گزارش:\n{text}"
                    )
                    
                    response = model.generate_content(prompt)
                    response_text = response.text
                    
                    # استخراج نام رویداد از پاسخ برای نام‌گذاری فایل
                    file_name = "خلاصه_رویداد.docx"
                    for line in response_text.split('\n'):
                        if "نام رویداد:" in line:
                            extracted_name = line.replace("نام رویداد:", "").strip()
                            if extracted_name:
                                # حذف کاراکترهای غیرمجاز برای نام فایل در سیستم عامل
                                invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
                                for char in invalid_chars:
                                    extracted_name = extracted_name.replace(char, '')
                                file_name = f"{extracted_name}.docx"
                            break
                    
                    new_doc = Document()
                    new_doc.add_paragraph(response_text)
                    
                    output = BytesIO()
                    new_doc.save(output)
                    output.seek(0)
                    
                    # ارسال فایل با نام اختصاصی رویداد
                    files = {'document': (file_name, output, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')}
                    requests.post(f"{TELEGRAM_URL}/sendDocument", data={'chat_id': chat_id}, files=files)
                    
                except Exception as e:
                    requests.post(f"{TELEGRAM_URL}/sendMessage", json={"chat_id": chat_id, "text": f"خطا: {str(e)}"})
            
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
