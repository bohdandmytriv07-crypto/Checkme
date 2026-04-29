import os
import re
import base64
import httpx
import time
from pathlib import Path
from difflib import SequenceMatcher
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles 
from pydantic import BaseModel
from dotenv import load_dotenv
import database


env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

app = FastAPI()


database.init_db()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

VT_API_KEY = os.getenv("VT_API_KEY")
user_requests = {}

TRUSTED_BRANDS = [
    "google", "facebook", "instagram", "privat24", "monobank", 
    "ukr.net", "diia.gov.ua", "gmail", "youtube", "rozetka", "olx"
]

class UrlCheckRequest(BaseModel):
    url: str

URL_PATTERN = re.compile(
    r'^(https?:\/\/)?'
    r'(([a-z\d]([a-z\d-]*[a-z\d])*)\.)+[a-z]{2,}'
    r'(\/[-a-z\d%_.~+]*)*'
    r'(\?[;&a-z\d%_.~+=-]*)?'
    r'(\#[-a-z\d_]*)?$', re.IGNORECASE)

def check_typosquatting(domain):
    domain_name = domain.split('.')[0].lower()
    for brand in TRUSTED_BRANDS:
        if domain_name == brand:
            return None
        similarity = SequenceMatcher(None, domain_name, brand).ratio()
        if 0.7 < similarity < 1.0:
            return brand
    return None

def get_detailed_reason(analysis_results):
    all_detects = []
    for engine, result in analysis_results.items():
        if result.get('result'):
            all_detects.append(result['result'].lower())
    full_text = " ".join(all_detects)
    if any(word in full_text for word in ['phish', 'social engineering', 'fake', 'scam']):
        return "це сайт-пастка, який намагається вкрасти ваші паролі або дані картки"
    if any(word in full_text for word in ['malware', 'trojan', 'virus', 'spyware']):
        return "на цьому сайті є віруси, які можуть пошкодити ваш пристрій"
    if any(word in full_text for word in ['adware', 'advertising', 'pop-up']):
        return "тут занадто багато нав'язливої реклами та вікон, що заважають"
    return "наші системи помітили підозрілу активність, краще не ризикувати"

def translate_result(malicious_count, analysis_results, is_https, suspicious_brand=None):
    if suspicious_brand:
        return {
            "status": "danger",
            "title": "❌ ОБЕРЕЖНО, ПІДРОБКА!",
            "message": f"Ця адреса дуже схожа на справжній сайт {suspicious_brand.capitalize()}, але має помилки. Це популярний трюк шахраїв!"
        }
    
    if malicious_count == 0:
        if not is_https:
            return {
                "status": "warning",
                "title": "⚠️ Будьте обережні",
                "message": "Сайт ніби чистий, але він використовує старий метод захисту. Не вводіть там жодних паролів."
            }
        return {
            "status": "safe",
            "title": "✅ Все добре!",
            "message": "Цей сайт безпечний та має сучасний захист. Можете ним користуватися."
        }
    
    reason = get_detailed_reason(analysis_results)
    if 1 <= malicious_count <= 3:
        return {
            "status": "warning",
            "title": "⚠️ Небезпечне місце",
            "message": f"Сайт не зовсім надійний: {reason}. Ми радимо його закрити."
        }
    else:
        return {
            "status": "danger",
            "title": "❌ КАТЕГОРИЧНО НЕ МОЖНА!",
            "message": f"УВАГА: {reason.upper()}! Це шахраї. Терміново закрийте сторінку."
        }



@app.get("/history")
async def get_history():
    return database.get_recent_history(10)

@app.post("/check-url")
async def check_url(request_data: UrlCheckRequest, request: Request):
    client_ip = request.client.host
    current_time = time.time()

    if client_ip in user_requests:
        if current_time - user_requests[client_ip] < 15:
            wait_time = int(15 - (current_time - user_requests[client_ip]))
            return {
                "status": "warning", "title": "⏳ Зачекайте",
                "message": f"Спробуйте ще раз через {wait_time} сек."
            }

    raw_url = request_data.url.strip()
    if not VT_API_KEY: raise HTTPException(status_code=500, detail="API key missing")
    if not raw_url: raise HTTPException(status_code=400, detail="URL missing")
    if not URL_PATTERN.match(raw_url):
        return {"status": "warning", "title": "⚠️ Це не посилання", "message": "Введіть правильну адресу."}

    user_requests[client_ip] = current_time
    
    full_url = raw_url if raw_url.startswith(('http://', 'https://')) else 'https://' + raw_url
    domain = full_url.replace("https://", "").replace("http://", "").split('/')[0].replace("www.", "")
    
    suspicious_brand = check_typosquatting(domain)
    is_https = full_url.startswith('https://')
    cached = database.get_cached_info(full_url)
    
    if cached and cached.get("check_count", 0) > 5:
        return cached

    url_id = base64.urlsafe_b64encode(full_url.encode()).decode().strip("=")
    headers = {"x-apikey": VT_API_KEY, "accept": "application/json"}

    async with httpx.AsyncClient(verify=False) as client:
        try:
            response = await client.get(f"https://www.virustotal.com/api/v3/urls/{url_id}", headers=headers)
            if response.status_code == 200:
                attr = response.json()['data']['attributes']
                res = translate_result(attr['last_analysis_stats']['malicious'], attr['last_analysis_results'], is_https, suspicious_brand)
                database.save_or_update_cache(full_url, res)
                return res
            elif response.status_code == 404:
                if suspicious_brand:
                    return translate_result(0, {}, is_https, suspicious_brand)
                return {"status": "warning", "title": "Аналіз...", "message": "Сайт ще не перевірявся. Зачекайте хвилину."}
            else:
                raise HTTPException(status_code=response.status_code, detail="VT Error")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

!
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
  
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)