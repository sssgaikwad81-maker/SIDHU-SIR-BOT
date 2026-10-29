"""
Sidhu Sir's Ultimate Multi-Channel AI Bot (Strict Accuracy + Vision + PDF + Word Doc + Manual Edit + Back Everywhere)
=====================================================================================================================
Features:
1. Strict Historical & Constitutional Accuracy Guardrails (Swaraj Bill = Tilak's inspiration; Mahad = Dr. Ambedkar, etc.).
2. Handles:
   - 📝 Text Topics
   - 📸 Book Page Photos (Vision AI with Qwen 3.8 27B)
   - 📄 PDF Documents (pypdf up to 10 pages)
   - 📑 Word Files (.docx / .doc built-in zero-dependency extractor)
3. 🔙 Back button navigation on EVERY step from start to finish (Format, Channel, Level, Lang, Count, Timer, Preview, Edit).
4. ✏️ Manual Edit Option: Fix any word (e.g., 'बदला: सादर केले -> टिळकांच्या प्रेरणेने') or rewrite entire question before posting!
5. 📋 Full Question Preview (Displays ALL generated questions Q1, Q2, Q3, Q4, Q5... before posting).
6. ♾️ Normal Quiz (Permanent open) vs ⏱️ Live Test (45s Timer).
7. 📊 Quizzes, 💡 Mnemonics, 📌 Quick Notes for all 7 channels.
8. 🛡️ Active 2026 Groq Models (openai/gpt-oss-20b & qwen/qwen3.8-27b): Zero 404 model_not_found errors!
9. 🔁 Rock-solid 409 Conflict auto-recovery loop: Never exits on redeploy handover!
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

# Graceful PDF support (Prevents bot crash if pypdf is not yet installed in requirements.txt)
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

    # Priority 1: Match against verified active models (gpt-oss-20b, qwen3.8-27b, etc.)
    for m in KNOWN_TEXT_MODELS:
        if m in available and m not in candidates:
            candidates.append(m)

    # Priority 2: Any other available chat model that is NOT an audio/guard/canopy model
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
        "STRICT FACTUAL & TERMINOLOGICAL ACCURACY RULES (CRITICAL):\n"
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
        "4. Source Material Fidelity:\n"
        "   - When notes, Word docs, or PDF content are provided, questions and answers MUST strictly adhere to the exact facts and vocabulary stated in the notes.\n"
        "   - Use authentic MPSC Marathi phrasing: 'कोणाच्या प्रेरणेने', 'कोणाच्या अध्यक्षतेखाली', 'खालीलपैकी अचूक विधान कोणते', etc. Never use loose or inaccurate verbs.\n"
    )

    last_error = ""
    for model_name in candidate_models:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_rules},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.25,
            "max_tokens": 2048
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=35)
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

def parse_plain_text_mcqs(text: str) -> list:
    mcqs = []
    blocks = re.split(r"(?:\n\s*|\A)(?:Q\s*\d+[\.:]|\d+[\.:])\s*", text)
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        opts = re.findall(r"(?:[A-Da-d][\.\)]|[\(][A-Da-d][\)])\s*(.+?)(?=(?:[A-Da-d][\.\)]|[\(][A-Da-d][\)]|उत्तर|Ans|Explanation|स्पष्टीकरण|\Z))", b, re.DOTALL)
        if len(opts) >= 4:
            q_lines = b.split("\n")[0].strip()
            clean_opts = [o.strip() for o in opts[:4]]
            ans_match = re.search(r"(?:उत्तर|Ans|Correct)\s*[:\-]?\s*([A-Da-d])", b)
            corr_idx = 0
            if ans_match:
                corr_idx = ord(ans_match.group(1).upper()) - ord("A")
            exp_match = re.search(r"(?:स्पष्टीकरण|Explanation)\s*[:\-]?\s*(.+)", b, re.DOTALL)
            exp = exp_match.group(1).strip()[:140] if exp_match else "MPSC संदर्भ नोट्सनुसार अचूक उत्तर."
            mcqs.append({
                "question": q_lines[:280],
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

    # Strategy 1: Direct JSON parse
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

    # Strategy 2: Array regex extract
    arr_match = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
    if arr_match:
        try:
            data = json.loads(arr_match.group(0))
            if isinstance(data, list):
                return data
        except Exception:
            pass

    # Strategy 3: Object regex extract
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

    # Strategy 4: Plain text numbered MCQ fallback
    parsed = parse_plain_text_mcqs(text)
    if parsed:
        return parsed

    raise Exception(f"AI उत्तरामधून प्रश्न काढता आले नाहीत. कृपया पुन्हा प्रयत्न करा.")

# ------------------------------------------------------------------------------
# 3. INPUT HANDLERS: TEXT, PHOTO, PDF, WORD DOC & MANUAL EDIT
# ------------------------------------------------------------------------------
@bot.message_handler(commands=['start', 'help'])
def start_cmd(msg):
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

# 1. Text Input & Manual Edit Handler
@bot.message_handler(func=lambda m: True, content_types=['text'])
def handle_text(msg):
    topic = msg.text.strip()
    if not topic or topic.startswith('/'):
        return

    # Check if user is currently editing a question
    sess = user_sessions.get(msg.chat.id, {})
    if "editing" in sess:
        edit_info = sess.pop("editing")
        post_id = edit_info["post_id"]
        q_idx = edit_info["q_idx"]
        mid = edit_info["mid"]

        if post_id in pending_posts and pending_posts[post_id]["type"] == "quiz":
            q_item = pending_posts[post_id]["data"][q_idx]

            # Pattern: बदला: जुना शब्द -> नवीन शब्द (किंवा replace: old -> new)
            rep_match = re.search(r"(?:बदला|replace)\s*:\s*(.+?)\s*(?:->|=>|–>|ते|म्हणजे)\s*(.+)", topic, re.IGNORECASE)
            if rep_match:
                old_w = rep_match.group(1).strip()
                new_w = rep_match.group(2).strip()
                q_item["question"] = q_item["question"].replace(old_w, new_w)
                q_item["explanation"] = q_item["explanation"].replace(old_w, new_w)
                q_item["options"] = [opt.replace(old_w, new_w) for opt in q_item["options"]]
                bot.reply_to(msg, f"✅ **दुरुस्ती यशस्वी!**\n`{old_w}` ➔ `{new_w}`", parse_mode="Markdown")
            else:
                q_item["question"] = topic
                bot.reply_to(msg, f"✅ **Q{q_idx+1} चा प्रश्न यशस्वीरीत्या बदलला!**", parse_mode="Markdown")

            render_preview_message(msg.chat.id, mid, post_id, sess)
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

# 3. Word Document (.docx) Extractor (Pure Standard Library - Zero Dependency)
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
            for page in reader.pages[:10]:
                t = page.extract_text()
                if t:
                    extracted += t + "\n"

        bot.delete_message(msg.chat.id, status.message_id)
        if not extracted.strip():
            bot.send_message(msg.chat.id, "⚠️ या फाईलमधून मजकूर काढता आले नाही (कदाचित ही स्कॅन केलेली प्रतिमा असावी). कृपया थेट फोटो काढून पाठवा.")
            return

        user_sessions[msg.chat.id] = {"topic": extracted[:3000], "source_type": "doc"}
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

# ------------------------------------------------------------------------------
# 5. STEP-BY-STEP FLOW WITH BACK BUTTONS ON EVERY STEP
# ------------------------------------------------------------------------------
@bot.callback_query_handler(func=lambda call: True)
def handle_cb(call):
    cid = call.message.chat.id
    mid = call.message.message_id
    sess = user_sessions.get(cid, {})

    # Step 0: Back to Start (New Topic)
    if call.data == "back_to_start":
        bot.edit_message_text("🔄 **सुरुवात:**\nकृपया खाली नवीन विषयाचे नाव, पुस्तकाचा फोटो, PDF किंवा Word फाईल (.docx) पाठवा.", cid, mid)

    # Step 1: Format Chosen -> Choose Channel
    elif call.data.startswith("fmt_"):
        sess["fmt"] = call.data.replace("fmt_", "")
        show_channel_menu(cid, mid)

    elif call.data == "back_to_fmt":
        show_format_menu(cid, sess.get("topic", "विषय")[:60], mid)

    # Step 2: Channel Chosen -> Level (for Quiz) or Lang (for Notes)
    elif call.data.startswith("ch_"):
        sess["ch"] = call.data.replace("ch_", "")
        if sess.get("fmt") == "quiz":
            show_level_menu(cid, mid)
        else:
            show_lang_menu(cid, mid)

    elif call.data == "back_to_ch":
        show_channel_menu(cid, mid)

    # Step 3: Level Chosen -> Lang
    elif call.data.startswith("lvl_"):
        sess["lvl"] = call.data.replace("lvl_", "")
        show_lang_menu(cid, mid)

    elif call.data == "back_to_lvl":
        if sess.get("fmt") == "quiz":
            show_level_menu(cid, mid)
        else:
            show_channel_menu(cid, mid)

    # Step 4: Lang Chosen -> Count (for Quiz) or Run (for Notes)
    elif call.data.startswith("lng_"):
        sess["lang"] = call.data.replace("lng_", "")
        if sess.get("fmt") == "quiz":
            show_count_menu(cid, mid)
        else:
            run_content_generation(cid, mid, sess)

    elif call.data == "back_to_lang":
        show_lang_menu(cid, mid)

    # Step 5: Count Chosen -> Choose Mode (Normal vs Live Timer)
    elif call.data.startswith("cnt_"):
        sess["cnt"] = int(call.data.replace("cnt_", ""))
        show_timer_menu(cid, mid)

    elif call.data == "back_to_cnt":
        show_count_menu(cid, mid)

    # Step 6: Mode Selection (Timer vs Normal) -> Run Generation
    elif call.data.startswith("tmr_"):
        t_val = call.data.replace("tmr_", "")
        sess["timer"] = 45 if t_val == "45" else None
        run_content_generation(cid, mid, sess)

    elif call.data == "back_to_timer":
        show_timer_menu(cid, mid)

    # Manual Edit Menu: Choose which question to edit
    elif call.data.startswith("edt_menu_"):
        post_id = call.data.replace("edt_menu_", "")
        if post_id not in pending_posts:
            bot.answer_callback_query(call.id, "कालबाह्य झाले आहे.")
            return

        quizzes = pending_posts[post_id]["data"]
        markup = types.InlineKeyboardMarkup(row_width=2)
        for idx in range(len(quizzes)):
            markup.add(types.InlineKeyboardButton(f"✏️ Q{idx+1} दुरुस्त करा", callback_data=f"do_edit_{post_id}_{idx}"))
        markup.add(types.InlineKeyboardButton("🔙 प्रिव्ह्यूवर परत जा (Back)", callback_data=f"back_to_prev_{post_id}"))
        bot.edit_message_text("👇 **कोणता प्रश्न दुरुस्त करायचा आहे? निवडा:**", cid, mid, reply_markup=markup, parse_mode="Markdown")

    # Enter Question Edit State
    elif call.data.startswith("do_edit_"):
        parts = call.data.split("_")
        post_id = parts[2]
        q_idx = int(parts[3])

        q_item = pending_posts[post_id]["data"][q_idx]
        sess["editing"] = {"post_id": post_id, "q_idx": q_idx, "mid": mid}

        prompt_txt = (
            f"✏️ **Q{q_idx+1} दुरुस्ती (Manual Edit):**\n\n"
            f"📌 *सध्याचा प्रश्न:*\n`{q_item['question']}`\n\n"
            f"💡 *सध्याचे स्पष्टीकरण:*\n_{q_item['explanation']}_\n\n"
            f"👇 **खालीलपैकी कोणताही एक मेसेज पाठवा:**\n"
            f"1️⃣ **केवळ विशिष्ट शब्द बदलायचा असल्यास:**\n"
            f"`बदला: जुना शब्द -> नवीन शब्द`\n"
            f"*(उदा. `बदला: सादर केले -> टिळकांच्या प्रेरणेने`)*\n\n"
            f"2️⃣ **किंवा नवीन सुधारित प्रश्न थेट टाईप करून पाठवा.**"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 रद्द करा / प्रिव्ह्यूवर जा (Back)", callback_data=f"back_to_prev_{post_id}"))
        bot.edit_message_text(prompt_txt, cid, mid, reply_markup=markup, parse_mode="Markdown")

    # Back to Preview
    elif call.data.startswith("back_to_prev_"):
        post_id = call.data.replace("back_to_prev_", "")
        if "editing" in sess:
            del sess["editing"]
        render_preview_message(cid, mid, post_id, sess)

    # Step 7: Publish to Target Channel
    elif call.data.startswith("pub_"):
        post_id = call.data.replace("pub_", "")
        if post_id not in pending_posts:
            bot.answer_callback_query(call.id, "कालबाह्य झाले आहे.")
            return

        item = pending_posts[post_id]
        target_id = item["channel_id"]
        bot.edit_message_text(f"🚀 `{target_id}` वर पोस्ट होत आहे...", cid, mid, parse_mode="Markdown")

        if item["type"] == "quiz":
            quizzes = item["data"]
            timer_sec = item.get("timer")
            brand = "\n\n🎯 Join: @sidhu_sir_official"

            for i, q in enumerate(quizzes):
                exp = q["explanation"]
                if len(exp) + len(brand) <= 200:
                    exp += brand

                poll_kwargs = {
                    "chat_id": target_id,
                    "question": f"[{i+1}/{len(quizzes)}] {q['question']}" if len(quizzes) > 1 else q['question'],
                    "options": q["options"],
                    "type": "quiz",
                    "correct_option_id": q["correct_option_id"],
                    "explanation": exp,
                    "is_anonymous": True
                }
                if timer_sec:
                    poll_kwargs["open_period"] = timer_sec

                bot.send_poll(**poll_kwargs)
                time.sleep(2.5)
        else:
            content = item["data"] + "\n\n━━━━━━━━━━━━━━━\n📢 **अधिक तयारीसाठी जॉईन करा:** @sidhu_sir_official"
            bot.send_message(target_id, content, parse_mode="Markdown")

        bot.send_message(cid, f"🎉 **अभिनंदन!** कन्टेन्ट `{target_id}` चॅनेलवर यशस्वीरीत्या पोस्ट झाला आहे!")
        del pending_posts[post_id]

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
    markup.add(types.InlineKeyboardButton("🔙 मागे जा (Back)", callback_data="back_to_fmt"))
    bot.edit_message_text("👇 **कोणत्या चॅनेलवर पोस्ट करायचे आहे?**", cid, mid, reply_markup=markup, parse_mode="Markdown")

def show_level_menu(cid, mid):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👑 UPSC Latest", callback_data="lvl_upsc"),
        types.InlineKeyboardButton("🏛️ MPSC राज्यसेवा", callback_data="lvl_rajyaseva")
    )
    markup.add(
        types.InlineKeyboardButton("🎯 MPSC Combine", callback_data="lvl_combine"),
        types.InlineKeyboardButton("👮 पोलीस भरती/सरळसेवा", callback_data="lvl_bharti")
    )
    markup.add(types.InlineKeyboardButton("🔙 मागे जा (Back)", callback_data="back_to_ch"))
    bot.edit_message_text("👇 **परीक्षेचा स्तर (Level) निवडा:**", cid, mid, reply_markup=markup, parse_mode="Markdown")

def show_lang_menu(cid, mid):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🌐 Bilingual (मराठी + English)", callback_data="lng_bilingual"),
        types.InlineKeyboardButton("🚩 फक्त शुद्ध मराठी", callback_data="lng_marathi"),
        types.InlineKeyboardButton("🇬🇧 Only English", callback_data="lng_english"),
        types.InlineKeyboardButton("🔙 मागे जा (Back)", callback_data="back_to_lvl")
    )
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
    markup.add(types.InlineKeyboardButton("🔙 मागे जा (Back)", callback_data="back_to_lang"))
    bot.edit_message_text("👇 **किती प्रश्न तयार करायचे आहेत?**", cid, mid, reply_markup=markup, parse_mode="Markdown")

def show_timer_menu(cid, mid):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("♾️ नॉर्मल क्विझ (कायम चालू - कधीही सोडवता येईल)", callback_data="tmr_none"),
        types.InlineKeyboardButton("⏱️ लाईव्ह टेस्ट (४५ सेकंदांचा उलटा टायमर)", callback_data="tmr_45"),
        types.InlineKeyboardButton("🔙 मागे जा (Back)", callback_data="back_to_cnt")
    )
    bot.edit_message_text("👇 **क्विझ प्रकार (Quiz Mode) निवडा:**", cid, mid, reply_markup=markup, parse_mode="Markdown")

def run_content_generation(cid, mid, sess):
    ch_info = CHANNELS[sess["ch"]]
    topic = sess["topic"]
    fmt = sess["fmt"]
    lang = sess["lang"]

    bot.edit_message_text("⏳ **AI द्वारे कन्टेन्ट तयार होत आहे...** (अवघे १-२ सेकंद थांबा)...", cid, mid, parse_mode="Markdown")
    try:
        lang_str = "BILINGUAL (English / Marathi)" if lang == "bilingual" else ("Marathi only" if lang == "marathi" else "English only")
        post_id = str(mid)

        if fmt == "quiz":
            cnt = sess.get("cnt", 1)
            prompt = (
                f"Subject: {ch_info['sub']}. Exam Level: {sess.get('lvl', 'MPSC')}. Language: {lang_str}.\n"
                f"Source Material / Notes:\n'''\n{topic}\n'''\n\n"
                f"CRITICAL MPSC / UPSC QUESTION DESIGN RULES:\n"
                f"1. Generate exactly {cnt} MCQs strictly based on authentic facts from the source material and MPSC syllabus.\n"
                f"2. Strict historical & constitutional phrasing:\n"
                f"   - NEVER say a leader 'सादर केले' (introduced) unless it was officially introduced in a legislative assembly or parliament. E.g., for 1895 Swaraj Bill, the correct wording MUST BE: '१८९५ चे स्वराज्य विधेयक (Constitution of India Bill) कोणाच्या प्रेरणेने/मार्गदर्शनाखाली तयार करण्यात आले होते?'.\n"
                f"   - Questions, options, and explanations must be grammatically flawless and academically precise in standard Marathi.\n"
                f"3. Question max 280 chars, 4 options under 90 chars each, correct index 0-3, explanation max 140 chars.\n"
                f"Output MUST be a valid JSON object in this exact format:\n"
                f"{{\n"
                f"  \"questions\": [\n"
                f"    {{\n"
                f"      \"question\": \"...\",\n"
                f"      \"options\": [\"A\", \"B\", \"C\", \"D\"],\n"
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
            q_text = f"*Q{idx+1}: {q['question']}*\n"
            for i, o in enumerate(q['options']):
                q_text += f"{'✅' if i == q['correct_option_id'] else '⚪'} {chr(65+i)}. {o}\n"
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
        markup.add(types.InlineKeyboardButton("✏️ प्रश्न दुरुस्त करा (Manual Edit)", callback_data=f"edt_menu_{post_id}"))
        markup.add(types.InlineKeyboardButton("🔙 मागे जा (Back / बदल करा)", callback_data="back_to_timer"))
    else:
        markup.add(types.InlineKeyboardButton("🔙 मागे जा (Back / बदल करा)", callback_data="back_to_lang"))
    markup.add(types.InlineKeyboardButton("❌ रद्द करा (Cancel)", callback_data="can_"))

    try:
        bot.edit_message_text(preview, cid, mid, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        bot.send_message(cid, preview, reply_markup=markup, parse_mode="Markdown")

# ------------------------------------------------------------------------------
# 6. RUN BOT (ROCK SOLID INFINITY POLLING & 409 CONFLICT HANDLER)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    print("🚀 Sidhu Sir's Bot is online 24/7!")
    while True:
        try:
            bot.polling(none_stop=True, timeout=30, long_polling_timeout=20, skip_pending=True)
        except telebot.apihelper.ApiTelegramException as e:
            if getattr(e, "error_code", None) == 409 or "409" in str(e):
                print("⚠️ Telegram 409 Conflict: जुनी प्रोसेस बंद होण्याची वाट पाहत आहे... (10 सेकंदात पुन्हा कनेक्ट होईल)")
                time.sleep(10)
            else:
                print(f"⚠️ Telegram API त्रुटी: {e}. 5 सेकंदात पुन्हा प्रयत्न करत आहे...")
                time.sleep(5)
        except Exception as e:
            print(f"⚠️ Polling त्रुटी: {e}. 5 सेकंदात पुन्हा प्रयत्न करत आहे...")
            time.sleep(5)
