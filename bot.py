"""
Sidhu Sir's Multi-Channel AI Quiz & Content Bot (Groq LPU Engine)
================================================================
Compact, ultra-reliable, zero-truncation version.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import logging
import os
import re
import threading
import time
import telebot
from telebot import types
import requests

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
# 2. GROQ AI ENGINE
# ------------------------------------------------------------------------------
def ask_groq(prompt: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY.strip()}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are a senior UPSC & MPSC paper setter. Always output strictly formatted exam material."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5,
        "max_tokens": 2048
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=35)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"]
    raise Exception(f"AI Error {resp.status_code}: {resp.text}")

def parse_json_mcqs(text: str) -> list:
    clean = re.sub(r"```json\s*", "", text)
    clean = re.sub(r"```\s*$", "", clean).strip()
    match = re.search(r"(\[.*\]|\{.*\})", clean, re.DOTALL)
    data = json.loads(match.group(1) if match else clean)
    return data if isinstance(data, list) else [data]

# ------------------------------------------------------------------------------
# 3. BOT COMMANDS & TOPIC INPUT
# ------------------------------------------------------------------------------
@bot.message_handler(commands=['start', 'help'])
def start_cmd(msg):
    text = (
        "🚀 *Sidhu Sir's Ultimate Quiz & Content Bot Active!*\n\n"
        "1. 📊 **Quiz Poll** (४ पर्यायांचे प्रश्न)\n"
        "2. 💡 **Mnemonic Trick** (लक्षात ठेवण्याच्या शॉर्ट ट्रिक्स)\n"
        "3. 📌 **Quick Notes** (१ मिनिट रिव्हिजन नोट्स)\n\n"
        "👉 **वापरण्यासाठी:** कोणताही विषय टाईप करून पाठवा!"
    )
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: True, content_types=['text'])
def handle_topic(msg):
    topic = msg.text.strip()
    if not topic or topic.startswith('/'):
        return
    user_sessions[msg.chat.id] = {"topic": topic}
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📊 Quiz Poll (प्रश्न)", callback_data="fmt_quiz"),
        types.InlineKeyboardButton("💡 Mnemonic (शॉर्टकट ट्रिक)", callback_data="fmt_mnemonic"),
        types.InlineKeyboardButton("📌 Quick Notes (रिव्हिजन नोट्स)", callback_data="fmt_notes")
    )
    bot.reply_to(msg, f"📝 **विषय:** `{topic}`\n\n👇 **काय तयार करायचे आहे?**", reply_markup=markup, parse_mode="Markdown")

# ------------------------------------------------------------------------------
# 4. INTERACTIVE MENUS & GENERATION
# ------------------------------------------------------------------------------
@bot.callback_query_handler(func=lambda call: True)
def handle_cb(call):
    cid = call.message.chat.id
    mid = call.message.message_id
    sess = user_sessions.get(cid, {})

    # Step 1: Format Chosen -> Choose Channel
    if call.data.startswith("fmt_"):
        sess["fmt"] = call.data.replace("fmt_", "")
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
        bot.edit_message_text("👇 **कोणत्या चॅनेलवर पोस्ट करायचे आहे?**", cid, mid, reply_markup=markup, parse_mode="Markdown")

    # Step 2: Channel Chosen -> Level (for Quiz) or Lang (for Notes)
    elif call.data.startswith("ch_"):
        sess["ch"] = call.data.replace("ch_", "")
        if sess["fmt"] == "quiz":
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("👑 UPSC Latest", callback_data="lvl_upsc"),
                types.InlineKeyboardButton("🏛️ MPSC राज्यसेवा", callback_data="lvl_rajyaseva")
            )
            markup.add(
                types.InlineKeyboardButton("🎯 MPSC Combine", callback_data="lvl_combine"),
                types.InlineKeyboardButton("👮 पोलीस भरती/सरळसेवा", callback_data="lvl_bharti")
            )
            bot.edit_message_text("👇 **परीक्षेचा स्तर (Level) निवडा:**", cid, mid, reply_markup=markup, parse_mode="Markdown")
        else:
            show_lang_options(cid, mid)

    # Step 3: Level Chosen -> Lang
    elif call.data.startswith("lvl_"):
        sess["lvl"] = call.data.replace("lvl_", "")
        show_lang_options(cid, mid)

    # Step 4: Lang Chosen -> Count (for Quiz) or Run (for Notes)
    elif call.data.startswith("lng_"):
        sess["lang"] = call.data.replace("lng_", "")
        if sess["fmt"] == "quiz":
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("⚡ १ प्रश्न", callback_data="cnt_1"),
                types.InlineKeyboardButton("🔥 ५ प्रश्न", callback_data="cnt_5")
            )
            markup.add(
                types.InlineKeyboardButton("🏆 १० प्रश्न", callback_data="cnt_10"),
                types.InlineKeyboardButton("🚀 २५ प्रश्न", callback_data="cnt_25")
            )
            bot.edit_message_text("👇 **किती प्रश्न तयार करायचे आहेत?**", cid, mid, reply_markup=markup, parse_mode="Markdown")
        else:
            run_content_generation(cid, mid, sess)

    # Step 5: Count Chosen -> Run
    elif call.data.startswith("cnt_"):
        sess["cnt"] = int(call.data.replace("cnt_", ""))
        run_content_generation(cid, mid, sess)

    # Step 6: Publish
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
            brand = "\n\n🎯 Join: @sidhu_sir_official"
            for i, q in enumerate(quizzes):
                exp = q["explanation"]
                if len(exp) + len(brand) <= 200:
                    exp += brand
                bot.send_poll(
                    chat_id=target_id,
                    question=f"[{i+1}/{len(quizzes)}] {q['question']}" if len(quizzes) > 1 else q['question'],
                    options=q["options"],
                    type="quiz",
                    correct_option_id=q["correct_option_id"],
                    explanation=exp,
                    is_anonymous=True,
                    open_period=45
                )
                time.sleep(2.5)
        else:
            content = item["data"] + "\n\n━━━━━━━━━━━━━━━\n📢 **अधिक तयारीसाठी जॉईन करा:** @sidhu_sir_official"
            bot.send_message(target_id, content, parse_mode="Markdown")

        bot.send_message(cid, f"🎉 **अभिनंदन!** कन्टेन्ट `{target_id}` चॅनेलवर यशस्वीरीत्या पोस्ट झाला आहे!")
        del pending_posts[post_id]

    elif call.data.startswith("can_"):
        bot.edit_message_text("❌ रद्द करण्यात आले.", cid, mid)

def show_lang_options(cid, mid):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🌐 Bilingual (मराठी + English)", callback_data="lng_bilingual"),
        types.InlineKeyboardButton("🚩 फक्त शुद्ध मराठी", callback_data="lng_marathi"),
        types.InlineKeyboardButton("🇬🇧 Only English", callback_data="lng_english")
    )
    bot.edit_message_text("👇 **कोणत्या भाषेत कन्टेन्ट हवा आहे?**", cid, mid, reply_markup=markup, parse_mode="Markdown")

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
                f"Subject: {ch_info['sub']}. Exam: {sess.get('lvl', 'UPSC')}. Language: {lang_str}.\n"
                f"Create {cnt} MCQs on: '{topic}'.\n"
                f"RULES: Question max 280 chars, 4 options under 90 chars each, correct index 0-3, explanation max 140 chars.\n"
                f"Return ONLY JSON array:\n"
                f"[{{\"question\":\"...\",\"options\":[\"...\",\"...\",\"...\",\"...\"],\"correct_option_id\":0,\"explanation\":\"...\"}}]"
            )
            raw = ask_groq(prompt)
            data = parse_json_mcqs(raw)
            pending_posts[post_id] = {"type": "quiz", "channel_id": ch_info["id"], "data": data}
            
            q1 = data[0]
            preview = f"📋 *Quiz Preview (Total: {len(data)})*\n🎯 *Target:* `{ch_info['id']}`\n\n*Q1:* {q1['question']}\n\n"
            for i, o in enumerate(q1['options']):
                preview += f"{'✅' if i == q1['correct_option_id'] else '⚪'} {chr(65+i)}. {o}\n"
            preview += f"\n💡 *Explanation:* {q1['explanation']}"

        elif fmt == "mnemonic":
            prompt = f"Create a memorable MNEMONIC / SHORT TRICK in {lang_str} for subject '{ch_info['sub']}' on topic '{topic}'. Use emojis, bold text, clear breakdown."
            text = ask_groq(prompt)
            pending_posts[post_id] = {"type": "mnemonic", "channel_id": ch_info["id"], "data": text}
            preview = f"📋 *Mnemonic Preview*\n🎯 *Target:* `{ch_info['id']}`\n\n{text}"

        else: # notes
            prompt = f"Create a 1-Minute Quick Revision Note in {lang_str} for '{ch_info['sub']}' on topic '{topic}'. 4-5 high-yield bullet points with emojis, key articles/facts, and exam traps."
            text = ask_groq(prompt)
            pending_posts[post_id] = {"type": "notes", "channel_id": ch_info["id"], "data": text}
            preview = f"📋 *Quick Notes Preview*\n🎯 *Target:* `{ch_info['id']}`\n\n{text}"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 चॅनलवर पोस्ट करा", callback_data=f"pub_{post_id}"))
        markup.add(types.InlineKeyboardButton("❌ रद्द करा", callback_data="can_"))
        bot.edit_message_text(preview, cid, mid, reply_markup=markup, parse_mode="Markdown")

    except Exception as e:
        bot.edit_message_text(f"❌ त्रुटी: {str(e)}", cid, mid)

# ------------------------------------------------------------------------------
# 5. RUN BOT (ROCK SOLID INFINITY POLLING)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    print("🚀 Sidhu Sir's Bot is online 24/7!")
    bot.infinity_polling()
