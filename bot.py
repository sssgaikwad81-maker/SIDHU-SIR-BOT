"""
Ultimate Multi-Channel AI Bot for Sidhu Sir's Educational Network
==================================================================
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import io
import json
import logging
import os
import threading
import time
import telebot
from telebot import types
import google.generativeai as genai
from PIL import Image

# ==============================================================================
# 0. FREE CLOUD KEEP-ALIVE SERVER (For Render Web Service)
# ==============================================================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Sidhu Sir's Quiz Bot is running live 24/7!")

    def log_message(self, format, *args):
        pass

def start_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=start_health_server, daemon=True).start()

# ==============================================================================
# 1. CONFIGURATION (Your Live Credentials)
# ==============================================================================
TELEGRAM_BOT_TOKEN = "9253804253:AAG3NaTU7O4bmwO0hznomU1NKgslOg4JgvU"
GEMINI_API_KEY = "AQ.Ab8RN6KgyFsfQFkls0DV93sjEaMvGT3mMzYH_2H2QM2ZZpHSEw"
ADMIN_USER_ID = 0

CHANNELS = {
    "upsc_polity": {
        "title": "🏛️ Polity (UPSC)",
        "id": "@polity_quiz_mcq",
        "subject": "Indian Polity, Constitution & Governance",
        "default_lang": "english",
        "default_level": "upsc"
    },
    "upsc_history": {
        "title": "📜 History (UPSC)",
        "id": "@history_quiz_mcq",
        "subject": "Ancient, Medieval, Modern Indian History, Art & Culture",
        "default_lang": "english",
        "default_level": "upsc"
    },
    "upsc_geo": {
        "title": "🌍 Geography (UPSC)",
        "id": "@geography_quiz_mcq",
        "subject": "Physical, Indian, and World Geography",
        "default_lang": "english",
        "default_level": "upsc"
    },
    "upsc_economy": {
        "title": "📈 Economy (UPSC)",
        "id": "@economy_quiz_mcq",
        "subject": "Indian Economy, Fiscal & Monetary Policies, Budget, Banking",
        "default_lang": "english",
        "default_level": "upsc"
    },
    "upsc_env": {
        "title": "🌿 Environment (UPSC)",
        "id": "@environment_quiz_mcq",
        "subject": "Ecology, Biodiversity, Climate Change, Treaties, Wildlife",
        "default_lang": "english",
        "default_level": "upsc"
    },
    "upsc_sci": {
        "title": "🔬 Science & Tech (UPSC)",
        "id": "@science_quiz_mcq",
        "subject": "Science & Tech, Space (ISRO/NASA), Defense, AI, Biotech",
        "default_lang": "english",
        "default_level": "upsc"
    },
    "mpsc_official": {
        "title": "🚩 Sidhu Sir Official (MPSC)",
        "id": "@sidhu_sir_official",
        "subject": "MPSC GS (All Subjects / General Studies)",
        "default_lang": "bilingual",
        "default_level": "combine"
    }
}

# ==============================================================================
# 2. INITIALIZATION
# ==============================================================================
logging.basicConfig(level=logging.INFO)
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)

user_sessions = {}
pending_items = {}

# ==============================================================================
# 3. AI GENERATION ENGINES
# ==============================================================================
def generate_quizzes(input_content, subject: str, exam_level: str, lang: str, count: int = 1, is_image: bool = False) -> list:
    level_map = {
        "upsc": "UPSC Civil Services Prelims Latest Pattern. Statement-based or 'How many are correct' format.",
        "rajyaseva": "MPSC State Services (Rajyaseva) Prelims. Deep conceptual multiple statements.",
        "combine": "MPSC Combined Group B & Group C Prelims. 1-2 statement or factual-analytical MCQ.",
        "bharti": "Police Bharti / Talathi / Saral Seva. Direct 1-liner factual multiple choice question."
    }
    lang_map = {
        "english": "Language: 100% English.",
        "marathi": "Language: 100% Formal Marathi (शुद्ध मराठी).",
        "bilingual": "Language: Strictly BILINGUAL (English / Marathi) for Question, Options, and Explanation."
    }

    prompt = f"""
Specialization: {subject}
Level: {level_map.get(exam_level, level_map['combine'])}
{lang_map.get(lang, lang_map['bilingual'])}

Create {count} high-quality MCQs based on the input.
STRICT LIMITS:
1. Question: Max 280 chars.
2. 4 Options: Each UNDER 90 chars.
3. Correct Index: 0, 1, 2, or 3.
4. Explanation: Max 140 chars.

Return ONLY a JSON array of objects:
[
  {{
    "question": "string",
    "options": ["string", "string", "string", "string"],
    "correct_option_id": 0,
    "explanation": "string"
  }}
]
"""
    model = genai.GenerativeModel("gemini-1.5-flash")
    if is_image:
        resp = model.generate_content([prompt, "Extract key exam points from this image:", input_content], generation_config={"response_mime_type": "application/json"})
    else:
        resp = model.generate_content(f"{prompt}\n\nInput Topic/Notes:\n{input_content}", generation_config={"response_mime_type": "application/json"})

    data = json.loads(resp.text)
    return data if isinstance(data, list) else [data]


def generate_mnemonic(input_content, subject: str, lang: str, is_image: bool = False) -> str:
    lang_text = "in Marathi" if lang == "marathi" else ("Bilingual (Marathi + English)" if lang == "bilingual" else "in English")
    prompt = f"""
You are an expert competitive exam memory coach specializing in {subject}.
Create a powerful, catchy, and memorable MNEMONIC / SHORT TRICK {lang_text} to easily remember this topic:
Input: {input_content}

Format the response beautifully for a Telegram channel post using emojis, bold text, and clear breakdown.
Structure:
💡 **विषय / Topic:** ...
🎯 **शॉर्टकट ट्रिक / Memory Trick:** ...
🔍 **डिकोडिंग / Breakdown:** ...
📚 **परीक्षेसाठी टीप / Exam Tip:** ...
"""
    model = genai.GenerativeModel("gemini-1.5-flash")
    if is_image:
        resp = model.generate_content([prompt, input_content])
    else:
        resp = model.generate_content(prompt)
    return resp.text.strip()


def generate_quick_notes(input_content, subject: str, lang: str, is_image: bool = False) -> str:
    lang_text = "in Marathi" if lang == "marathi" else ("Bilingual (Marathi + English)" if lang == "bilingual" else "in English")
    prompt = f"""
You are an expert exam educator specializing in {subject}.
Create a '1-Minute Quick Revision Note' {lang_text} on this topic:
Input: {input_content}

Format the response beautifully for Telegram with bold headers, bullet points, and relevant emojis.
Structure:
📌 **१ मिनिट रिव्हिजन / Quick Concept:** (Topic Name)
🔹 **महत्त्वाचे मुद्दे / Key Points:** (4-5 crisp, high-yield bullet points)
⚖️ **महत्त्वाची कलमे / वर्षे / तथ्ये (Key Facts):** ...
⚠️ **अपवाद किंवा ट्रिकी पॉईंट (Exam Trap to avoid):** ...
"""
    model = genai.GenerativeModel("gemini-1.5-flash")
    if is_image:
        resp = model.generate_content([prompt, input_content])
    else:
        resp = model.generate_content(prompt)
    return resp.text.strip()


# ==============================================================================
# 4. TELEGRAM HANDLERS
# ==============================================================================
def is_admin(user_id: int) -> bool:
    return ADMIN_USER_ID == 0 or user_id == ADMIN_USER_ID


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if not is_admin(message.from_user.id):
        return

    text = (
        "🚀 *Sidhu Sir's Ultimate Content & Quiz Bot Active!*\n\n"
        "✨ **तुम्ही काय काय पोस्ट करू शकता?**\n"
        "1. 📊 **Quiz Poll:** ४ पर्यायांचे प्रश्न (टायमर आणि स्पष्टीकरणासह)\n"
        "2. 💡 **Mnemonic Trick:** लक्षात ठेवण्याच्या सोप्या शॉर्टकट ट्रिक्स\n"
        "3. 📌 **Quick Revision Notes:** १ मिनिटांत वाचता येतील अशा सुटसुटीत नोट्स\n\n"
        "👉 **कसे सुरू करायचे?**\n"
        "कोणताही विषय पाठवा किंवा पुस्तकाचा फोटो पाठवा!"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text_input(message):
    if not is_admin(message.from_user.id):
        return

    topic = message.text.strip()
    if not topic or topic.startswith('/'):
        return

    user_sessions[message.chat.id] = {"type": "text", "data": topic}
    show_format_selection_menu(message.chat.id, f"📝 **विषय:** `{topic}`")


@bot.message_handler(content_types=['photo'])
def handle_photo_input(message):
    if not is_admin(message.from_user.id):
        return

    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    image = Image.open(io.BytesIO(downloaded_file))

    user_sessions[message.chat.id] = {"type": "photo", "data": image}
    show_format_selection_menu(message.chat.id, "📸 **पुस्तकाचा फोटो मिळाला!**")


def show_format_selection_menu(chat_id: int, heading: str):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📊 Quiz Poll (प्रश्न संच)", callback_data="fmt_quiz"),
        types.InlineKeyboardButton("💡 Mnemonic (स्मरण युक्ती / शॉर्टकट ट्रिक)", callback_data="fmt_mnemonic"),
        types.InlineKeyboardButton("📌 Quick Revision Notes (१ मिनिट रिव्हिजन नोट्स)", callback_data="fmt_notes")
    )
    bot.send_message(chat_id, f"{heading}\n\n👇 **तुम्हाला काय तयार करायचे आहे?**", reply_markup=markup, parse_mode="Markdown")


def show_channel_menu(chat_id: int, message_id: int):
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
    bot.edit_message_text("👇 **कोणत्या चॅनेलवर पोस्ट करायचे आहे?**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    session = user_sessions.get(chat_id, {})

    if call.data.startswith("fmt_"):
        session["format"] = call.data.replace("fmt_", "")
        show_channel_menu(chat_id, call.message.message_id)

    elif call.data.startswith("ch_"):
        channel_key = call.data.replace("ch_", "")
        session["channel_key"] = channel_key

        if session["format"] == "quiz":
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("👑 UPSC Latest Pattern", callback_data="lvl_upsc"),
                types.InlineKeyboardButton("🏛️ MPSC राज्यसेवा (Deep)", callback_data="lvl_rajyaseva")
            )
            markup.add(
                types.InlineKeyboardButton("🎯 MPSC Combine (B & C)", callback_data="lvl_combine"),
                types.InlineKeyboardButton("👮 पोलीस भरती / सरळसेवा", callback_data="lvl_bharti")
            )
            bot.edit_message_text("👇 **परीक्षेचा स्तर (Level) निवडा:**", chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        else:
            show_language_menu(chat_id, call.message.message_id)

    elif call.data.startswith("lvl_"):
        session["level"] = call.data.replace("lvl_", "")
        show_language_menu(chat_id, call.message.message_id)

    elif call.data.startswith("lng_"):
        session["lang"] = call.data.replace("lng_", "")

        if session["format"] == "quiz":
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("⚡ १ प्रश्न", callback_data="cnt_1"),
                types.InlineKeyboardButton("🔥 ५ प्रश्न", callback_data="cnt_5")
            )
            markup.add(
                types.InlineKeyboardButton("🏆 १० प्रश्न", callback_data="cnt_10"),
                types.InlineKeyboardButton("🚀 २५ प्रश्न", callback_data="cnt_25")
            )
            bot.edit_message_text("👇 **एका वेळी किती प्रश्न तयार करायचे आहेत?**", chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        else:
            trigger_content_generation(chat_id, call.message.message_id, session)

    elif call.data.startswith("cnt_"):
        session["count"] = int(call.data.replace("cnt_", ""))
        trigger_content_generation(chat_id, call.message.message_id, session)

    elif call.data.startswith("pub_"):
        item_id = call.data.replace("pub_", "")
        if item_id not in pending_items:
            bot.answer_callback_query(call.id, "हा कन्टेन्ट कालबाह्य झाला आहे.")
            return

        item = pending_items[item_id]
        channel_id = item["channel_id"]

        bot.edit_message_text(f"🚀 `{channel_id}` वर पोस्ट होत आहे...", chat_id, call.message.message_id, parse_mode="Markdown")

        if item["type"] == "quiz":
            quizzes = item["data"]
            branding = "\n\n🎯 Join: @sidhu_sir_official"
            for idx, q in enumerate(quizzes):
                exp = q["explanation"]
                if len(exp) + len(branding) <= 200:
                    exp += branding
                bot.send_poll(
                    chat_id=channel_id,
                    question=f"[{idx+1}/{len(quizzes)}] {q['question']}" if len(quizzes) > 1 else q['question'],
                    options=q["options"],
                    type="quiz",
                    correct_option_id=q["correct_option_id"],
                    explanation=exp,
                    is_anonymous=True,
                    open_period=45
                )
                time.sleep(2.5)
        else:
            content_text = item["data"] + "\n\n━━━━━━━━━━━━━━━\n📢 **अधिक तयारीसाठी जॉईन करा:** @sidhu_sir_official"
            bot.send_message(channel_id, content_text, parse_mode="Markdown")

        bot.send_message(chat_id, f"🎉 **यशस्वी!** कन्टेन्ट `{channel_id}` चॅनेलवर पोस्ट झाला आहे!")
        del pending_items[item_id]

    elif call.data.startswith("cancel_"):
        item_id = call.data.replace("cancel_", "")
        if item_id in pending_items:
            del pending_items[item_id]
        bot.edit_message_text("❌ रद्द करण्यात आले.", chat_id, call.message.message_id)


def show_language_menu(chat_id: int, message_id: int):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🌐 Bilingual (मराठी + English)", callback_data="lng_bilingual"),
        types.InlineKeyboardButton("🚩 फक्त शुद्ध मराठी", callback_data="lng_marathi"),
        types.InlineKeyboardButton("🇬🇧 Only English", callback_data="lng_english")
    )
    bot.edit_message_text("👇 **कोणत्या भाषेत कन्टेन्ट हवा आहे?**", chat_id, message_id, reply_markup=markup, parse_mode="Markdown")


def trigger_content_generation(chat_id: int, message_id: int, session: dict):
    conf = CHANNELS[session["channel_key"]]
    fmt = session["format"]
    lang = session["lang"]
    is_image = (session["type"] == "photo")

    bot.edit_message_text(f"⏳ AI द्वारे **{fmt.upper()}** तयार होत आहे...\nकृपया थांबा...", chat_id, message_id, parse_mode="Markdown")

    try:
        item_id = str(message_id)
        if fmt == "quiz":
            quizzes = generate_quizzes(session["data"], conf["subject"], session["level"], lang, session["count"], is_image)
            pending_items[item_id] = {"type": "quiz", "channel_id": conf["id"], "data": quizzes}

            q1 = quizzes[0]
            preview = f"📋 *Quiz Preview (Total: {len(quizzes)})*\n🎯 *Target:* `{conf['id']}`\n\n*Q1:* {q1['question']}\n\n"
            for i, opt in enumerate(q1['options']):
                preview += f"{'✅' if i == q1['correct_option_id'] else '⚪'} {chr(65+i)}. {opt}\n"
            preview += f"\n💡 *Explanation:* {q1['explanation']}"
        elif fmt == "mnemonic":
            text = generate_mnemonic(session["data"], conf["subject"], lang, is_image)
            pending_items[item_id] = {"type": "mnemonic", "channel_id": conf["id"], "data": text}
            preview = f"📋 *Mnemonic Preview*\n🎯 *Target:* `{conf['id']}`\n\n{text}"
        else:
            text = generate_quick_notes(session["data"], conf["subject"], lang, is_image)
            pending_items[item_id] = {"type": "notes", "channel_id": conf["id"], "data": text}
            preview = f"📋 *Quick Notes Preview*\n🎯 *Target:* `{conf['id']}`\n\n{text}"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 चॅनलवर पोस्ट करा", callback_data=f"pub_{item_id}"))
        markup.add(types.InlineKeyboardButton("❌ रद्द करा", callback_data=f"cancel_{item_id}"))

        bot.edit_message_text(preview, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

    except Exception as e:
        bot.edit_message_text(f"❌ त्रुटी: {str(e)}", chat_id, message_id)


# ==============================================================================
# 5. RUN
# ==============================================================================
if __name__ == "__main__":
    print("🚀 Sidhu Sir's Ultimate Multi-Channel Bot Running...")
    bot.infinity_polling()
