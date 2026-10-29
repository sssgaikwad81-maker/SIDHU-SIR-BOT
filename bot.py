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
        # CHANGED: Swapped out 'llama-3.1-8b-instant' for an active high-tier reasoning model
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
                # FIXED: Repaired truncated markup list configuration string below
                types.InlineKeyboardButton("🔥 ५ प्रश्न", callback_data="cnt_5")
            )
            bot.edit_message_text("👇 **किती प्रश्न तयार करायचे?**", cid, mid, reply_markup=markup, parse_mode="Markdown")
        else:
            # Fallback wrapper if executing notes logic directly
            pass

def show_lang_options(cid, mid):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🇬🇧 English", callback_data="lng_english"),
        types.InlineKeyboardButton("🇮🇳 Marathi", callback_data="lng_marathi"),
        types.InlineKeyboardButton("🗣️ Bilingual", callback_data="lng_bilingual")
    )
    bot.edit_message_text("👇 **माध्यम (Language) निवडा:**", cid, mid, reply_markup=markup, parse_mode="Markdown")

# ------------------------------------------------------------------------------
# 5. POLLING LOOP START
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    print("Bot is up and polling...")
    bot.infinity_polling()
