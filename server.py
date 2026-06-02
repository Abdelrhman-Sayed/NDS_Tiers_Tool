import os
import json
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.error

# الـ Key بتتاخد من Railway Environment Variables
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Gemini API endpoint
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

class Handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        if self.path == "/api/search":
            # 1. اقرأ الـ request الجاي من المتصفح
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)

            query   = data.get("query", "")
            filters = data.get("filters", {})

            # 2. جهز الـ prompt
            prompt = f"""أنت خبير في سوق الكاوتش (الإطارات) في مصر.
رد فقط بـ JSON array بدون أي نص زيادة أو backticks أو markdown.

كل عنصر في الـ array يحتوي على:
{{
  "brand": "الماركة",
  "model": "الموديل",
  "size": "مثال: 205/55R16",
  "price_min": رقم بالجنيه,
  "price_max": رقم بالجنيه,
  "price_avg": رقم بالجنيه,
  "cities": ["القاهرة", "الإسكندرية"],
  "is_bestseller": true أو false,
  "car_type": "نوع السيارة",
  "features": ["ميزة1", "ميزة2"],
  "origin": "بلد الصنع",
  "notes": "ملاحظة مفيدة"
}}

ابحث عن: {query}
فلاتر: {json.dumps(filters, ensure_ascii=False)}

أرجع 6 إلى 10 نتايج واقعية بأسعار السوق المصري 2024-2025. JSON فقط بدون أي كلام تاني."""

            # 3. كلم Gemini API
            payload = json.dumps({
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 3000
                }
            }).encode()

            url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"}
            )

            try:
                with urllib.request.urlopen(req) as resp:
                    result = json.loads(resp.read())

                    # استخرج النص من رد Gemini
                    text = result["candidates"][0]["content"]["parts"][0]["text"]

                    # نظف الـ JSON لو فيه backticks
                    text = re.sub(r'```json|```', '', text).strip()

                    # استخرج الـ array
                    match = re.search(r'\[[\s\S]*\]', text)
                    items = json.loads(match.group()) if match else []

                    # فلتر السعر لو موجود
                    max_price = filters.get("maxPrice")
                    if max_price:
                        items = [i for i in items if i.get("price_min", 0) <= int(max_price)]

                    self._respond(200, {"results": items})

            except urllib.error.HTTPError as e:
                error_body = e.read().decode()
                self._respond(500, {"error": f"Gemini API Error {e.code}: {error_body}"})
            except Exception as e:
                self._respond(500, {"error": str(e)})
        else:
            self._respond(404, {"error": "Not found"})

    def _respond(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}")


if __name__ == "__main__":
    port = 8000
    if not GEMINI_API_KEY:
        print("⚠️  تحذير: GEMINI_API_KEY مش موجودة!")
        print("   حطها في Railway Variables أو اكتبها في الكود مؤقتاً للتجربة")
    print(f"✅ السيرفر شغال على http://localhost:{port}")
    print(f"   افتح الملف index.html في المتصفح")
    print(f"   اضغط Ctrl+C لتوقيف السيرفر\n")
    HTTPServer(("localhost", port), Handler).serve_forever()
