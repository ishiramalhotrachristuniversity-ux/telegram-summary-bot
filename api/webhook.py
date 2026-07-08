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
                    
                    # اصلاح پرامپت برای حفظ لحن روایی متن اصلی و حذف نام اشخاص
                    prompt = (
                        "گزارش زیر را تحلیل کن و یک خلاصه در قالب فایل ورد با فرمت زیر ارائه بده. "
                        "مهم: در تمام بخش‌ها، لحن روایی، شاعرانه و توصیفیِ خودِ گزارش را حفظ کن اما نام هیچ شخصی را ذکر نکن:\n\n"
                        "نام رویداد: [عنوان دقیق رویداد]\n"
                        "خلاصه رویداد: [یک پاراگرافِ فشرده که با همان لحنِ ادبی و توصیفیِ متن اصلی، جزئیاتِ کلیدی را روایت کند]\n"
                        "ارزش محوری: [جمله‌ای با همان لحن درباره ارزشِ عمیق و نهفته در این رویداد]\n\n"
                        f"متن گزارش:\n{text}"
                    )
                    
                    response = model.generate_content(prompt)
                    
                    new_doc = Document()
                    new_doc.add_paragraph(response.text)
                    
                    output = BytesIO()
                    new_doc.save(output)
                    output.seek(0)
                    
                    files = {'document': ('Report_Summary.docx', output, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')}
                    requests.post(f"{TELEGRAM_URL}/sendDocument", data={'chat_id': chat_id}, files=files)
                    
                except Exception as e:
                    requests.post(f"{TELEGRAM_URL}/sendMessage", json={"chat_id": chat_id, "text": f"خطا: {str(e)}"})
            
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
