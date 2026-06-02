import os
import json
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.error

# API Key comes from environment variable (set it in Railway dashboard)
API_KEY = os.environ.get("GEMINI_API_KEY")

class Handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok", "message": "Server is running"})
        else:
            self._respond(200, {"status": "ok"})

    def do_POST(self):
        if self.path == "/api/search":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)

            query = data.get("query", "")
            filters = data.get("filters", {})

            system_prompt = """أنت خبير في سوق الكاوتش في مصر. رد فقط بـ JSON array بدون أي نص زيادة.
كل عنصر في الـ array يحتوي على:
{
  "brand": "الماركة",
  "model": "الموديل",
  "size": "مثال: 205/55R16",
  "price_min": رقم,
  "price_max": رقم,
  "price_avg": رقم,
  "cities": ["القاهرة","الإسكندرية"],
  "is_bestseller": true أو false,
  "car_type": "نوع السيارة",
  "features": ["ميزة1","ميزة2"],
  "origin": "بلد الصنع",
  "notes": "ملاحظة"
}
أرجع 6 إلى 10 نتايج واقعية بأسعار السوق المصري 2024-2025."""

            user_msg = f"ابحث عن: {query}\nفلاتر: {json.dumps(filters, ensure_ascii=False)}"

            payload = json.dumps({
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 3000,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_msg}]
            }).encode()

            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": API_KEY,
                    "anthropic-version": "2023-06-01"
                }
            )

            try:
                with urllib.request.urlopen(req) as resp:
                    result = json.loads(resp.read())
                    text = result["content"][0]["text"]
                    match = re.search(r'\[[\s\S]*\]', text)
                    items = json.loads(match.group()) if match else []

                    max_price = filters.get("maxPrice")
                    if max_price:
                        items = [i for i in items if i.get("price_min", 0) <= int(max_price)]

                    self._respond(200, {"results": items})

            except urllib.error.HTTPError as e:
                self._respond(500, {"error": f"API Error: {e.code}"})
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
    # Railway gives us a PORT env variable — must use it
    port = int(os.environ.get("PORT", 8000))
    print(f"✅ Server running on port {port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
