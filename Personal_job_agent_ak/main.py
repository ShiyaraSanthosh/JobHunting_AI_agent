import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

API_URL = f"https://api.telegram.org/bot{TOKEN}/"
seen_jobs = set()

def get_updates(offset=None):
    url = API_URL + "getUpdates"
    params = {"timeout": 5, "offset": offset}
    try:
        # Timeout add cheythu, so hang aavilla!
        return requests.get(url, params=params, timeout=10).json()
    except:
        return None

def send_job_message(job):
    url = API_URL + "sendMessage"
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ Apply", "url": job['link']},
                {"text": "❌ Decline", "callback_data": f"decline_{job['id']}"}
            ]
        ]
    }
    text = f"🧪 <b>New Job Found!</b>\n\n<b>Role:</b> {job['title']}\n<b>Company:</b> {job['company']}\n<b>Location:</b> {job['location']}"
    
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": reply_markup
    })

def gray_out_message(message_id, original_text):
    url = API_URL + "editMessageText"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "message_id": message_id,
        "text": f"🚫 <b>Declined</b>\n<blockquote>{original_text}</blockquote>",
        "parse_mode": "HTML"
    })

def fetch_jobs():
    print("🔍 Checking Google for jobs...")
    url = "https://serpapi.com/search.json"
    params = {"engine": "google_jobs", "q": "Chemical Engineer", "location": "India", "api_key": SERPAPI_KEY}
    try:
        data = requests.get(url, params=params).json()
        if "jobs_results" in data:
            # 15 jobs edukkkunnu!
            for job_data in data["jobs_results"][:15]:
                title = job_data.get("title", "No Title")
                company = job_data.get("company_name", "No Company")
                
                # Job ID kku pakaram Title + Company unique ID aayi edukkkunnu
                unique_id = f"{title}_{company}"
                
                if unique_id not in seen_jobs:
                    apply_links = job_data.get("apply_options", [])
                    link = apply_links[0]["link"] if apply_links else "https://google.com"
                    job = {
                        "id": unique_id,
                        "title": title,
                        "company": company,
                        "location": job_data.get("location", "India"),
                        "link": link
                    }
                    send_job_message(job)
                    seen_jobs.add(unique_id)
    except Exception as e:
        print("Error fetching jobs:", e)

# TEST JOB 
test_job = {
    "id": "test_123",
    "title": "Dummy Chemical Engineer (TEST)",
    "company": "Test Company",
    "location": "Kerala",
    "link": "https://google.com"
}
send_job_message(test_job)
print("📱 Sent a TEST JOB to your phone! Check the new Decline Button!")

print("🚀 24/7 Agent is LIVE! Listening for jobs and button clicks...")
last_update_id = None

while True:
    fetch_jobs()
    end_time = time.time() + 3600 
    while time.time() < end_time:
        updates = get_updates(last_update_id)
        if updates and "result" in updates:
            for update in updates["result"]:
                last_update_id = update["update_id"] + 1
                if "callback_query" in update:
                    callback = update["callback_query"]
                    data = callback.get("data", "")
                    message_id = callback["message"]["message_id"]
                    
                    # 1. Stop animation INSTANTLY
                    requests.get(API_URL + f"answerCallbackQuery?callback_query_id={callback['id']}")
                    
                    # 2. Disable message
                    if data.startswith("decline"):
                        original_text = callback["message"].get("text", "Job")
                        gray_out_message(message_id, original_text)
                        print("🚫 You declined a job.")
