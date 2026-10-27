import os
import time
import json
import html
import hashlib
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

API_URL = f"https://api.telegram.org/bot{TOKEN}/"
SEEN_JOBS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_jobs.json")

def load_seen_jobs():
    """Load previously seen job IDs from disk so we don't resend them on restart."""
    if os.path.exists(SEEN_JOBS_FILE):
        try:
            with open(SEEN_JOBS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            print(f"⚠️ Error reading seen_jobs.json: {e}")
    return set()

def save_seen_jobs(seen_jobs):
    """Save seen job IDs to disk."""
    try:
        with open(SEEN_JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(seen_jobs), f, indent=2)
    except Exception as e:
        print(f"⚠️ Error saving seen_jobs.json: {e}")

seen_jobs = load_seen_jobs()
print(f"📂 Loaded {len(seen_jobs)} previously seen jobs from cache.")

def get_updates(offset=None):
    """Fetch updates from Telegram with timeout."""
    url = API_URL + "getUpdates"
    params = {"timeout": 5, "offset": offset}
    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            return res.json()
        else:
            print(f"⚠️ Telegram getUpdates error ({res.status_code}): {res.text}")
            return None
    except Exception as e:
        return None

def send_job_message(job):
    """Send job details to Telegram with safe HTML and safe callback_data (<= 64 bytes)."""
    url = API_URL + "sendMessage"
    
    # Telegram callback_data limit is 64 bytes.
    # Long titles/company names easily exceed 64 bytes. Use short MD5 hash instead:
    short_hash = hashlib.md5(job['id'].encode('utf-8')).hexdigest()[:16]
    callback_data = f"dec_{short_hash}"
    
    # Ensure URL is valid
    apply_url = job.get('link') or "https://google.com"
    if not apply_url.startswith("http://") and not apply_url.startswith("https://"):
        apply_url = "https://" + apply_url

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ Apply", "url": apply_url},
                {"text": "❌ Decline", "callback_data": callback_data}
            ]
        ]
    }
    
    # Telegram HTML mode requires escaping special characters (&, <, >)
    safe_title = html.escape(str(job.get('title', 'No Title')))
    safe_company = html.escape(str(job.get('company', 'No Company')))
    safe_location = html.escape(str(job.get('location', 'India')))
    
    text = (
        f"🧪 <b>New Job Found!</b>\n\n"
        f"<b>Role:</b> {safe_title}\n"
        f"<b>Company:</b> {safe_company}\n"
        f"<b>Location:</b> {safe_location}"
    )
    
    try:
        res = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": reply_markup
        }, timeout=10)
        
        result_json = res.json()
        if result_json.get("ok"):
            return True
        else:
            print(f"❌ Telegram API rejected message: {result_json.get('description')}")
            return False
    except Exception as e:
        print(f"❌ Network error sending message to Telegram: {e}")
        return False

def gray_out_message(message_id, original_text):
    """Edit message to declined state."""
    url = API_URL + "editMessageText"
    safe_text = html.escape(original_text)
    try:
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "message_id": message_id,
            "text": f"🚫 <b>Declined</b>\n<blockquote>{safe_text}</blockquote>",
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print(f"⚠️ Error graying out message: {e}")

def fetch_jobs():
    """Fetch jobs from SerpAPI and send any newly found ones."""
    print(f"\n🔍 [{time.strftime('%Y-%m-%d %H:%M:%S')}] Checking Google Jobs via SerpAPI...")
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_jobs",
        "q": "Chemical Engineer",
        "location": "India",
        "api_key": SERPAPI_KEY
    }
    
    try:
        res = requests.get(url, params=params, timeout=25)
        data = res.json()
        
        if "error" in data:
            print(f"❌ SerpAPI Error: {data['error']}")
            return
            
        if "jobs_results" in data:
            new_jobs_count = 0
            jobs = data["jobs_results"]
            print(f"📋 Found {len(jobs)} total jobs on Google Jobs.")
            
            for job_data in jobs:
                title = job_data.get("title", "No Title")
                company = job_data.get("company_name", "No Company")
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
                    
                    sent = send_job_message(job)
                    if sent:
                        seen_jobs.add(unique_id)
                        new_jobs_count += 1
                        time.sleep(1) # brief delay to avoid Telegram rate limits
                        
            save_seen_jobs(seen_jobs)
            if new_jobs_count > 0:
                print(f"✅ Successfully sent {new_jobs_count} new job(s) to Telegram!")
            else:
                print("ℹ️ No new jobs found in this search (all returned jobs were already sent earlier).")
        else:
            print("⚠️ No 'jobs_results' field found in SerpAPI response.")
    except Exception as e:
        print(f"❌ Error fetching jobs: {e}")

# Optional test message on startup
test_job = {
    "id": "test_bot_online",
    "title": "Agent Online Test (Chemical Engineer)",
    "company": "System Check",
    "location": "Kerala, India",
    "link": "https://google.com"
}

# Run first check immediately
print("🚀 Starting Job Agent...")
fetch_jobs()

print("\n📡 Listening for button clicks and scheduled checks...")
last_update_id = None

# Check for jobs every 4 hours (14400 seconds) to avoid burning the 250/month SerpAPI quota
CHECK_INTERVAL_SECONDS = 4 * 3600  # 4 hours = ~6 checks/day = ~180 checks/month (within 250 free limit)

while True:
    end_time = time.time() + CHECK_INTERVAL_SECONDS
    while time.time() < end_time:
        try:
            updates = get_updates(last_update_id)
            if updates and "result" in updates:
                for update in updates["result"]:
                    last_update_id = update["update_id"] + 1
                    if "callback_query" in update:
                        callback = update["callback_query"]
                        data = callback.get("data", "")
                        
                        # Stop spinner instantly
                        try:
                            requests.get(
                                API_URL + f"answerCallbackQuery?callback_query_id={callback['id']}",
                                timeout=5
                            )
                        except Exception:
                            pass
                            
                        # Handle decline button
                        if data.startswith("dec_"):
                            msg = callback.get("message")
                            if msg:
                                message_id = msg.get("message_id")
                                original_text = msg.get("text", "Job")
                                gray_out_message(message_id, original_text)
                                print("🚫 You declined a job.")
            time.sleep(1)
        except Exception as loop_err:
            print(f"⚠️ Loop warning: {loop_err}")
            time.sleep(5)
            
    # When interval expires, fetch jobs again
    fetch_jobs()

