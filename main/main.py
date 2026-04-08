import os
import re
import base64
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv


import database

load_dotenv()

app = FastAPI(title="CheckMe API")


database.init_db()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


VT_API_KEY = os.getenv("VT_API_KEY")

class UrlCheckRequest(BaseModel):
    url: str


URL_PATTERN = re.compile(
    r'^(https?:\/\/)?'
    r'(([a-z\d]([a-z\d-]*[a-z\d])*)\.)+[a-z]{2,}'
    r'(\/[-a-z\d%_.~+]*)*'
    r'(\?[;&a-z\d%_.~+=-]*)?'
    r'(\#[-a-z\d_]*)?$', re.IGNORECASE)

def translate_result(malicious_count):
  
    if malicious_count == 0:
        return {
            "status": "safe",
            "title": "✅ Посилання безпечне",
            "message": "Наші системи перевірили цей сайт. Він виглядає надійним, ви можете сміливо ним користуватися."
        }
    elif 1 <= malicious_count <= 3:
        return {
            "status": "warning",
            "title": "⚠️ Будьте обережні",
            "message": f"Декілька антивірусів ({malicious_count}) попередили про небезпеку. Ми рекомендуємо не вводити там свої паролі."
        }
    else:
        return {
            "status": "danger",
            "title": "❌ НЕБЕЗПЕЧНО!",
            "message": "Це посилання веде на шахрайський сайт. Обов'язково закрийте цю сторінку, щоб захистити свої дані!"
        }

@app.post("/check-url")
async def check_url(request: UrlCheckRequest):
    raw_url = request.url.strip()


    if not raw_url:
        raise HTTPException(status_code=400, detail="URL не вказано")

    if len(raw_url) > 2048:
        raise HTTPException(status_code=400, detail="Посилання занадто довге")

    if not URL_PATTERN.match(raw_url):
        return {
            "status": "warning",
            "title": "⚠️ Це не посилання",
            "message": "Будь ласка, введіть правильну адресу сайту (наприклад: google.com)."
        }


    full_url = raw_url
    if not full_url.startswith(('http://', 'https://')):
        full_url = 'https://' + full_url

    cached = database.get_cached_info(full_url)
    

    if cached and cached["check_count"] > 5:
        return {
            "status": cached["status"],
            "title": cached["title"],
            "message": cached["message"]
        }


    url_id = base64.urlsafe_b64encode(full_url.encode()).decode().strip("=")
    
    headers = {
        "x-apikey": VT_API_KEY,
        "accept": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://www.virustotal.com/api/v3/urls/{url_id}",
                headers=headers
            )
            

            if response.status_code == 200:
                data = response.json()
                stats = data['data']['attributes']['last_analysis_stats']
                malicious_count = stats['malicious']
                
                final_result = translate_result(malicious_count)
                

                database.save_or_update_cache(full_url, final_result)
                
                return final_result


            elif response.status_code == 404:
         
                if cached:
                    return {
                        "status": cached["status"],
                        "title": cached["title"],
                        "message": cached["message"]
                    }
                return {
                    "status": "warning",
                    "title": "Аналіз...",
                    "message": "Ми ще не бачили цього посилання. Зачекайте хвилину, ми вже почали його перевірку."
                }
            
            else:
        
                if cached:
                    return {"status": cached["status"], "title": cached["title"], "message": cached["message"]}
                raise HTTPException(status_code=response.status_code, detail="Помилка сервісу VirusTotal")

        except Exception as e:
          
            if cached:
                return {"status": cached["status"], "title": cached["title"], "message": cached["message"]}
            raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
 
    uvicorn.run(app, host="0.0.0.0", port=8080)
