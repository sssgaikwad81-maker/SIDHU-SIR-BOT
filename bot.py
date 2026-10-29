"""
Sidhu Sir's Ultimate Multi-Channel AI Bot (Strict Accuracy + Vision + PDF + Back Navigation)
=============================================================================================
Features:
1. Strict Historical Accuracy Guardrails (Mahad Satyagraha = Dr. B.R. Ambedkar, etc.).
2. Handles Text Topics, Book Page Photos (Vision AI with Qwen 3.8 27B), and PDFs.
3. 🔙 Back button navigation on every step.
4. ♾️ Normal Quiz (Permanent open) vs ⏱️ Live Test (45s Timer).
5. 📊 Quizzes, 💡 Mnemonics, 📌 Quick Notes for all 7 channels.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import io
import json
import logging
import os
import re
import threading
import time
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
# 2. DYNAMIC GROQ AI ENGINE WITH STRICT FACTUAL GUARDRAILS
# ------------------------------------------------------------------------------
cached_groq_text_model = None
cached_groq_vision_model = None

def get_active_groq_model(vision=False):
    global cached_groq_text_model, cached_groq_vision_model
    if vision and cached_groq_vision_model:
        return cached_groq_vision_model
    if not vision and cached_groq_text_model:
        return cached_groq_text_model

    headers = {"Authorization": f"Bearer {GROQ_API_KEY.strip()}"}
    try:
        r = requests.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=5)
        if r.status_code == 200:
            models = [m["id"] for m in r.json().get("data", [])]
            for m in models:
                if any(v in m.lower() for v in ["qwen", "vision", "scout"]):
                    cached_groq_vision_model = m
                    break
            for m in models:
                if not any(x in m.lower() for x in ["whisper", "guard", "embed", "tts", "safeguard"]):
                    cached_groq_text_model = m
                    break
    except Exception:
        pass

    if vision:
        return cached_groq_vision_model or "qwen/qwen3.8-27b"
    return cached_groq_text_model or "llama-3.1-8b-instant"

def ask_groq(prompt: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY.strip()}", "Content-Type": "application/json"}
    model_name = get_active_groq_model(vision=False)
    
    system_rules = (
        "You are an authoritative, senior exam paper setter for UPSC and MPSC examinations.\n"
        "STRICT FACTUAL ACCURACY RULES (CRITICAL):\n"
        "1. Never hallucinate or confuse historical figures, leaders, or events.\n"
        "2. For Maharashtra & Indian History:\n"
        "   - Mahad Satyagraha (20 March 1927), Chavdar Tale, Kalaram Temple Satyagraha (1930), Bahishkrit Hitakarini Sabha (1924), Mooknayak, and Manusmriti Dahan (25 Dec 1927) are led strictly by Dr. B.R. Ambedkar (NOT Mahatma Gandhi).\n"
        "   - Satyashodhak Samaj is Mahatma Jyotirao Phule.\n"
        "   - Rajarshi Chhatrapati Shahu Maharaj is associated with reservation in Kolhapur (1902), Satya Shodhak support, and Vedokta controversy.\n"
        "   - Salt Satyagraha / Dandi March (1930), Champaran (1917), Kheda (1918), Non-Cooperation (1920), Quit India (1942) are Mahatma Gandhi.\n"
        "   - Do NOT associate Mahatma Gandhi with Mahad Chavdar Tale Satyagraha.\n"
        "3. Every answer and explanation must cite authentic dates, places, and historical facts without error.\n"
    )
    
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_rules},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 2048
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=35)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"]
    raise Exception(f"AI Error ({model_name}): {resp.status_code} {resp.text}")

def parse_json_mcqs(text: str) -> list:
    clean = re.sub(r"```json\s*", "", text)
    clean = re.sub(r"```\s*$", "", clean).strip()
    match = re.search(r"(\[.*\]|\{.*\})", clean, re.DOTALL)
    data = json.loads(match.group(1) if match else clean)
    return data if isinstance(data, list) else [data]

# ------------------------------------------------------------------------------
# 3. INPUT HANDLERS: TEXT, PHOTO & PDF
# ------------------------------------------------------------------------------
@bot.message_handler(commands=['start', 'help'])
def start_cmd(msg):
    text = (
        "🚀 *Sidhu Sir's Ultimate Quiz & Content Bot Active!*\n\n"
        "✨ **तुम्ही काय पाठवू शकता?**\n"
        "1. 📝 **विषयाचे नाव** थेट टाईप करून पाठवा (उदा. `महाड सत्याग्रह` किंवा `Article 32`).\n"
        "2. 📸 **पुस्तकाचा फोटो** काढून पाठवा (AI पान वाचून थेट प्रश्न काढेल).\n"
        "3. 📄 **नोट्सची PDF** पाठवा (AI पीडीएफ मधील मुद्द्यांवर प्रश्न बनवेल).\n\n"
        "👉 **सुरुवात करण्यासाठी:** खाली मेसेज, फोटो किंवा PDF पाठवा!"
    )
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

# 1. Text Input
@bot.message_handler(func=lambda m: True, content_types=['text'])
def handle_text(msg):
    topic = msg.text.strip()
    if not topic or topic.startswith('/'):
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
        
        user_sessions[msg.chat.id] = {"topic": extracted_text[:1500], "source_type": "photo"}
        show_format_menu(msg.chat.id, "📖 पुस्तकाचे पान (Photo Scanned)")
    except Exception as e:
        bot.edit_message_text(f"❌ फोटो वाचताना त्रुटी: {str(e)}", msg.chat.id, status.message_id)

def extract_text_from_photo(img_bytes: bytes) -> str:
    import base64
    b64 = base64.b64encode(img_bytes).decode('utf-8')
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY.strip()}", "Content-Type": "application/json"}
    model_name = get_active_groq_model(vision=True)
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

# 3. PDF Document Input
@bot.message_handler(content_types=['document'])
def handle_doc(msg):
    fname = msg.document.file_name.lower() if msg.document.file_name else "file.pdf"
    if not fname.endswith('.pdf'):
        bot.reply_to(msg, "कृपया केवळ PDF फाईल किंवा पुस्तकाचा फोटो पाठवा.")
        return

    if pypdf is None:
        bot.reply_to(msg, "⚠️ PDF वाचण्यासाठी GitHub वरील `requirements.txt` मध्ये `pypdf` असणे आवश्यक आहे.\n\n📸 तोपर्यंत तुम्ही **पुस्तकाच्या पानाचा थेट फोटो** पाठवू शकता, AI फोटो अचूक वाचून प्रश्न बनवेल!")
        return

    status = bot.reply_to(msg, f"📄 *PDF मिळाली:* `{fname}`\nमजकूर वाचत आहे...", parse_mode="Markdown")
    try:
        file_info = bot.get_file(msg.document.file_id)
        pdf_bytes = bot.download_file(file_info.file_path)
        
        # Read text from PDF
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        extracted = ""
        for page in reader.pages[:5]:  # Read first 5 pages
            t = page.extract_text()
            if t:
                extracted += t + "\n"
                
        bot.delete_message(msg.chat.id, status.message_id)
        if not extracted.strip():
            bot.send_message(msg.chat.id, "⚠️ या PDF मधून टेक्स्ट काढता आले नाही (कदाचित ही स्कॅन केलेली इमेज PDF असावी). कृपया पानाचा थेट फोटो काढून पाठवा.")
            return

        user_sessions[msg.chat.id] = {"topic": extracted[:2000], "source_type": "pdf"}
        show_format_menu(msg.chat.id, f"📄 {fname} (PDF मधील मजकूर)")
    except Exception as e:
        bot.edit_message_text(f"❌ PDF वाचताना त्रुटी: {str(e)}", msg.chat.id, status.message_id)

def show_format_menu(cid, topic_label, mid=None):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📊 Quiz Poll (प्रश्न संच)", callback_data="fmt_quiz"),
        types.InlineKeyboardButton("💡 Mnemonic (शॉर्टकट ट्रिक)", callback_data="fmt_mnemonic"),
        types.InlineKeyboardButton("📌 Quick Notes (रिव्हिजन नोट्स)", callback_data="fmt_notes"),
        types.InlineKeyboardButton("❌ रद्द करा (Cancel)", callback_data="can_")
    )
    text = f"📝 **सामग्री:** `{topic_label[:80]}`\n\n👇 **काय तयार करायचे आहे?**"
    if mid:
        bot.edit_message_text(text, cid, mid, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(cid, text, reply_markup=markup, parse_mode="Markdown")

# ------------------------------------------------------------------------------
# 4. STEP-BY-STEP FLOW WITH BACK BUTTONS
# ------------------------------------------------------------------------------
@bot.callback_query_handler(func=lambda call: True)
def handle_cb(call):
    cid = call.message.chat.id
    mid = call.message.message_id
    sess = user_sessions.get(cid, {})

    # Step 1: Format Chosen -> Choose Channel
    if call.data.startswith("fmt_"):
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
                f"Source Topic / Material:\n'{topic}'\n\n"
                f"RULES (STRICT):\n"
                f"1. Generate exactly {cnt} MCQs strictly based on authentic historical/constitutional facts.\n"
                f"2. Ensure zero confusion between historical figures (e.g. Mahad Satyagraha is strictly Dr. B.R. Ambedkar).\n"
                f"3. Question max 280 chars, 4 options under 90 chars each, correct index 0-3, explanation max 140 chars.\n"
                f"Return ONLY valid JSON array:\n"
                f"[{{\"question\":\"...\",\"options\":[\"...\",\"...\",\"...\",\"...\"],\"correct_option_id\":0,\"explanation\":\"...\"}}]"
            )
            raw = ask_groq(prompt)
            data = parse_json_mcqs(raw)
            pending_posts[post_id] = {
                "type": "quiz",
                "channel_id": ch_info["id"],
                "data": data,
                "timer": sess.get("timer")
            }
            
            q1 = data[0]
            mode_lbl = "⏱️ ४५ सेकंद टायमर" if sess.get("timer") else "♾️ कायम चालू (Normal)"
            preview = (
                f"📋 *Quiz Preview (Total: {len(data)})*\n"
                f"🎯 *Target:* `{ch_info['id']}` | *Mode:* {mode_lbl}\n\n"
                f"*Q1:* {q1['question']}\n\n"
            )
            for i, o in enumerate(q1['options']):
                preview += f"{'✅' if i == q1['correct_option_id'] else '⚪'} {chr(65+i)}. {o}\n"
            preview += f"\n💡 *Explanation:* {q1['explanation']}"

        elif fmt == "mnemonic":
            prompt = f"Create a memorable MNEMONIC / SHORT TRICK in {lang_str} for subject '{ch_info['sub']}' on topic '{topic}'. Ensure 100% historical accuracy. Use emojis, bold text, clear breakdown."
            text = ask_groq(prompt)
            pending_posts[post_id] = {"type": "mnemonic", "channel_id": ch_info["id"], "data": text}
            preview = f"📋 *Mnemonic Preview*\n🎯 *Target:* `{ch_info['id']}`\n\n{text}"

        else: # notes
            prompt = f"Create a 1-Minute Quick Revision Note in {lang_str} for '{ch_info['sub']}' on topic '{topic}'. Ensure strict historical accuracy. 4-5 high-yield bullet points with emojis, key articles/facts, and exam traps."
            text = ask_groq(prompt)
            pending_posts[post_id] = {"type": "notes", "channel_id": ch_info["id"], "data": text}
            preview = f"📋 *Quick Notes Preview*\n🎯 *Target:* `{ch_info['id']}`\n\n{text}"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 चॅनलवर पोस्ट करा", callback_data=f"pub_{post_id}"))
        markup.add(types.InlineKeyboardButton("❌ रद्द करा (Cancel)", callback_data="can_"))
        bot.edit_message_text(preview, cid, mid, reply_markup=markup, parse_mode="Markdown")

    except Exception as e:
        bot.edit_message_text(f"❌ त्रुटी: {str(e)}", cid, mid)

# ------------------------------------------------------------------------------
# 5. RUN BOT (ROCK SOLID INFINITY POLLING)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    print("🚀 Sidhu Sir's Bot is online 24/7!")
    bot.infinity_polling()
