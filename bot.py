"""
Sidhu Sir's Ultimate Multi-Channel AI Bot (Two-Part UPSC/MPSC Cards + Distinct Line Statements)
================================================================================================
Features:
1. 🏛️ Two-Part Card + Poll Strategy for UPSC & MPSC Rajyaseva:
   - For long / analytical questions (> 250 chars or multi-statement questions):
     Part 1: Beautiful Rich Text Question Card with statements clearly separated ONE BELOW THE OTHER.
     Part 2: Clickable Native Telegram Quiz Poll immediately below with authentic options & confetti!
   - For short 1-liner questions: Posts directly as native quiz poll.
2. 📑 Distinct Statement Formatting:
   - Statements (अ), (ब), (क) and 1., 2., 3. are NEVER run-on or continuous.
   - Automatically formatted with double line breaks for maximum readability.
3. 🎯 UPSC vs MPSC Exact Numbering:
   - UPSC: Statements 1., 2., 3. | Options (a), (b), (c), (d)
   - MPSC राज्यसेवा: Statements (अ), (ब), (क) | Options १), २), ३), ४)
   - MPSC Combine: Statements (अ), (ब) | Options १), २), ३), ४)
   - पोलीस भरती: Direct 1-liner | Options १), २), ३), ४)
4. 🚀 Bulk Question Support (50, 100, or Custom Count up to 200) with Live Progress Tracker.
5. ⚡ Non-blocking Asynchronous Background Posting (Never freezes /start or uploads).
6. 📑 As-Is PYQ Extraction vs 🤖 AI Generate choice.
7. 🛠️ Question Management & Individual Option Editor Hub.
8. 🔙 Universal Back button navigation on EVERY step.
9. ♾️ Normal Quiz (Permanent open) vs ⏱️ Live Test (45s Timer).
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import io
import json
import logging
import os
import re
import threading
import time
import zipfile
import xml.etree.ElementTree as ET
import telebot
from telebot import types
import requests

# Graceful PDF support
try:
    import pypdf
except ImportError:
    pypdf = None

# ------------------------------------------------------------------------------
# 0. FREE CLOUD KEEP-ALIVE SERVER (For Render Web Service)
# ------------------------------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive 24/7!")

    def log_message(self, format, *args):
        pass

def run_health_server():
    server = HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 8080))), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

# ------------------------------------------------------------------------------
# 1. CREDENTIALS & CHANNELS
# ------------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = "9253804253:AAG3NaTU704bmw00hznomU1NKgsl0g4JgvU"
GROQ_API_KEY = "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"

CHANNELS = {
    "upsc_polity": {"title": "🏛️ Polity (UPSC)", "id": "@polity_quiz_mcq", "sub": "Indian Polity & Constitution", "lang": "English", "lvl": "upsc"},
    "upsc_history": {"title": "📜 History (UPSC)", "id": "@history_quiz_mcq", "sub": "Indian History & Culture", "lang": "English", "lvl": "upsc"},
    "upsc_geo": {"title": "🌍 Geography (UPSC)", "id": "@geography_quiz_mcq", "sub": "Geography & Environment", "lang": "English", "lvl": "upsc"},
    "upsc_economy": {"title": "📈 Economy (UPSC)", "id": "@economy_quiz_mcq", "sub": "Economy & Budget", "lang": "English", "lvl": "upsc"},
    "upsc_env": {"title": "🌿 Environment (UPSC)", "id": "@environment_quiz_mcq", "sub": "Ecology & Wildlife", "lang": "English", "lvl": "upsc"},
    "upsc_sci": {"title": "🔬 Science & Tech (UPSC)", "id": "@science_quiz_mcq", "sub": "Science, Space & Tech", "lang": "English", "lvl": "upsc"},
    "mpsc_official": {"title": "🚩 Sidhu Sir Official (MPSC)", "id": "@sidhu_sir_official", "sub": "MPSC GS All Subjects", "lang": "Bilingual", "lvl": "combine"}
}

logging.basicConfig(level=logging.INFO)
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
user_sessions = {}
pending_posts = {}

# ------------------------------------------------------------------------------
# 2. BULLETPROOF GROQ AI ENGINE WITH ACTIVE 2026 REPLACEMENT MODELS
# ------------------------------------------------------------------------------
KNOWN_TEXT_MODELS = [
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
    "mixtral-8x7b-32768"
]

KNOWN_VISION_MODELS = [
    "qwen/qwen3.8-27b",
    "meta-llama/llama-4-scout-17b-16e-instruct"
]

def get_available_groq_models():
    headers = {"Authorization": f"Bearer {GROQ_API_KEY.strip()}"}
    try:
        r = requests.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=5)
        if r.status_code == 200:
            return [m["id"] for m in r.json().get("data", [])]
    except Exception:
        pass
    return []

def get_text_candidates():
    available = get_available_groq_models()
    candidates = []

    for m in KNOWN_TEXT_MODELS:
        if m in available and m not in candidates:
            candidates.append(m)

    for m in available:
        m_low = m.lower()
        if not any(bad in m_low for bad in ["whisper", "guard", "embed", "tts", "safeguard", "orpheus", "canopy"]):
            if m not in candidates:
                candidates.append(m)

    if not candidates:
        candidates = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b", "openai/gpt-oss-120b"]

    return candidates

def get_vision_model():
    available = get_available_groq_models()
    for m in KNOWN_VISION_MODELS:
        if m in available:
            return m
    for m in available:
        if any(v in m.lower() for v in ["qwen", "vision", "scout"]):
            return m
    return "qwen/qwen3.8-27b"

def ask_groq(prompt: str, json_mode: bool = False) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY.strip()}", "Content-Type": "application/json"}

    candidate_models = get_text_candidates()

    system_rules = (
        "You are an authoritative, senior exam paper setter for UPSC and MPSC examinations.\n"
        "STRICT FACTUAL & FORMATTING RULES (CRITICAL):\n"
        "1. Never hallucinate, confuse, or misattribute historical figures, leaders, or events.\n"
        "2. Indian Polity & Constitution Precision (Strict):\n"
        "   - 1895 Swaraj Bill (Constitution of India Bill, 1895): Was drafted under the inspiration and guidance of Lokmanya Bal Gangadhar Tilak ('लोकमान्य बाळ गंगाधर टिळक यांच्या प्रेरणेने / मार्गदर्शनाखाली तयार केले गेले'). NEVER write that Tilak 'सादर केले' (presented/introduced) it, as it was not introduced in any legislature. The correct question phrasing MUST BE: '१८९५ चे स्वराज्य विधेयक (Swaraj Bill) कोणाच्या प्रेरणेने/मार्गदर्शनाखाली तयार करण्यात आले होते?'.\n"
        "   - 1934: M.N. Roy first put forward the idea of a Constituent Assembly.\n"
        "   - 1935: INC officially demanded a Constituent Assembly.\n"
        "   - 1938: Pt. Jawaharlal Nehru declared that the Constitution must be framed by a Constituent Assembly elected on adult franchise.\n"
        "   - 1940: August Offer accepted the demand in principle.\n"
        "   - 1946: Constituent Assembly constituted under the Cabinet Mission Plan.\n"
        "   - 13 Dec 1946: Objectives Resolution moved by Nehru (passed 22 Jan 1947).\n"
        "3. Maharashtra & Modern Indian History:\n"
        "   - Mahad Satyagraha (20 March 1927, Chavdar Tale), Kalaram Temple Satyagraha (1930), Bahishkrit Hitakarini Sabha (1924), Mooknayak, and Manusmriti Dahan (25 Dec 1927) are strictly Dr. B.R. Ambedkar (NOT Mahatma Gandhi).\n"
        "   - Satyashodhak Samaj: Mahatma Jyotirao Phule (1873).\n"
        "   - Rajarshi Chhatrapati Shahu Maharaj: Kolhapur 50% reservation (1902), primary education act (1917), Satya Shodhak support, Vedokta.\n"
        "   - Salt Satyagraha / Dandi March (1930), Champaran (1917), Kheda (1918), Non-Cooperation (1920), Quit India (1942) are Mahatma Gandhi.\n"
        "4. Strict Statement Formatting (One below the other):\n"
        "   - Statements in multi-statement questions MUST be separated by a clean newline so each statement appears on its own line one below the other!\n"
        "   - NEVER write statements continuously on the same line (e.g. NEVER write '1. ... 2. ...' on one line).\n"
        "5. Separation of Question & Options:\n"
        "   - NEVER include option labels (A), (B), (C), (D) or option values inside the question text itself!\n"
        "   - The 'question' field MUST contain only the question sentence and statements.\n"
        "   - The 'options' list MUST contain the 4 distinct choices.\n"
        "6. Length limits:\n"
        "   - each option under 90 characters.\n"
        "   - 'explanation' under 140 characters.\n"
    )

    last_error = ""
    for model_name in candidate_models:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_rules},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 4096
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=45)
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                if content and content.strip():
                    return content
                last_error = f"Empty content from {model_name}"
            else:
                last_error = f"AI Error ({model_name}): {resp.status_code} {resp.text}"
                continue
        except Exception as e:
            last_error = str(e)
            continue

    raise Exception(last_error or "AI Generation failed.")

def format_statements_cleanly(text: str) -> str:
    """Formats statements (अ, ब, क or 1, 2, 3) cleanly one below the other with spacing."""
    t = text.strip()
    t = re.sub(r"\s*(\([अ-हa-dA-D]\))\s*", r"\n\n\1 ", t)
    t = re.sub(r"\s*(\b[1-4]\.)\s*", r"\n\n\1 ", t)
    t = re.sub(r"\s*(Statement[- ][I|V|X\d]+[:\.])\s*", r"\n\n\1 ", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*(खालीलपैकी|Which of the statements|वरीलपैकी|Select the correct)\s*", r"\n\n\1 ", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t

def parse_plain_text_mcqs(text: str) -> list:
    mcqs = []
    blocks = re.split(r"(?:\n\s*|\A)(?:Q\s*\d+[\.:]|\d+[\.:])\s*", text)
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        opts = re.findall(r"(?:[A-Da-d][\.\)]|[\(][A-Da-d][\)]|[१-४1-4][\.\)])\s*(.+?)(?=(?:[A-Da-d][\.\)]|[\(][A-Da-d][\)]|[१-४1-4][\.\)]|उत्तर|Ans|Explanation|स्पष्टीकरण|\Z))", b, re.DOTALL)
        if len(opts) >= 4:
            q_lines = b.split("\n")[0].strip()
            clean_opts = [o.strip()[:90] for o in opts[:4]]
            ans_match = re.search(r"(?:उत्तर|Ans|Correct)\s*[:\-]?\s*([A-Da-d१-४1-4])", b)
            corr_idx = 0
            if ans_match:
                ch = ans_match.group(1)
                if ch in "1234":
                    corr_idx = int(ch) - 1
                elif ch in "१२३४":
                    corr_idx = "१२३४".index(ch)
                elif ch.upper() in "ABCD":
                    corr_idx = ord(ch.upper()) - ord("A")
            exp_match = re.search(r"(?:स्पष्टीकरण|Explanation)\s*[:\-]?\s*(.+)", b, re.DOTALL)
            exp = exp_match.group(1).strip()[:140] if exp_match else "संदर्भ नोट्सनुसार अचूक उत्तर."
            mcqs.append({
                "question": q_lines,
                "options": clean_opts,
                "correct_option_id": corr_idx if 0 <= corr_idx <= 3 else 0,
                "explanation": exp
            })
    return mcqs

def parse_json_mcqs(text: str) -> list:
    if not text:
        raise Exception("AI कडून रिकामे उत्तर आले.")

    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE).strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ["questions", "mcqs", "quiz", "data"]:
                if key in data and isinstance(data[key], list):
                    return data[key]
            if "question" in data and "options" in data:
                return [data]
    except Exception:
        pass

    arr_match = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
    if arr_match:
        try:
            data = json.loads(arr_match.group(0))
            if isinstance(data, list):
                return data
        except Exception:
            pass

    obj_match = re.search(r"\{\s*\"(?:questions|mcqs|data|question)\".*\}", text, re.DOTALL)
    if obj_match:
        try:
            data = json.loads(obj_match.group(0))
            for key in ["questions", "mcqs", "quiz", "data"]:
                if key in data and isinstance(data[key], list):
                    return data[key]
            if "question" in data:
                return [data]
        except Exception:
            pass

    parsed = parse_plain_text_mcqs(text)
    if parsed:
        return parsed

    raise Exception(f"AI उत्तरामधून प्रश्न काढता आले नाहीत. कृपया पुन्हा प्रयत्न करा.")

# ------------------------------------------------------------------------------
# 3. INPUT HANDLERS: TEXT, PHOTO, PDF, WORD DOC & MANUAL EDIT
# ------------------------------------------------------------------------------
@bot.message_handler(commands=['start', 'help'])
def start_cmd(msg):
    user_sessions[msg.chat.id] = {}  # Clean reset on /start
    text = (
        "🚀 *Sidhu Sir's Ultimate Quiz & Content Bot Active!*\n\n"
        "✨ **तुम्ही काय पाठवू शकता?**\n"
        "1. 📝 **विषयाचे नाव** थेट टाईप करा (उदा. `राज्यघटनेची निर्मिती` किंवा `महाड सत्याग्रह`).\n"
        "2. 📸 **पुस्तकाचा फोटो** काढून पाठवा (AI पान वाचून अचूक प्रश्न काढेल).\n"
        "3. 📄 **नोट्सची PDF** पाठवा (AI पानांमधील मजकूर वाचून प्रश्न बनवेल).\n"
        "4. 📑 **Word फाईल (.docx)** पाठवा (AI नोट्स वाचून त्वरित प्रश्न संच बनवेल).\n\n"
        "👉 **सुरुवात करण्यासाठी:** खाली मेसेज, फोटो, PDF किंवा Word फाईल पाठवा!"
    )
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

# 1. Text Input, Custom Count & Advanced Option Edit Handler
@bot.message_handler(func=lambda m: True, content_types=['text'])
def handle_text(msg):
    topic = msg.text.strip()
    if not topic or topic.startswith('/'):
        return

    sess = user_sessions.get(msg.chat.id, {})

    # Check if user is typing custom question count
    if "waiting_custom_cnt" in sess:
        mid = sess.pop("waiting_custom_cnt")
        digits = re.findall(r"\d+", topic)
        if digits:
            val = int(digits[0])
            val = max(1, min(val, 200))
            sess["cnt"] = val
            bot.reply_to(msg, f"🎯 **प्रश्नांची संख्या निश्चित केली:** `{val} प्रश्न`")
            show_timer_menu(msg.chat.id, mid)
            return
        else:
            bot.reply_to(msg, "कृपया योग्य संख्या टाईप करा (उदा. 40, 75, 100).")
            return

    # Check if user is editing a question
    if "editing" in sess:
        edit_info = sess.pop("editing")
        post_id = edit_info["post_id"]
        q_idx = edit_info["q_idx"]
        target = edit_info.get("target", "auto")
        mid = edit_info["mid"]

        if post_id in pending_posts and pending_posts[post_id]["type"] == "quiz":
            quizzes = pending_posts[post_id]["data"]
            if q_idx < len(quizzes):
                q_item = quizzes[q_idx]

                if target == "q":
                    q_item["question"] = topic
                    bot.reply_to(msg, f"✅ **Q{q_idx+1} चा प्रश्न बदलला!**", parse_mode="Markdown")
                elif target == "opt0":
                    q_item["options"][0] = topic[:90]
                    bot.reply_to(msg, f"✅ **Q{q_idx+1} चा पर्याय १ बदलला:** `{topic[:90]}`", parse_mode="Markdown")
                elif target == "opt1":
                    q_item["options"][1] = topic[:90]
                    bot.reply_to(msg, f"✅ **Q{q_idx+1} चा पर्याय २ बदलला:** `{topic[:90]}`", parse_mode="Markdown")
                elif target == "opt2":
                    q_item["options"][2] = topic[:90]
                    bot.reply_to(msg, f"✅ **Q{q_idx+1} चा पर्याय ३ बदलला:** `{topic[:90]}`", parse_mode="Markdown")
                elif target == "opt3":
                    q_item["options"][3] = topic[:90]
                    bot.reply_to(msg, f"✅ **Q{q_idx+1} चा पर्याय ४ बदलला:** `{topic[:90]}`", parse_mode="Markdown")
                elif target == "exp":
                    q_item["explanation"] = topic[:140]
                    bot.reply_to(msg, f"✅ **Q{q_idx+1} चे स्पष्टीकरण बदलले!**", parse_mode="Markdown")
                else:
                    arrow_match = re.search(r"^(?:(?:बदला|replace)\s*:\s*)?(.+?)\s*(?:->|=>|–>|ते|म्हणजे)\s*(.+)$", topic, re.IGNORECASE)
                    if arrow_match:
                        old_w = arrow_match.group(1).strip()
                        new_w = arrow_match.group(2).strip()
                        q_item["question"] = q_item["question"].replace(old_w, new_w)
                        q_item["explanation"] = q_item["explanation"].replace(old_w, new_w)[:140]
                        q_item["options"] = [opt.replace(old_w, new_w)[:90] for opt in q_item["options"]]
                        bot.reply_to(msg, f"✅ **बदल यशस्वी!**\n`{old_w}` ➔ `{new_w}`", parse_mode="Markdown")
                    else:
                        opt_match = re.match(r"^([A-Da-d१-४1-4])\s*[\.:\)]\s*(.+)$", topic)
                        if opt_match:
                            opt_char = opt_match.group(1)
                            opt_val = opt_match.group(2).strip()[:90]
                            if opt_char in "1234":
                                opt_i = int(opt_char) - 1
                            elif opt_char in "१२३४":
                                opt_i = "१२३४".index(opt_char)
                            else:
                                opt_i = ord(opt_char.upper()) - ord('A')
                            q_item["options"][opt_i] = opt_val
                            bot.reply_to(msg, f"✅ **Q{q_idx+1} चा पर्याय {opt_char} बदलला:** `{opt_val}`", parse_mode="Markdown")
                        else:
                            q_item["question"] = topic
                            bot.reply_to(msg, f"✅ **Q{q_idx+1} चा प्रश्न बदलला!**", parse_mode="Markdown")

                show_question_edit_menu(msg.chat.id, mid, post_id, q_idx)
                return

    user_sessions[msg.chat.id] = {"topic": topic, "source_type": "text"}
    show_format_menu(msg.chat.id, topic)

# 2. Book Photo Input (Vision AI)
@bot.message_handler(content_types=['photo'])
def handle_photo(msg):
    status = bot.reply_to(msg, "📸 *पुस्तकाचा फोटो मिळाला!* AI पान वाचत आहे...", parse_mode="Markdown")
    try:
        file_info = bot.get_file(msg.photo[-1].file_id)
        img_bytes = bot.download_file(file_info.file_path)
        extracted_text = extract_text_from_photo(img_bytes)
        bot.delete_message(msg.chat.id, status.message_id)

        user_sessions[msg.chat.id] = {"topic": extracted_text[:2000], "source_type": "photo"}
        show_format_menu(msg.chat.id, "📖 पुस्तकाचे पान (Photo Scanned)")
    except Exception as e:
        bot.edit_message_text(f"❌ फोटो वाचताना त्रुटी: {str(e)}", msg.chat.id, status.message_id)

def extract_text_from_photo(img_bytes: bytes) -> str:
    import base64
    b64 = base64.b64encode(img_bytes).decode('utf-8')
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY.strip()}", "Content-Type": "application/json"}
    model_name = get_vision_model()
    payload = {
        "model": model_name,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "Extract and transcribe all educational study notes, facts, and key concepts from this textbook page accurately in Marathi/English:"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
            ]
        }],
        "temperature": 0.2,
        "max_tokens": 1500
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=40)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"]
    raise Exception(f"Vision API Error ({model_name}): {resp.status_code} {resp.text[:100]}")

# 3. Word Document (.docx) Extractor
def extract_text_from_docx(docx_bytes: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
            xml_content = z.read('word/document.xml')
            tree = ET.fromstring(xml_content)
            paragraphs = []
            for p in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                texts = [t.text for t in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if t.text]
                if texts:
                    paragraphs.append("".join(texts))
            return "\n".join(paragraphs)
    except Exception:
        return ""

# 4. Document Handler (PDF & Word .docx)
@bot.message_handler(content_types=['document'])
def handle_doc(msg):
    fname = msg.document.file_name.lower() if msg.document.file_name else "file"
    is_pdf = fname.endswith('.pdf')
    is_docx = fname.endswith('.docx') or fname.endswith('.doc')

    if not (is_pdf or is_docx):
        bot.reply_to(msg, "कृपया केवळ PDF, Word फाईल (.docx) किंवा पुस्तकाचा फोटो पाठवा.")
        return

    status = bot.reply_to(msg, f"📄 *दस्तऐवज मिळाला:* `{fname}`\nमजकूर वाचत आहे...", parse_mode="Markdown")
    try:
        file_info = bot.get_file(msg.document.file_id)
        file_bytes = bot.download_file(file_info.file_path)

        extracted = ""
        if is_docx:
            extracted = extract_text_from_docx(file_bytes)
        elif is_pdf:
            if pypdf is None:
                bot.reply_to(msg, "⚠️ PDF वाचण्यासाठी GitHub वरील `requirements.txt` मध्ये `pypdf` असणे आवश्यक आहे.\n\n📸 तोपर्यंत तुम्ही **Word फाईल (.docx)** किंवा **पुस्तकाचा फोटो** पाठवू शकता!")
                return
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages[:15]:
                t = page.extract_text()
                if t:
                    extracted += t + "\n"

        bot.delete_message(msg.chat.id, status.message_id)
        if not extracted.strip():
            bot.send_message(msg.chat.id, "⚠️ या फाईलमधून मजकूर काढता आले नाही (कदाचित ही स्कॅन केलेली प्रतिमा असावी). कृपया थेट फोटो काढून पाठवा.")
            return

        user_sessions[msg.chat.id] = {"topic": extracted[:5000], "source_type": "doc"}
        label = f"📄 {fname} (नोट्स)"
        show_format_menu(msg.chat.id, label)
    except Exception as e:
        bot.edit_message_text(f"❌ फाईल वाचताना त्रुटी: {str(e)}", msg.chat.id, status.message_id)

def show_format_menu(cid, topic_label, mid=None):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📊 Quiz Poll (प्रश्न संच)", callback_data="fmt_quiz"),
        types.InlineKeyboardButton("💡 Mnemonic (शॉर्टकट ट्रिक)", callback_data="fmt_mnemonic"),
        types.InlineKeyboardButton("📌 Quick Notes (रिव्हिजन नोट्स)", callback_data="fmt_notes"),
        types.InlineKeyboardButton("🔙 मागे जा (नवीन विषय टाका)", callback_data="back_to_start"),
        types.InlineKeyboardButton("❌ रद्द करा (Cancel)", callback_data="can_")
    )
    text = f"📝 **सामग्री:** `{topic_label[:80]}`\n\n👇 **काय तयार करायचे आहे?**"
    if mid:
        bot.edit_message_text(text, cid, mid, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(cid, text, reply_markup=markup, parse_mode="Markdown")

def show_quiz_mode_choice_menu(cid, mid):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📑 फाईलमधील प्रश्न जसेच्या तसे काढा (As-Is PYQ)", callback_data="qmode_asis"),
        types.InlineKeyboardButton("🤖 AI द्वारे नवीन संभाव्य प्रश्न बनवा (Generate New)", callback_data="qmode_aigen"),
        types.InlineKeyboardButton("🔙 मागे जा (Back)", callback_data="back_to_fmt")
    )
    text = (
        "👇 **क्विझ तयार करण्याची पद्धत निवडा:**\n\n"
        "1️⃣ **As-Is PYQ:** जर तुमच्या फाईलमध्ये आधीच प्रश्न, ४ पर्याय आणि उत्तरे असतील, तर ते जसेच्या तसे कोणतीही छेडछाड न करता काढले जातील.\n\n"
        "2️⃣ **Generate New:** दिलेल्या नोट्सच्या आधारे AI परीक्षेच्या अचूक पॅटर्ननुसार नवीन प्रश्न तयार करेल."
    )
    bot.edit_message_text(text, cid, mid, reply_markup=markup, parse_mode="Markdown")

# ------------------------------------------------------------------------------
# 4. QUESTION MANAGEMENT & EDITING HUB
# ------------------------------------------------------------------------------
def show_question_edit_menu(cid, mid, post_id, q_idx):
    if post_id not in pending_posts:
        return
    quizzes = pending_posts[post_id]["data"]
    if q_idx >= len(quizzes):
        render_preview_message(cid, mid, post_id, user_sessions.get(cid, {}))
        return

    q_item = quizzes[q_idx]
    corr_char = chr(65 + q_item["correct_option_id"])
    formatted_q = format_statements_cleanly(q_item['question'])
    text = (
        f"🛠️ **प्रश्न Q{q_idx+1} व्यवस्थापन (Question Editor):**\n\n"
        f"📌 *प्रश्न:*\n{formatted_q}\n\n"
        f"1️⃣ {q_item['options'][0]}\n"
        f"2️⃣ {q_item['options'][1]}\n"
        f"3️⃣ {q_item['options'][2]}\n"
        f"4️⃣ {q_item['options'][3]}\n\n"
        f"✅ *अचूक उत्तर:* **पर्याय {corr_char} (क्र. {q_item['correct_option_id']+1})**\n"
        f"💡 *स्पष्टीकरण:* _{q_item['explanation']}_\n\n"
        f"👇 **काय बदलायचे आहे? निवडा:**"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("✏️ प्रश्न वाक्य बदला", callback_data=f"edtarget_{post_id}_{q_idx}_q"))
    markup.add(
        types.InlineKeyboardButton("१️⃣ पर्याय १ बदला", callback_data=f"edtarget_{post_id}_{q_idx}_opt0"),
        types.InlineKeyboardButton("२️⃣ पर्याय २ बदला", callback_data=f"edtarget_{post_id}_{q_idx}_opt1")
    )
    markup.add(
        types.InlineKeyboardButton("३️⃣ पर्याय ३ बदला", callback_data=f"edtarget_{post_id}_{q_idx}_opt2"),
        types.InlineKeyboardButton("४️⃣ पर्याय ४ बदला", callback_data=f"edtarget_{post_id}_{q_idx}_opt3")
    )
    markup.add(
        types.InlineKeyboardButton("🎯 अचूक उत्तर बदला", callback_data=f"ansmenu_{post_id}_{q_idx}"),
        types.InlineKeyboardButton("💡 स्पष्टीकरण बदला", callback_data=f"edtarget_{post_id}_{q_idx}_exp")
    )
    markup.add(types.InlineKeyboardButton("🗑️ हा प्रश्न वगळा / डिलीट करा", callback_data=f"askdel_{post_id}_{q_idx}"))
    markup.add(types.InlineKeyboardButton("🔙 प्रिव्ह्यूवर परत जा (Done)", callback_data=f"back_to_prev_{post_id}"))

    try:
        bot.edit_message_text(text, cid, mid, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        bot.send_message(cid, text, reply_markup=markup, parse_mode="Markdown")

def show_answer_select_menu(cid, mid, post_id, q_idx):
    q_item = pending_posts[post_id]["data"][q_idx]
    text = (
        f"🎯 **Q{q_idx+1} चे अचूक उत्तर कोणते आहे? निवडा:**\n\n"
        f"१) {q_item['options'][0]}\n"
        f"२) {q_item['options'][1]}\n"
        f"३) {q_item['options'][2]}\n"
        f"४) {q_item['options'][3]}"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(f"{'✅' if q_item['correct_option_id']==0 else '⚪'} पर्याय १", callback_data=f"setans_{post_id}_{q_idx}_0"),
        types.InlineKeyboardButton(f"{'✅' if q_item['correct_option_id']==1 else '⚪'} पर्याय २", callback_data=f"setans_{post_id}_{q_idx}_1")
    )
    markup.add(
        types.InlineKeyboardButton(f"{'✅' if q_item['correct_option_id']==2 else '⚪'} पर्याय ३", callback_data=f"setans_{post_id}_{q_idx}_2"),
        types.InlineKeyboardButton(f"{'✅' if q_item['correct_option_id']==3 else '⚪'} पर्याय ४", callback_data=f"setans_{post_id}_{q_idx}_3")
    )
    markup.add(types.InlineKeyboardButton("🔙 मागे जा", callback_data=f"do_edit_{post_id}_{q_idx}"))
    bot.edit_message_text(text, cid, mid, reply_markup=markup, parse_mode="Markdown")

# ------------------------------------------------------------------------------
# 5. STEP-BY-STEP FLOW WITH ASYNC BACKGROUND PUBLISHING & TWO-PART CARDS
# ------------------------------------------------------------------------------
def publish_in_background(post_id, cid, mid, item):
    """Executes posting with Two-Part Cards for large questions and native polls for short ones."""
    target_id = item["channel_id"]
    try:
        if item["type"] == "quiz":
            quizzes = item["data"]
            total_q = len(quizzes)
            timer_sec = item.get("timer")
            brand = "\n\n🎯 Join: @sidhu_sir_official"
            posted_count = 0
            last_err = ""

            for i, q in enumerate(quizzes):
                exp = q.get("explanation", "")
                if len(exp) + len(brand) <= 200:
                    exp += brand
                exp = exp[:200]

                raw_q = q['question'].strip()
                # Check if question is large / multi-statement (e.g. UPSC/Rajyaseva statements)
                is_large = len(raw_q) > 240 or any(pat in raw_q for pat in ["(अ)", "(ब)", "1.", "2.", "\n"])

                if is_large:
                    # Part 1: Detailed Question Card with distinct lines
                    formatted_q = format_statements_cleanly(raw_q)
                    card_text = (
                        f"📋 **[प्रश्न {i+1}/{total_q}]**\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"{formatted_q}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"👇 **खालील पोलमध्ये अचूक पर्याय निवडा:**"
                    )
                    try:
                        bot.send_message(target_id, card_text, parse_mode="Markdown")
                    except Exception:
                        bot.send_message(target_id, card_text)
                    time.sleep(1.2)

                    # Part 2: Interactive Clickable Quiz Poll attached below
                    poll_q = f"[{i+1}/{total_q}] वरील प्रश्नाचे अचूक उत्तर निवडा:"
                else:
                    poll_q = f"[{i+1}/{total_q}] {raw_q}" if total_q > 1 else raw_q

                poll_kwargs = {
                    "chat_id": target_id,
                    "question": poll_q[:300],
                    "options": [opt[:100] for opt in q["options"][:4]],
                    "type": "quiz",
                    "correct_option_id": q["correct_option_id"] if 0 <= q["correct_option_id"] <= 3 else 0,
                    "explanation": exp,
                    "is_anonymous": True
                }
                if timer_sec:
                    poll_kwargs["open_period"] = timer_sec

                # Flood-control retry loop
                success = False
                for attempt in range(3):
                    try:
                        bot.send_poll(**poll_kwargs)
                        posted_count += 1
                        success = True
                        break
                    except telebot.apihelper.ApiTelegramException as e:
                        last_err = str(e)
                        if getattr(e, 'error_code', None) == 429:
                            wait_t = getattr(e, 'retry_after', 10) or 10
                            time.sleep(wait_t + 1)
                        else:
                            break
                    except Exception as e:
                        last_err = str(e)
                        break

                if not success and posted_count == 0:
                    break

                # Progress update for bulk posts (every 10 questions)
                if posted_count > 0 and posted_count % 10 == 0 and posted_count < total_q:
                    try:
                        bot.send_message(cid, f"⏳ **प्रगती:** `{posted_count}/{total_q}` प्रश्न `{target_id}` वर पोस्ट झाले आहेत...")
                    except Exception:
                        pass

                time.sleep(2.5)  # Safe Telegram channel pacing (20-24 msgs/min)

            if posted_count == total_q:
                bot.send_message(cid, f"🎉 **अभिनंदन!** सर्व {posted_count} प्रश्न `{target_id}` चॅनेलवर यशस्वीरीत्या पोस्ट झाले आहेत!")
            elif posted_count > 0:
                bot.send_message(cid, f"⚠️ **अर्धवट पोस्टिंग:** {total_q} पैकी {posted_count} प्रश्न पोस्ट झाले.\nत्रुटी: `{last_err}`")
            else:
                bot.send_message(
                    cid,
                    f"❌ **प्रश्न `{target_id}` चॅनेलवर पोस्ट होऊ शकले नाहीत!**\n\n"
                    f"📌 **टेलिग्राम त्रुटी:** `{last_err}`\n\n"
                    f"💡 **कृपया तपासा:**\n"
                    f"१. बॉट (`@SIDHUSIR_QUIZBOT`) हा `{target_id}` चॅनेलचा **Administrator (Admin)** आहे का?\n"
                    f"२. बॉटला **'Post Messages'** ची परवानगी दिली आहे का?"
                )
        else:
            content = item["data"] + "\n\n━━━━━━━━━━━━━━━\n📢 **अधिक तयारीसाठी जॉईन करा:** @sidhu_sir_official"
            try:
                bot.send_message(target_id, content, parse_mode="Markdown")
                bot.send_message(cid, f"🎉 **अभिनंदन!** मजकूर `{target_id}` चॅनेलवर यशस्वीरीत्या पोस्ट झाला आहे!")
            except Exception as e:
                bot.send_message(
                    cid,
                    f"❌ **चॅनेलवर पोस्ट करता आले नाही:** `{e}`\n\n"
                    f"बॉट `{target_id}` चा Admin आहे का ते तपासा."
                )

    except Exception as e:
        bot.send_message(cid, f"❌ पोस्टिंग प्रक्रिया त्रुटी: {str(e)}")
    finally:
        if post_id in pending_posts:
            del pending_posts[post_id]

@bot.callback_query_handler(func=lambda call: True)
def handle_cb(call):
    cid = call.message.chat.id
    mid = call.message.message_id
    sess = user_sessions.get(cid, {})

    # Step 0: Back to Start (New Topic)
    if call.data == "back_to_start":
        user_sessions[cid] = {}
        bot.edit_message_text("🔄 **सुरुवात:**\nकृपया खाली नवीन विषयाचे नाव, पुस्तकाचा फोटो, PDF किंवा Word फाईल (.docx) पाठवा.", cid, mid)

    # Step 1: Format Chosen -> If Quiz, ask As-Is vs AI Generate; else choose channel
    elif call.data.startswith("fmt_"):
        fmt_val = call.data.replace("fmt_", "")
        sess["fmt"] = fmt_val
        if fmt_val == "quiz":
            show_quiz_mode_choice_menu(cid, mid)
        else:
            show_channel_menu(cid, mid)

    elif call.data == "back_to_fmt":
        show_format_menu(cid, sess.get("topic", "विषय")[:60], mid)

    # Step 1.5: Quiz Mode Selection (As-Is PYQ vs AI Generate)
    elif call.data.startswith("qmode_"):
        sess["quiz_source_mode"] = "as_is" if call.data == "qmode_asis" else "ai_gen"
        show_channel_menu(cid, mid)

    # Step 2: Channel Chosen -> Level (for Quiz) or Lang (for Notes)
    elif call.data.startswith("ch_"):
        sess["ch"] = call.data.replace("ch_", "")
        if sess.get("fmt") == "quiz":
            show_level_menu(cid, mid)
        else:
            show_lang_menu(cid, mid)

    elif call.data == "back_to_ch":
        if sess.get("fmt") == "quiz":
            show_quiz_mode_choice_menu(cid, mid)
        else:
            show_format_menu(cid, sess.get("topic", "विषय")[:60], mid)

    # Step 3: Level Chosen -> Lang
    elif call.data.startswith("lvl_"):
        sess["lvl"] = call.data.replace("lvl_", "")
        show_lang_menu(cid, mid)

    elif call.data == "back_to_lvl":
        show_channel_menu(cid, mid)

    # Step 4: Lang Chosen -> Count (for Quiz) or Run (for Notes)
    elif call.data.startswith("lng_"):
        sess["lang"] = call.data.replace("lng_", "")
        if sess.get("fmt") == "quiz":
            show_count_menu(cid, mid)
        else:
            run_content_generation(cid, mid, sess)

    elif call.data == "back_to_lang":
        if sess.get("fmt") == "quiz":
            show_level_menu(cid, mid)
        else:
            show_channel_menu(cid, mid)

    # Step 5: Count Chosen -> Choose Mode (Normal vs Live Timer)
    elif call.data.startswith("cnt_"):
        val = call.data.replace("cnt_", "")
        if val == "custom":
            sess["waiting_custom_cnt"] = mid
            bot.edit_message_text(
                "👇 **तुम्हाला किती प्रश्न तयार/पोस्ट करायचे आहेत? संख्या टाईप करून पाठवा:**\n*(उदा. 40, 50, 75, 100, 150)*",
                cid, mid, parse_mode="Markdown"
            )
            return

        sess["cnt"] = int(val)
        show_timer_menu(cid, mid)

    elif call.data == "back_to_cnt":
        show_lang_menu(cid, mid)

    # Step 6: Mode Selection (Timer vs Normal) -> Run Generation
    elif call.data.startswith("tmr_"):
        t_val = call.data.replace("tmr_", "")
        sess["timer"] = 45 if t_val == "45" else None
        run_content_generation(cid, mid, sess)

    elif call.data == "back_to_timer":
        show_count_menu(cid, mid)

    # Manual Edit Menu: Choose which question to edit
    elif call.data.startswith("edt_menu_"):
        post_id = call.data.replace("edt_menu_", "")
        if post_id not in pending_posts:
            bot.answer_callback_query(call.id, "कालबाह्य झाले आहे.")
            return

        quizzes = pending_posts[post_id]["data"]
        markup = types.InlineKeyboardMarkup(row_width=2)
        for idx in range(min(len(quizzes), 25)):
            markup.add(types.InlineKeyboardButton(f"🛠️ Q{idx+1} एडिट / पर्याय / डिलीट", callback_data=f"do_edit_{post_id}_{idx}"))
        markup.add(types.InlineKeyboardButton("🔙 प्रिव्ह्यूवर परत जा (Back)", callback_data=f"back_to_prev_{post_id}"))
        bot.edit_message_text("👇 **कोणत्या प्रश्नाचे व्यवस्थापन करायचे आहे? निवडा:**", cid, mid, reply_markup=markup, parse_mode="Markdown")

    # Enter Question Editor Hub
    elif call.data.startswith("do_edit_"):
        parts = call.data.split("_")
        post_id = parts[2]
        q_idx = int(parts[3])
        show_question_edit_menu(cid, mid, post_id, q_idx)

    # Select Specific Edit Target
    elif call.data.startswith("edtarget_"):
        parts = call.data.split("_")
        post_id = parts[1]
        q_idx = int(parts[2])
        target = parts[3]

        sess["editing"] = {"post_id": post_id, "q_idx": q_idx, "target": target, "mid": mid}
        q_item = pending_posts[post_id]["data"][q_idx]

        labels = {
            "q": ("प्रश्न वाक्य", q_item["question"]),
            "opt0": ("पर्याय १ / A", q_item["options"][0]),
            "opt1": ("पर्याय २ / B", q_item["options"][1]),
            "opt2": ("पर्याय ३ / C", q_item["options"][2]),
            "opt3": ("पर्याय ४ / D", q_item["options"][3]),
            "exp": ("स्पष्टीकरण", q_item["explanation"])
        }
        lbl, current_val = labels.get(target, ("मजकूर", ""))

        prompt_txt = (
            f"✏️ **Q{q_idx+1} साठी {lbl} बदला:**\n\n"
            f"📌 *सध्याचा मजकूर:*\n`{current_val}`\n\n"
            f"👇 **नवीन {lbl} खाली थेट टाईप करून पाठवा:**"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 रद्द करा / मागे जा", callback_data=f"do_edit_{post_id}_{q_idx}"))
        bot.edit_message_text(prompt_txt, cid, mid, reply_markup=markup, parse_mode="Markdown")

    # Change Answer Menu
    elif call.data.startswith("ansmenu_"):
        parts = call.data.split("_")
        post_id = parts[1]
        q_idx = int(parts[2])
        show_answer_select_menu(cid, mid, post_id, q_idx)

    # Set Correct Answer directly
    elif call.data.startswith("setans_"):
        parts = call.data.split("_")
        post_id = parts[1]
        q_idx = int(parts[2])
        ans_id = int(parts[3])

        pending_posts[post_id]["data"][q_idx]["correct_option_id"] = ans_id
        bot.answer_callback_query(call.id, f"अचूक उत्तर निश्चित केले!")
        show_question_edit_menu(cid, mid, post_id, q_idx)

    # Ask Delete Confirmation
    elif call.data.startswith("askdel_"):
        parts = call.data.split("_")
        post_id = parts[1]
        q_idx = int(parts[2])

        text = f"⚠️ **तुम्हाला Q{q_idx+1} खरोखर वगळायचा (Delete करायचा) आहे का?**\nहा प्रश्न या क्विझ संचामधून कायमचा काढून टाकला जाईल."
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🗑️ हो, हा प्रश्न डिलीट करा", callback_data=f"confirmdel_{post_id}_{q_idx}"),
            types.InlineKeyboardButton("❌ नको, मागे जा", callback_data=f"do_edit_{post_id}_{q_idx}")
        )
        bot.edit_message_text(text, cid, mid, reply_markup=markup, parse_mode="Markdown")

    # Confirm Delete
    elif call.data.startswith("confirmdel_"):
        parts = call.data.split("_")
        post_id = parts[1]
        q_idx = int(parts[2])

        quizzes = pending_posts[post_id]["data"]
        if len(quizzes) <= 1:
            bot.answer_callback_query(call.id, "किमान १ प्रश्न असणे आवश्यक आहे!")
            return

        del quizzes[q_idx]
        bot.answer_callback_query(call.id, f"Q{q_idx+1} यशस्वीरीत्या वगळण्यात आला!")
        render_preview_message(cid, mid, post_id, sess)

    # Back to Preview
    elif call.data.startswith("back_to_prev_"):
        post_id = call.data.replace("back_to_prev_", "")
        if "editing" in sess:
            del sess["editing"]
        render_preview_message(cid, mid, post_id, sess)

    # Step 7: Publish to Target Channel (Non-blocking Asynchronous Background Thread)
    elif call.data.startswith("pub_"):
        post_id = call.data.replace("pub_", "")
        if post_id not in pending_posts:
            bot.answer_callback_query(call.id, "कालबाह्य झाले आहे.")
            return

        bot.answer_callback_query(call.id, "🚀 चॅनलवर पोस्टिंग सुरू केले आहे...")
        item = pending_posts[post_id]
        target_id = item["channel_id"]
        bot.edit_message_text(f"🚀 `{target_id}` वर पोस्टिंग सुरू झाले आहे...", cid, mid, parse_mode="Markdown")

        threading.Thread(target=publish_in_background, args=(post_id, cid, mid, item), daemon=True).start()

    elif call.data == "can_":
        bot.edit_message_text("❌ रद्द करण्यात आले.", cid, mid)

def show_channel_menu(cid, mid):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(CHANNELS["upsc_polity"]["title"], callback_data="ch_upsc_polity"),
        types.InlineKeyboardButton(CHANNELS["upsc_history"]["title"], callback_data="ch_upsc_history")
    )
    markup.add(
        types.InlineKeyboardButton(CHANNELS["upsc_geo"]["title"], callback_data="ch_upsc_geo"),
        types.InlineKeyboardButton(CHANNELS["upsc_economy"]["title"], callback_data="ch_upsc_economy")
    )
    markup.add(
        types.InlineKeyboardButton(CHANNELS["upsc_env"]["title"], callback_data="ch_upsc_env"),
        types.InlineKeyboardButton(CHANNELS["upsc_sci"]["title"], callback_data="ch_upsc_sci")
    )
    markup.add(
        types.InlineKeyboardButton(CHANNELS["mpsc_official"]["title"], callback_data="ch_mpsc_official")
    )
    markup.add(types.InlineKeyboardButton("🔙 मागे जा (Back)", callback_data="back_to_ch"))
    bot.edit_message_text("👇 **कोणत्या चॅनेलवर पोस्ट करायचे आहे?**", cid, mid, reply_markup=markup, parse_mode="Markdown")

def show_level_menu(cid, mid):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👑 UPSC Latest (1, 2 Statements)", callback_data="lvl_upsc"),
        types.InlineKeyboardButton("🏛️ MPSC राज्यसेवा (अ, ब, क विधाने)", callback_data="lvl_rajyaseva")
    )
    markup.add(
        types.InlineKeyboardButton("🎯 MPSC Combine (कलमे व वस्तुनिष्ठ)", callback_data="lvl_combine"),
        types.InlineKeyboardButton("👮 पोलीस भरती/सरळसेवा (थेट १-ओळी)", callback_data="lvl_bharti")
    )
    markup.add(types.InlineKeyboardButton("🔙 मागे जा (Back)", callback_data="back_to_lvl"))
    bot.edit_message_text("👇 **परीक्षेचा अचूक पॅटर्न व स्तर (Level) निवडा:**", cid, mid, reply_markup=markup, parse_mode="Markdown")

def show_lang_menu(cid, mid):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🌐 Bilingual (मराठी + English)", callback_data="lng_bilingual"),
        types.InlineKeyboardButton("🚩 फक्त शुद्ध मराठी", callback_data="lng_marathi"),
        types.InlineKeyboardButton("🇬🇧 Only English", callback_data="lng_english"),
        types.InlineKeyboardButton("🔙 मागे जा (Back)", callback_data="back_to_lang"))
    bot.edit_message_text("👇 **कोणत्या भाषेत कन्टेन्ट हवा आहे?**", cid, mid, reply_markup=markup, parse_mode="Markdown")

def show_count_menu(cid, mid):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("⚡ १ प्रश्न", callback_data="cnt_1"),
        types.InlineKeyboardButton("🔥 ५ प्रश्न", callback_data="cnt_5")
    )
    markup.add(
        types.InlineKeyboardButton("🏆 १० प्रश्न", callback_data="cnt_10"),
        types.InlineKeyboardButton("🚀 २५ प्रश्न", callback_data="cnt_25")
    )
    markup.add(
        types.InlineKeyboardButton("🎯 ५० प्रश्न", callback_data="cnt_50"),
        types.InlineKeyboardButton("💯 १०० प्रश्न", callback_data="cnt_100")
    )
    markup.add(types.InlineKeyboardButton("✍️ स्वतः संख्या टाका (Custom Count)", callback_data="cnt_custom"))
    markup.add(types.InlineKeyboardButton("🔙 मागे जा (Back)", callback_data="back_to_cnt"))
    bot.edit_message_text("👇 **किती प्रश्न तयार / पोस्ट करायचे आहेत?**", cid, mid, reply_markup=markup, parse_mode="Markdown")

def show_timer_menu(cid, mid):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("♾️ नॉर्मल क्विझ (कायम चालू - कधीही सोडवता येईल)", callback_data="tmr_none"),
        types.InlineKeyboardButton("⏱️ लाईव्ह टेस्ट (४५ सेकंदांचा उलटा टायमर)", callback_data="tmr_45"),
        types.InlineKeyboardButton("🔙 मागे जा (Back)", callback_data="back_to_timer")
    )
    bot.edit_message_text("👇 **क्विझ प्रकार (Quiz Mode) निवडा:**", cid, mid, reply_markup=markup, parse_mode="Markdown")

def run_content_generation(cid, mid, sess):
    ch_info = CHANNELS[sess["ch"]]
    topic = sess["topic"]
    fmt = sess["fmt"]
    lang = sess["lang"]
    qmode = sess.get("quiz_source_mode", "ai_gen")

    bot.edit_message_text("⏳ **AI द्वारे प्रक्रिया सुरू आहे...** (अवघे काही सेकंद थांबा)...", cid, mid, parse_mode="Markdown")
    try:
        lang_str = "BILINGUAL (English / Marathi)" if lang == "bilingual" else ("Marathi only" if lang == "marathi" else "English only")
        post_id = str(mid)

        if fmt == "quiz":
            cnt = sess.get("cnt", 1)
            lvl = sess.get("lvl", "combine")

            if qmode == "as_is":
                pattern_instruction = (
                    "TASK: EXTRACT QUESTIONS AND OPTIONS AS-IS FROM SOURCE MATERIAL.\n"
                    f"Source Material containing Question Bank / PYQs:\n'''\n{topic}\n'''\n\n"
                    f"RULES:\n"
                    f"1. Extract up to {cnt} questions verbatim from the source material without inventing, altering, or rephrasing them.\n"
                    f"2. Statements MUST be separated by newlines so each appears on its own line.\n"
                    f"3. Extract the exact question text, the 4 choices, correct answer (0-3), and explanation.\n"
                )
            else:
                if lvl == "upsc":
                    pattern_instruction = (
                        "EXAM LEVEL: UPSC Civil Services Examination (CSE) Prelims Standard.\n"
                        "QUESTION FORMAT (MANDATORY UPSC STYLE):\n"
                        "- Analytical, multi-statement questions ('Consider the following statements:\\n1. ...\\n\\n2. ...\\n\\nWhich of the statements given above is/are correct?').\n"
                        "- Statements in the question text MUST be numbered with digits: 1., 2., 3. and separated by newlines!\n"
                        "- Options MUST be lettered in English: (a) 1 only, (b) 2 only, (c) Both 1 and 2, (d) Neither 1 nor 2 OR (a) Only one, (b) Only two, (c) All three, (d) None.\n"
                    )
                elif lvl == "rajyaseva":
                    pattern_instruction = (
                        "EXAM LEVEL: MPSC राज्यसेवा (Civil Services) पूर्व परीक्षा Standard.\n"
                        "QUESTION FORMAT (MANDATORY MPSC RAJYASEVA STYLE):\n"
                        "- बहुविधानात्मक विश्लेषणात्मक प्रश्न ('खालील विधाने विचारात घ्या:\\n(अ) ...\\n\\n(ब) ...\\n\\n(क) ...\\n\\nवरीलपैकी कोणते/ती विधान/ने योग्य आहे/त?').\n"
                        "- प्रश्न वाक्यातील विधाने MUST be lettered in Marathi: (अ), (ब), (क), (ड) and separated by newlines!\n"
                        "- खालील ४ पर्याय MUST be numbered in Marathi digits: १) फक्त (अ), २) (अ) आणि (ब), ३) (ब) आणि (क), ४) वरील सर्व.\n"
                    )
                elif lvl == "combine":
                    pattern_instruction = (
                        "EXAM LEVEL: MPSC गट ब व गट क संयुक्त (Combine Group B & C) Standard.\n"
                        "QUESTION FORMAT (MANDATORY MPSC COMBINE STYLE):\n"
                        "- विधानात्मक + थेट वस्तुनिष्ठ संमिश्र प्रश्न (कलमे, घटनादुरुस्त्या, समित्या, तारखा).\n"
                        "- विधाने असल्यास (अ), (ब) वापरा आणि ओळी वेगळ्या ठेवा.\n"
                        "- खालील ४ पर्याय MUST be numbered: १) ..., २) ..., ३) ..., ४) ...\n"
                    )
                else: # bharti
                    pattern_instruction = (
                        "EXAM LEVEL: पोलीस भरती / तलाठी / सरळसेवा परीक्षा Standard.\n"
                        "QUESTION FORMAT (MANDATORY BHARTI STYLE):\n"
                        "- थेट १-ओळी (One-liner) वस्तुनिष्ठ प्रश्न. सोपी व थेट प्रमाण भाषा.\n"
                        "- खालील ४ पर्याय MUST be numbered: १) ..., २) ..., ३) ..., ४) ...\n"
                    )

                pattern_instruction += (
                    f"Subject: {ch_info['sub']}. Language: {lang_str}.\n"
                    f"Source Material / Notes:\n'''\n{topic}\n'''\n\n"
                    f"Generate exactly {cnt} high-yield MCQs.\n"
                )

            prompt = (
                f"{pattern_instruction}\n"
                f"CONSTRAINTS (STRICT FOR TELEGRAM POLLS):\n"
                f"1. 'question' can be detailed with statements on separate lines (DO NOT put option letters A/B/C/D inside question).\n"
                f"2. exactly 4 'options', each under 90 chars.\n"
                f"3. 'correct_option_id' integer 0 to 3.\n"
                f"4. 'explanation' max 140 chars.\n"
                f"Output MUST be valid JSON in this exact structure:\n"
                f"{{\n"
                f"  \"questions\": [\n"
                f"    {{\n"
                f"      \"question\": \"...\",\n"
                f"      \"options\": [\"...\", \"...\", \"...\", \"...\"],\n"
                f"      \"correct_option_id\": 0,\n"
                f"      \"explanation\": \"...\"\n"
                f"    }}\n"
                f"  ]\n"
                f"}}"
            )

            raw = ask_groq(prompt, json_mode=True)
            data = parse_json_mcqs(raw)
            pending_posts[post_id] = {
                "type": "quiz",
                "channel_id": ch_info["id"],
                "data": data,
                "timer": sess.get("timer")
            }

        elif fmt == "mnemonic":
            prompt = f"Create a memorable MNEMONIC / SHORT TRICK in {lang_str} for subject '{ch_info['sub']}' on topic '{topic}'. Ensure 100% historical accuracy. Use emojis, bold text, clear breakdown."
            text = ask_groq(prompt, json_mode=False)
            pending_posts[post_id] = {"type": "mnemonic", "channel_id": ch_info["id"], "data": text}

        else: # notes
            prompt = f"Create a 1-Minute Quick Revision Note in {lang_str} for '{ch_info['sub']}' on topic '{topic}'. Ensure strict historical accuracy. 4-5 high-yield bullet points with emojis, key articles/facts, and exam traps."
            text = ask_groq(prompt, json_mode=False)
            pending_posts[post_id] = {"type": "notes", "channel_id": ch_info["id"], "data": text}

        render_preview_message(cid, mid, post_id, sess)

    except Exception as e:
        bot.edit_message_text(f"❌ त्रुटी: {str(e)}", cid, mid)

def render_preview_message(cid, mid, post_id, sess):
    if post_id not in pending_posts:
        return
    item = pending_posts[post_id]
    ch_info = CHANNELS[sess["ch"]]
    fmt = item["type"]

    if fmt == "quiz":
        data = item["data"]
        mode_lbl = "⏱️ ४५ सेकंद टायमर" if item.get("timer") else "♾️ कायम चालू (Normal)"
        preview = (
            f"📋 *Quiz Preview (एकूण {len(data)} प्रश्न तयार झाले)*\n"
            f"🎯 *Target:* `{ch_info['id']}` | *Mode:* {mode_lbl}\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
        )
        for idx, q in enumerate(data):
            fmt_q = format_statements_cleanly(q['question'])
            q_text = f"*Q{idx+1}:*\n{fmt_q}\n\n"
            for i, o in enumerate(q['options']):
                q_text += f"{'✅' if i == q['correct_option_id'] else '⚪'} {o}\n"
            q_text += f"💡 *Exp:* {q['explanation']}\n\n"

            if len(preview) + len(q_text) < 3800:
                preview += q_text
            else:
                preview += f"*(...आणि इतर {len(data) - idx} प्रश्न थेट चॅनेलवर पोस्ट होतील)*\n"
                break
    elif fmt == "mnemonic":
        preview = f"📋 *Mnemonic Preview*\n🎯 *Target:* `{ch_info['id']}`\n\n{item['data']}"
    else:
        preview = f"📋 *Quick Notes Preview*\n🎯 *Target:* `{ch_info['id']}`\n\n{item['data']}"

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("🚀 चॅनलवर पोस्ट करा", callback_data=f"pub_{post_id}"))
    if fmt == "quiz":
        markup.add(types.InlineKeyboardButton("🛠️ प्रश्न / पर्याय एडिट करा किंवा वगळा", callback_data=f"edt_menu_{post_id}"))
        markup.add(types.InlineKeyboardButton("🔙 मागे जा (Back / बदल करा)", callback_data="back_to_timer"))
    else:
        markup.add(types.InlineKeyboardButton("🔙 मागे जा (Back / बदल करा)", callback_data="back_to_lang"))
    markup.add(types.InlineKeyboardButton("❌ रद्द करा (Cancel)", callback_data="can_"))

    try:
        bot.edit_message_text(preview, cid, mid, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        bot.send_message(cid, preview, reply_markup=markup, parse_mode="Markdown")

# ------------------------------------------------------------------------------
# 6. RUN BOT (CLEAN INFINITY POLLING WITH AUTO-RESTART)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    print("🚀 Sidhu Sir's Bot is online 24/7!")
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10, logger_level=logging.INFO)
        except Exception as e:
            logging.error(f"Polling loop restart after error: {e}")
            time.sleep(3)
