"""
Sidhu Sir's Ultimate Multi-Channel AI Bot (Exact Statement Parser + Smart Two-Part Detection + 50-Page Support)
=================================================================================================================
Features:
1. 🎯 Flawless Document MCQ Parser:
   - Statements 1, 2, 3, 4 and (अ), (ब), (क) are NEVER eaten or truncated as options.
   - All statements stay inside the question 100% intact!
2. 💡 Smart Two-Part vs Direct Poll Detection:
   - Direct 1-liner questions (e.g. Ballon d'Or, awards, dates) post directly as clean single polls (NO fake statements!).
   - Multi-statement analytical questions post as Two-Part Cards (Question Card + Poll).
3. 📚 Large File Support (Up to 50 Pages / 300,000 characters):
   - As-Is PYQ extractor parses 50-100+ questions in 0.05 seconds with zero token errors.
   - Blocked tiny models like allam-2-7b to prevent 'Please reduce length' 400 errors.
4. 🏛️ UPSC vs 🚩 MPSC Exact Numbering:
   - UPSC: Statements 1., 2., 3. | Options (a), (b), (c), (d)
   - MPSC राज्यसेवा: Statements (अ), (ब), (क) | Options १), २), ३), ४)
   - MPSC Combine: Statements (अ), (ब) | Options १), २), ३), ४)
   - पोलीस भरती: Direct 1-liner | Options १), २), ३), ४)
5. 🚀 Bulk 50/100+ Question Support with Live Progress Tracker.
6. ⚡ Non-blocking Asynchronous Background Posting.
7. ⏱️ Active Render Self-Ping Keep-Alive Thread.
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

def keep_render_awake():
    """Pings Render public URL every 4 minutes to prevent Free Web Service from sleeping."""
    time.sleep(30)
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://sidhu-sir-bot.onrender.com")
    while True:
        try:
            requests.get(render_url, timeout=10)
        except Exception:
            pass
        time.sleep(240)

threading.Thread(target=run_health_server, daemon=True).start()
threading.Thread(target=keep_render_awake, daemon=True).start()

# ------------------------------------------------------------------------------
# 1. CREDENTIALS & CHANNELS
# ------------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = "9253804253:AAG3NaTU704bmw00hznomU1NKgsl0g4JgvU"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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").strip()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

CHANNELS = {
    "upsc_polity": {"title": "🏛️ Polity (UPSC)", "id": "@polity_quiz_mcq", "sub": "Indian Polity & Constitution", "lang": "English", "lvl": "upsc"},
    "upsc_history": {"title": "📜 History (UPSC)", "id": "@history_quiz_mcq", "sub": "Indian History & Culture", "lang": "English", "lvl": "upsc"},
    "upsc_geo": {"title": "🌍 Geography (UPSC)", "id": "@geography_quiz_mcq", "sub": "Geography & Environment", "lang": "English", "lvl": "upsc"},
    "upsc_economy": {"title": "📈 Economy (UPSC)", "id": "@economy_quiz_mcq", "sub": "Economy & Budget", "lang": "English", "lvl": "upsc"},
    "upsc_env": {"title": "🌿 Environment (UPSC)", "id": "@environment_quiz_mcq", "sub": "Ecology & Wildlife", "lang": "English", "lvl": "upsc"},
    "upsc_sci": {"title": "🔬 Science & Tech (UPSC)", "id": "@science_quiz_mcq", "sub": "Science, Space & Tech", "lang": "English", "lvl": "upsc"},
    "mpsc_official": {"title": "🚩 Sidhu Sir Official (MPSC)", "id": "@sidhu_sir_official", "sub": "MPSC GS All Subjects", "lang": "Bilingual", "lvl": "combine"},
    "vachal_tar_vachal": {"title": "📖 वाचाल तर वाचाल", "id": "@Vachal_Tar_Vachal", "sub": "प्रबोधन व वाचन चळवळ", "lang": "Marathi", "lvl": "combine"},
    "ebooks_lab": {"title": "📚 eBooks Lab", "id": "@eBooks_Lab", "sub": "ई-पुस्तके व अभ्यास साहित्य", "lang": "Marathi", "lvl": "combine"}
}

logging.basicConfig(level=logging.INFO)
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
user_sessions = {}
pending_posts = {}

# ------------------------------------------------------------------------------
# 2. BULLETPROOF GROQ AI ENGINE WITH VERIFIED 128K MODELS ONLY
# ------------------------------------------------------------------------------
KNOWN_TEXT_MODELS = [
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile"
]

KNOWN_VISION_MODELS = [
    "llama-3.2-11b-vision-preview",
    "llama-3.2-90b-vision-preview",
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

    # Priority 1: Match against verified 128k context flagship models
    for m in KNOWN_TEXT_MODELS:
        if m in available and m not in candidates:
            candidates.append(m)

    # Priority 2: Other large models (STRICTLY filter out allam, orpheus, whisper, guard)
    for m in available:
        m_low = m.lower()
        if any(ok in m_low for ok in ["gpt-oss", "qwen", "llama-3.3"]):
            if not any(bad in m_low for bad in ["whisper", "guard", "embed", "tts", "safeguard", "orpheus", "canopy", "allam"]):
                if m not in candidates:
                    candidates.append(m)

    if not candidates:
        candidates = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b", "openai/gpt-oss-120b"]

    return candidates

def get_vision_candidates():
    available = get_available_groq_models()
    candidates = []
    for m in KNOWN_VISION_MODELS:
        if m in available:
            candidates.append(m)
    for m in available:
        m_low = m.lower()
        if ("vision" in m_low or "scout" in m_low) and not any(b in m_low for b in ["guard", "whisper", "qwen"]):
            if m not in candidates:
                candidates.append(m)
    if not candidates:
        candidates = ["llama-3.2-11b-vision-preview", "llama-3.2-90b-vision-preview", "meta-llama/llama-4-scout-17b-16e-instruct"]
    return candidates

def get_vision_model():
    cands = get_vision_candidates()
    return cands[0] if cands else "llama-3.2-11b-vision-preview" 

def ask_gemini_vision(img_bytes: bytes, prompt: str) -> str:
    """Calls Google Gemini 1.5 Flash Vision - world gold-standard for Marathi OCR (100% free with GEMINI_API_KEY)."""
    if not GEMINI_API_KEY:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    import base64
    b64 = base64.b64encode(img_bytes).decode('utf-8')
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": b64
                    }
                }
            ]
        }]
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=35)
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    txt = parts[0].get("text", "")
                    if txt and txt.strip():
                        return txt.strip()
        else:
            logging.warning(f"Gemini Vision HTTP {resp.status_code}: {resp.text[:120]}")
    except Exception as e:
        logging.warning(f"Gemini Vision exception: {e}")
    return None

def is_ai_refusal(text: str) -> bool:
    """Detects canned AI refusals like 'I\'m sorry, but I can\'t help with that.' so the bot auto-falls back to Groq."""
    if not text:
        return True
    low = text.strip().lower()
    refusal_phrases = [
        "i'm sorry, but i can't help with that",
        "i cannot help with that",
        "i am unable to help",
        "i am sorry, but i cannot",
        "i cannot fulfill this request",
        "i'm unable to assist"
    ]
    if any(p in low for p in refusal_phrases):
        return True
    if len(low) < 100 and "sorry" in low and ("cannot" in low or "can't" in low or "unable" in low):
        return True
    return False

def ask_claude(prompt: str, json_mode: bool = False, system_rules: str = "") -> str:
    """Calls Anthropic Claude 3.5 Haiku with premium Marathi/English reasoning."""
    if not ANTHROPIC_API_KEY:
        return None
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    sys_prompt = system_rules
    if json_mode:
        sys_prompt += "\nIMPORTANT: Output strictly a valid, raw JSON object matching the requested schema. Do not include markdown codeblocks or conversational text."
    
    payload = {
        "model": "claude-3-5-haiku-20241022",
        "max_tokens": 4096,
        "temperature": 0.2,
        "system": sys_prompt,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=50)
        if resp.status_code == 200:
            data = resp.json()
            content_blocks = data.get("content", [])
            if content_blocks and len(content_blocks) > 0:
                txt = content_blocks[0].get("text", "")
                if txt and txt.strip():
                    return txt
            logging.warning(f"Claude empty response: {resp.text}")
        else:
            logging.warning(f"Claude API HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        logging.warning(f"Claude request error: {e}")
    return None

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
        "4. DO NOT INVENT FAKE STATEMENTS:\n"
        "   - If a question is a direct factual question (e.g. awards, sports, appointments, dates, books), keep it as a clean 1-liner question with 4 direct options!\n"
        "   - NEVER create fake (अ) and (ब) statements for direct questions.\n"
        "   - Only use multi-statements when the subject genuinely requires analytical evaluation.\n"
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
    # Normalize inline statement numbers like " 2. " or " 3. " or "(अ)"
    t = re.sub(r"(?<=[^\n])\s*(\([अ-हa-dA-D]\))\s*", r"\n\1 ", t)
    t = re.sub(r"(?<=[^\n])\s*(\b[1-4]\.)\s*", r"\n\1 ", t)
    t = re.sub(r"(?<=[^\n])\s*(Statement[- ][I|V|X\d]+[:\.])\s*", r"\n\1 ", t, flags=re.IGNORECASE)
    # Question conclusion line
    t = re.sub(r"(?<=[^\n])\s*(खालीलपैकी|Which of the statements|वरीलपैकी|Select the correct|Arrange the following)\s*", r"\n\n\1 ", t, flags=re.IGNORECASE)
    # Cleanup extra lines
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t

def format_notes_for_telegram(text: str) -> str:
    """Converts notes with '>■' to native Telegram HTML <blockquote> cards so they render with the beautiful pinkish shaded box, vertical line, and quote mark."""
    lines = text.strip().split("\n")
    html_lines = []
    in_quote = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(">"):
            if not in_quote:
                html_lines.append("<blockquote>")
                in_quote = True
            content = stripped.lstrip(">").strip()
            # Clean duplicate bullets
            content = re.sub(r"^[•\-\*\■]\s*", "■ ", content)
            if not content.startswith("■"):
                content = "■ " + content
            # Convert **bold** to <b>bold</b>
            content = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", content)
            html_lines.append(content)
        else:
            if in_quote:
                html_lines.append("</blockquote>")
                in_quote = False
            content = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
            html_lines.append(content)
    if in_quote:
        html_lines.append("</blockquote>")
    return "\n".join(html_lines)

def is_multi_statement_card(q: dict) -> bool:
    """Determines if a question requires a Two-Part Card. Prevents any question text from being cut off at Telegram's 300 char poll limit."""
    q_text = q.get("question", "").strip()
    options = q.get("options", [])

    # If question text alone exceeds 230 characters, it MUST be a Two-Part Card so Telegram NEVER truncates it!
    if len(q_text) > 230:
        return True

    is_combo_opt = any(
        any(k in opt for k in ["फक्त", "आणि", "दोन्ही", "सर्व", "यांपैकी", "only", "Both", "Neither", "(अ)", "(ब)", "Only one"])
        for opt in options
    )
    has_statements = any(st in q_text for st in ["\n(अ)", "\n(ब)", "\n1.", "\n2.", "खालील विधाने", "Consider the following", "Arrange the following", "कालानुक्रम"])
    return bool((has_statements or is_combo_opt) and len(q_text) > 150)

def standardize_mcq_for_exam(q: dict, lvl: str) -> dict:
    """Strictly guarantees MPSC numbering: statements (अ), (ब), (क) and options १), २), ३), ४)
    and UPSC numbering: statements 1., 2., 3. and options (a), (b), (c), (d)."""
    question = q.get("question", "").strip()
    options = list(q.get("options", []))[:4]

    is_upsc = (lvl == "upsc")
    is_mpsc = (lvl in ["rajyaseva", "combine"])

    # 1. Standardize statements in question
    if is_mpsc:
        mpsc_map = {"a": "अ", "b": "ब", "c": "क", "d": "ड", "A": "अ", "B": "ब", "C": "क", "D": "ड"}
        for eng_l, mar_l in mpsc_map.items():
            question = re.sub(rf"\({eng_l}\)", f"({mar_l})", question)
            question = re.sub(rf"(?:^|\n)\s*{eng_l}\.\s*", f"\n({mar_l}) ", question)
    elif is_upsc:
        mar_to_digit = {"(अ)": "1.", "(ब)": "2.", "(क)": "3.", "(ड)": "4.", "(a)": "1.", "(b)": "2.", "(c)": "3.", "(d)": "4."}
        for mar_l, dig in mar_to_digit.items():
            question = question.replace(mar_l, dig)

    # 2. Standardize options numbering
    clean_options = []
    mar_digits = ["१)", "२)", "३)", "४)"]
    upsc_letters = ["(a)", "(b)", "(c)", "(d)"]

    for idx in range(4):
        opt_text = options[idx].strip() if idx < len(options) else f"पर्याय {idx+1}"
        opt_text = re.sub(r"^\([A-Da-d१-४1-4]\)\s*", "", opt_text).strip()
        opt_text = re.sub(r"^[A-Da-d१-४1-4][\.\:\)]\s*", "", opt_text).strip()

        if is_mpsc:
            mpsc_map = {"(a)": "(अ)", "(b)": "(ब)", "(c)": "(क)", "(d)": "(ड)"}
            for eng_l, mar_l in mpsc_map.items():
                opt_text = opt_text.replace(eng_l, mar_l)
            clean_options.append(f"{mar_digits[idx]} {opt_text}"[:90])
        elif is_upsc:
            clean_options.append(f"{upsc_letters[idx]} {opt_text}"[:90])
        else:
            clean_options.append(f"{mar_digits[idx]} {opt_text}"[:90])

    q["question"] = question
    q["options"] = clean_options
    return q

def extract_single_mcq_block(block: str) -> dict:
    """Robustly extracts an MCQ ensuring statements 1, 2, 3 and chronological sequences are NEVER confused with options."""
    ans_m = re.search(r"(?:\n\s*|\A)(?:[✅\*\s]*)?(?:उत्तर|Ans(?:wer)?|Correct|अचूक\s*उत्तर|योग्य\s*पर्याय|पर्याय)\s*[:\-]?\s*(?:पर्याय\s*)?[\(\[]?\s*([A-Da-d१-४1-4])\s*[\)\]]?", block, re.IGNORECASE)
    corr_idx = 0
    if ans_m:
        ch = ans_m.group(1)
        if ch in "1234":
            corr_idx = int(ch) - 1
        elif ch in "१२३४":
            corr_idx = "१२३४".index(ch)
        elif ch.upper() in "ABCD":
            corr_idx = ord(ch.upper()) - ord("A")

    exp_m = re.search(r"(?:\n\s*|\A)(?:[💡\*\s]*)?(?:स्पष्टीकरण|Explanation|Exp)\s*[:\-]?\s*(.+)", block, re.IGNORECASE | re.DOTALL)
    exp = exp_m.group(1).strip()[:140] if exp_m else "संदर्भ नोट्सनुसार अचूक उत्तर."

    main = block
    # Strip any Answer Key section from the question block so it does not pollute the last question
    ans_key_cut = re.search(r"(?:\n\s*|\A)(?:ANSWER\s*KEYS?|उत्तरपत्रिका|उत्तरांची\s*सूची|ANSWERS?|KEYS?|उत्तरसूची|अचूक\s*उत्तरे|उत्तरतालिका)\b", main, re.IGNORECASE)
    if ans_key_cut and ans_key_cut.start() > 20:
        main = main[:ans_key_cut.start()].strip()

    cut_pos = len(main)
    if ans_m and ans_m.start() > 20:
        cut_pos = min(cut_pos, ans_m.start())
    if exp_m and exp_m.start() > 20:
        cut_pos = min(cut_pos, exp_m.start())
    main = main[:cut_pos].strip()

    # Schemas: Strictly sequential 4 options!
    patterns = [
        # 1️⃣ ... 2️⃣ ... 3️⃣ ... 4️⃣ ...
        r"(?s)(.*?)(?:^|\n|\s)1️⃣\s*(.+?)(?:^|\n|\s)2️⃣\s*(.+?)(?:^|\n|\s)3️⃣\s*(.+?)(?:^|\n|\s)4️⃣\s*(.+)$",
        # [1] ... [2] ... [3] ... [4] ...
        r"(?s)(.*?)\[1\]\s*(.+?)\[2\]\s*(.+?)\[3\]\s*(.+?)\[4\]\s*(.+)$",
        # [A] ... [B] ... [C] ... [D] ...
        r"(?s)(.*?)\[[aA]\]\s*(.+?)\[[bB]\]\s*(.+?)\[[cC]\]\s*(.+?)\[[dD]\]\s*(.+)$",
        # (1) ... (2) ... (3) ... (4) ...
        r"(?s)(.*?)\(1\)\s*(.+?)\(2\)\s*(.+?)\(3\)\s*(.+?)\(4\)\s*(.+)$",
        # (a) ... (b) ... (c) ... (d) ...
        r"(?s)(.*?)\([aA]\)\s*(.+?)\([bB]\)\s*(.+?)\([cC]\)\s*(.+?)\([dD]\)\s*(.+)$",
        # (अ) ... (ब) ... (क) ... (ड) ...
        r"(?s)(.*?)\(अ\)\s*(.+?)\(ब\)\s*(.+?)\(क\)\s*(.+?)\(ड\)\s*(.+)$",
        # 1) ... 2) ... 3) ... 4) ...
        r"(?s)(.*?)(?:^|\n|\s)1\)\s*(.+?)(?:^|\n|\s)2\)\s*(.+?)(?:^|\n|\s)3\)\s*(.+?)(?:^|\n|\s)4\)\s*(.+)$",
        # १) ... २) ... ३) ... ४) ...
        r"(?s)(.*?)(?:^|\n|\s)१[\)\.]\s*(.+?)(?:^|\n|\s)२[\)\.]\s*(.+?)(?:^|\n|\s)३[\)\.]\s*(.+?)(?:^|\n|\s)४[\)\.]\s*(.+)$",
        # A. ... B. ... C. ... D. ... or A) ... B) ...
        r"(?s)(.*?)(?:^|\n|\s)[aA][\.\)]\s*(.+?)(?:^|\n|\s)[bB][\.\)]\s*(.+?)(?:^|\n|\s)[cC][\.\)]\s*(.+?)(?:^|\n|\s)[dD][\.\)]\s*(.+)$",
        # 1. ... 2. ... 3. ... 4. ... (as options)
        r"(?s)(.*?)(?:^|\n)1\.\s*(.+?)(?:^|\n)2\.\s*(.+?)(?:^|\n)3\.\s*(.+?)(?:^|\n)4\.\s*(.+)$"
    ]

    for p in patterns:
        m = re.search(p, main)
        if m:
            q_part = m.group(1).strip()
            # Strip Q 1 | UPSC 1984 or Question 1: headers cleanly
            q_clean = re.sub(r"^\s*(?:Q(?:uestion)?[\.\s]*\d+[\s\.:\)\|\-\–]*|प्रश्न\s*[\d१-९]+[\s\.:\)\|\-\–]*|\d+[\.:\)]\s*)", "", q_part, flags=re.IGNORECASE).strip()
            q_clean = re.sub(r"^(?:(?:UPSC|MPSC|Combine|Prelims|Mains|CSAT)?\s*[\d\–\-\|\s]+\n*)+", "", q_clean, flags=re.IGNORECASE).strip()
            if len(q_clean) > 5:
                raw_opts = [m.group(i).strip()[:90] for i in range(2, 6)]
                # Clean nested option tags if any
                clean_opts = []
                for o in raw_opts:
                    o = re.sub(r"^\([A-Da-d१-४1-4]\)\s*", "", o).strip()
                    o = re.sub(r"^[A-Da-d१-४1-4][\.\:\)]\s*", "", o).strip()
                    clean_opts.append(o)
                if all(len(o) > 0 for o in clean_opts):
                    q_num_m = re.search(r'(?:Q(?:uestion)?[\.\s]*|प्रश्न\s*|\A\s*)([0-9१-९]+)', block, re.IGNORECASE)
                    parsed_q_num = None
                    if q_num_m:
                        num_str = q_num_m.group(1)
                        if any(ch in "१२३४५६७८९०" for ch in num_str):
                            mar_nums = "०१२३४५६७८९"
                            parsed_q_num = int("".join(str(mar_nums.index(c)) for c in num_str))
                        else:
                            parsed_q_num = int(num_str)

                    return {
                        "question": q_clean,
                        "options": clean_opts,
                        "correct_option_id": corr_idx if 0 <= corr_idx <= 3 else 0,
                        "explanation": exp,
                        "has_detected_answer": True if ans_m else False,
                        "has_detected_exp": True if exp_m else False,
                        "q_num": parsed_q_num
                    }
    return None

def split_document_into_question_blocks(text: str) -> list:
    """Universal Question Splitter matching ANY exam question header (Q 1 |, Q1:, Q1., Question 1, प्रश्न 1, 1., etc.) without losing or duplicating questions."""
    text = text.strip()
    if not text:
        return []

    # Strategy 1: Universal Question marker (supports Q 1 | UPSC 1984, Q 1 |, Q1:, Q1., Question 1, प्रश्न 1, etc.)
    q_pat = r"(?:\n\s*|\A)(?:Q(?:uestion)?[\.\s]*\d+[\s\.:\)\|\-\–]+|प्रश्न\s*[\d१-९]+[\s\.:\)\|\-\–]+)"
    parts = list(re.finditer(q_pat, text, flags=re.IGNORECASE))
    if len(parts) >= 2:
        blocks = []
        for i in range(len(parts)):
            start = parts[i].start()
            end = parts[i+1].start() if i + 1 < len(parts) else len(text)
            b = text[start:end].strip()
            if b:
                blocks.append(b)
        if len(blocks) >= 2:
            return blocks

    # Strategy 2: Splitting by Answer boundaries
    ans_pat = r"(?:(?:^|\n)\s*(?:Answer|Ans(?:wer)?|उत्तर|Correct)\s*[:\-]?\s*[\(\[]?[A-Da-d१-४1-4][\)\.]?.*?(?:\n|$))"
    ans_matches = list(re.finditer(ans_pat, text, flags=re.IGNORECASE))
    if len(ans_matches) >= 2:
        blocks = []
        last_idx = 0
        for m in ans_matches:
            end_pos = m.end()
            b = text[last_idx:end_pos].strip()
            if b:
                blocks.append(b)
            last_idx = end_pos
        remainder = text[last_idx:].strip()
        if remainder:
            blocks.append(remainder)
        if len(blocks) >= 2:
            return blocks

    # Strategy 3: Numbered questions preceded by double newlines: \n\n+\d+[\.:\)]
    num_q_pat = r"(?:\n\s*\n\s*|\A)\s*(\d+)[\.:\)]\s+"
    matches = list(re.finditer(num_q_pat, text))
    if len(matches) >= 2:
        blocks = []
        for i in range(len(matches)):
            start = matches[i].end()
            end = matches[i+1].start() if i + 1 < len(matches) else len(text)
            b = text[start:end].strip()
            if b:
                blocks.append(b)
        if len(blocks) >= 2:
            return blocks

    # Strategy 4: Fallback to triple/double-newline blocks
    blocks = [b.strip() for b in re.split(r"\n\s*\n\s*\n+", text) if b.strip()]
    return blocks if blocks else [text]

def parse_all_document_mcqs(text: str) -> list:
    """Extracts all MCQs from document text without dropping statements."""
    mcqs = []
    blocks = split_document_into_question_blocks(text)
    for b in blocks:
        parsed = extract_single_mcq_block(b)
        if parsed:
            mcqs.append(parsed)
    return mcqs

def extract_answer_key_dict(text: str) -> dict:
    """Extracts answer key mappings from headers, tables (including 3-column Q | Year | Ans), lists, and keys."""
    key_dict = {}
    header_pat = r"(?:ANSWER\s*KEYS?|उत्तरपत्रिका|उत्तरांची\s*सूची|ANSWERS?|KEYS?|उत्तरसूची|अचूक\s*उत्तरे|उत्तरतालिका|KEY\s*ANSWERS?)"
    m = re.search(r"(?:\n\s*|\A)" + header_pat + r"\s*[:\-]?\s*(.+)", text, re.IGNORECASE | re.DOTALL)
    if not m:
        tail = text[-4000:] if len(text) > 4000 else text
        m = re.search(header_pat + r"\s*[:\-]?\s*(.+)", tail, re.IGNORECASE | re.DOTALL)
        if not m:
            return {}

    search_text = m.group(1)

    # Format A: 3-column table format (Q \n Year \n Ans, e.g. 1 \n 1984 \n A)
    tbl_pairs = re.findall(r"([0-9१-९]+)[\s\n\t\|]+(?:(?:19|20)\d\d[\s\n\t\|]+)?([A-Da-d1-4१-४])\b", search_text)
    for q_str, ans_str in tbl_pairs:
        try:
            q_num = int(q_str)
            q_idx = q_num - 1
            if ans_str in "1234":
                c_id = int(ans_str) - 1
            elif ans_str.upper() in "ABCD":
                c_id = ord(ans_str.upper()) - ord("A")
            else:
                continue
            key_dict[q_idx] = c_id
        except Exception:
            pass

    if key_dict:
        return key_dict

    # Format B: Standard inline pairs (1. A, 1-b, 1: C, Q1 D, १-२)
    pat = r"(?:Q(?:uestion)?\s*)?([0-9१-९]+)[\s\.:\|\-\–\t]+[\(\[]?\s*([A-Da-d1-4१-४अ-ड])\s*[\)\]]?"
    pairs = re.findall(pat, search_text)

    for q_str, ans_str in pairs:
        try:
            if any(ch in "१२३४५६७८९०" for ch in q_str):
                mar_nums = "०१२३४५६७८९"
                q_num = int("".join(str(mar_nums.index(c)) for c in q_str))
            else:
                q_num = int(q_str)
            q_idx = q_num - 1

            if ans_str in "1234":
                c_id = int(ans_str) - 1
            elif ans_str in "१२३४":
                c_id = "१२३४".index(ans_str)
            elif ans_str.upper() in "ABCD":
                c_id = ord(ans_str.upper()) - ord("A")
            elif ans_str in "अकबड":
                c_id = "अकबड".index(ans_str)
            else:
                continue

            if 0 <= c_id <= 3 and q_idx >= 0:
                key_dict[q_idx] = c_id
        except Exception:
            pass

    return key_dict

def parse_plain_text_mcqs(text: str) -> list:
    return parse_all_document_mcqs(text)

def parse_solve_json(text: str) -> list:
    """Parses AI auto-solver responses with keys like answers, solutions, results."""
    if not text:
        return []
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for k in ["answers", "solutions", "results", "questions", "data", "items"]:
                if k in data and isinstance(data[k], list):
                    return data[k]
            if "correct_option_id" in data:
                return [data]
    except Exception:
        pass

    arr_m = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
    if arr_m:
        try:
            return json.loads(arr_m.group(0))
        except Exception:
            pass
    return []

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

    parsed = parse_all_document_mcqs(text)
    if parsed:
        return parsed

    raise Exception(f"AI उत्तरामधून प्रश्न काढता आले नाहीत. कृपया पुन्हा प्रयत्न करा.")

def get_batch_sizes(total_cnt, max_per_batch=15):
    """Calculates safe batch sizes for large question requests (e.g. 50, 63, 100)."""
    batches = []
    rem = total_cnt
    start = 1
    while rem > 0:
        sz = min(rem, max_per_batch)
        batches.append((start, start + sz - 1, sz))
        start += sz
        rem -= sz
    return batches

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

    # Check if user is typing custom number for instant single MCQ
    if "waiting_inst_num" in sess:
        mid = sess.pop("waiting_inst_num")
        digits = re.findall(r"\d+", topic)
        if digits:
            val = int(digits[0])
            sess["inst_num"] = val
            bot.reply_to(msg, f"🎯 **प्रश्नाचा नंबर Q{val} निश्चित केला!**")
            q_item = sess.get("direct_mcq")
            if q_item:
                show_single_mcq_instant_menu(msg.chat.id, q_item)
            return
        else:
            bot.reply_to(msg, "कृपया योग्य नंबर टाईप करा (उदा. 11, 21, 51).")
            return

    # Check if user is typing custom start offset
    if "waiting_start_offset" in sess:
        mid = sess.pop("waiting_start_offset")
        digits = re.findall(r"\d+", topic)
        if digits:
            val = int(digits[0])
            sess["start_num"] = val
            bot.reply_to(msg, f"🎯 **सुरुवातीचा नंबर निश्चित केला:** `Q{val}`")
            show_count_menu(msg.chat.id, mid)
            return
        else:
            bot.reply_to(msg, "कृपया योग्य नंबर टाईप करा (उदा. 11, 21, 51).")
            return

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
            bot.reply_to(msg, "कृपया योग्य संख्या टाईप करा (उदा. 40, 63, 100).")
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

    # Check if user manually pasted a complete single MCQ!
    detected_single = extract_single_mcq_block(topic)
    if detected_single:
        user_sessions[msg.chat.id] = {
            "topic": topic,
            "source_type": "text_mcq",
            "direct_mcq": detected_single,
            "parsed_mcqs": [detected_single],
            "total_mcqs": 1,
            "start_num": 1
        }
        show_single_mcq_instant_menu(msg.chat.id, detected_single)
        return

    user_sessions[msg.chat.id] = {"topic": topic, "source_type": "text"}
    show_format_menu(msg.chat.id, topic)

# 2. Book Photo Input (Vision AI)
@bot.message_handler(content_types=['photo'])
def handle_photo(msg):
    status = bot.reply_to(msg, "📸 *वृत्तपत्राचा फोटो मिळाला!* AI मजकूर वाचत आहे...", parse_mode="Markdown")
    try:
        file_info = bot.get_file(msg.photo[-1].file_id)
        img_bytes = bot.download_file(file_info.file_path)
        extracted_text = extract_text_from_photo(img_bytes)
        bot.delete_message(msg.chat.id, status.message_id)

        cid = msg.chat.id
        sess = user_sessions.get(cid, {})

        # If user sends multiple photos within 45 seconds, seamlessly combine them!
        now_t = time.time()
        last_t = sess.get("last_photo_time", 0)
        if sess.get("source_type") == "photo" and (now_t - last_t < 45) and "topic" in sess:
            sess["topic"] += "\n\n" + extracted_text
            sess["photo_count"] = sess.get("photo_count", 1) + 1
            sess["last_photo_time"] = now_t
            label = f"📸 {sess['photo_count']} वृत्तपत्रांचे फोटो ( एकत्र स्कॅन केले )"
            bot.send_message(cid, f"✅ *अजून १ फोटो जोडला!* (एकूण {sess['photo_count']} फोटो एकत्र केले आहेत)", parse_mode="Markdown")
        else:
            sess["topic"] = extracted_text
            sess["source_type"] = "photo"
            sess["photo_count"] = 1
            sess["last_photo_time"] = now_t
            label = "📸 वृत्तपत्राचे कात्रण (Newspaper Scan)"

        user_sessions[cid] = sess
        show_format_menu(cid, label)
    except Exception as e:
        bot.edit_message_text(f"❌ फोटो वाचताना त्रुटी: {str(e)}", msg.chat.id, status.message_id)

def extract_text_from_photo(img_bytes: bytes) -> str:
    """Compresses high-res photos to 1024px thumbnail to avoid 429 token limits, and uses Claude Vision + Groq Vision."""
    import base64
    from PIL import Image
    import io

    # 1. Resize image to 1500px max (sharp enough for tiny Marathi Devanagari font, but under 300KB)
    try:
        image = Image.open(io.BytesIO(img_bytes))
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        out_buf = io.BytesIO()
        image.save(out_buf, format="JPEG", quality=80, optimize=True)
        img_payload = out_buf.getvalue()
    except Exception:
        img_payload = img_bytes

    b64 = base64.b64encode(img_payload).decode('utf-8')

    ocr_instruction = (
        "CRITICAL OCR INSTRUCTION:\n"
        "You are an exact OCR engine for Marathi newspapers. Transcribe the ACTUAL printed Marathi text from this image VERBATIM.\n"
        "1. Read the main bold headline word-for-word exactly as written (e.g. 'राज्यातील जिल्हा परिषदांच्या निवडणुकीचा मार्ग मोकळा').\n"
        "2. Read the subheadings, boxes, commissions (e.g. बांठिया आयोग), benches (e.g. न्या. सूर्यकांत), numbers, and body text exactly as printed.\n"
        "3. DO NOT interpret, DO NOT guess, DO NOT hallucinate job recruitments (like जिल्हा न्यायाधीश भरती) or other unrelated topics!\n"
        "Output ONLY the real printed Marathi text from this newspaper image."
    )

    # 1. Try Google Gemini 1.5 Flash Vision first (World gold-standard for Marathi OCR, 100% free with GEMINI_API_KEY)
    if GEMINI_API_KEY:
        try:
            gemini_txt = ask_gemini_vision(img_payload, ocr_instruction)
            if gemini_txt and gemini_txt.strip():
                return gemini_txt.strip()
        except Exception as ge:
            logging.warning(f"Gemini Vision fallback: {ge}")

    # 2. Try Claude Vision first if ANTHROPIC_API_KEY is available (gold standard for Marathi OCR)
    if ANTHROPIC_API_KEY:
        try:
            c_url = "https://api.anthropic.com/v1/messages"
            c_headers = {
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            c_payload = {
                "model": "claude-3-5-haiku-20241022",
                "max_tokens": 2000,
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": b64
                            }
                        },
                        {
                            "type": "text",
                            "text": ocr_instruction
                        }
                    ]
                }]
            }
            c_resp = requests.post(c_url, headers=c_headers, json=c_payload, timeout=45)
            if c_resp.status_code == 200:
                c_data = c_resp.json().get("content", [])
                if c_data:
                    c_txt = c_data[0].get("text", "")
                    if c_txt and c_txt.strip():
                        return c_txt.strip()
        except Exception as ce:
            logging.warning(f"Claude Vision fallback to Groq: {ce}")

    # 3. Groq Vision with candidate model fallback
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY.strip()}", "Content-Type": "application/json"}
    candidate_vision_models = get_vision_candidates()

    last_v_err = ""
    for v_model in candidate_vision_models:
        payload = {
            "model": v_model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": ocr_instruction},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]
            }],
            "temperature": 0.1,
            "max_tokens": 2000
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=40)
            if resp.status_code == 200:
                txt = resp.json()["choices"][0]["message"]["content"]
                if txt and txt.strip():
                    return txt.strip()
            last_v_err = f"Vision API Error ({v_model}): {resp.status_code} {resp.text[:120]}"
        except Exception as ve:
            last_v_err = str(ve)
            continue

    raise Exception(last_v_err or "सर्व व्हिजन मॉडेल्स अयशस्वी झाले.")

# 3. Word Document (.docx) Extractor (Reads entire document without truncation)
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

# 4. Document Handler (PDF & Word .docx - Full capacity up to 300,000 characters)
@bot.message_handler(content_types=['document'])
def handle_doc(msg):
    fname = msg.document.file_name.lower() if msg.document.file_name else "file"
    is_pdf = fname.endswith('.pdf')
    is_docx = fname.endswith('.docx') or fname.endswith('.doc')

    if not (is_pdf or is_docx):
        bot.reply_to(msg, "कृपया केवळ PDF, Word फाईल (.docx) किंवा पुस्तकाचा फोटो पाठवा.")
        return

    status = bot.reply_to(msg, f"📄 *दस्तऐवज मिळाला:* `{fname}`\nसंपूर्ण मजकूर वाचत आहे...", parse_mode="Markdown")
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
            for page in reader.pages[:50]:  # Up to 50 pages for large question banks
                t = page.extract_text()
                if t:
                    extracted += t + "\n"

        bot.delete_message(msg.chat.id, status.message_id)
        if not extracted.strip():
            bot.send_message(msg.chat.id, "⚠️ या फाईलमधून मजकूर काढता आले नाही (कदाचित ही स्कॅन केलेली प्रतिमा असावी). कृपया थेट फोटो काढून पाठवा.")
            return

        # Fast smart detection: check if file is a Question Bank or Theory Study Notes
        q_check_pat = r"(?:\n\s*|\A)(?:Q(?:uestion)?[\.\s]*\d+[\s\.:\)\|\-\–]+|प्रश्न\s*[\d१-९]+[\s\.:\)\|\-\–]+)"
        has_mcq_markers = len(re.findall(q_check_pat, extracted[:50000], flags=re.IGNORECASE)) >= 2

        if has_mcq_markers:
            # File is a genuine Question Bank -> Parse MCQs cleanly
            parsed_doc_mcqs = parse_all_document_mcqs(extracted)
            doc_count = len(parsed_doc_mcqs)
            user_sessions[msg.chat.id] = {
                "topic": extracted[:300000],
                "source_type": "doc",
                "parsed_mcqs": parsed_doc_mcqs,
                "total_mcqs": doc_count,
                "file_name": fname,
                "start_num": 1
            }
            count_msg = f"📄 *Question Bank स्कॅन केली:* `{fname}`\n✅ *या फाईलमध्ये एकूण {doc_count} प्रश्न आढळले आहेत!*\n(सर्व प्रश्न १ ते {doc_count} क्रमाने सुरक्षित ठेवले आहेत)"
            bot.send_message(msg.chat.id, count_msg, parse_mode="Markdown")
            label = f"📄 {fname} (एकूण {doc_count} प्रश्न)"
        else:
            # File is Theory Study Notes / Book -> Instant response in 0.1s without blocking!
            user_sessions[msg.chat.id] = {
                "topic": extracted[:300000],
                "source_type": "doc",
                "parsed_mcqs": [],
                "total_mcqs": 0,
                "file_name": fname,
                "start_num": 1
            }
            doc_msg = f"📄 *अभ्यास साहित्य / नोट्स स्कॅन केले:* `{fname}`\n✅ *या फाईलमधील संपूर्ण संकल्पना व संदर्भ वाचले आहेत!*\n(खालील मेनूमधून तुम्ही यावर क्विझ किंवा रिव्हिजन नोट्स बनवू शकता)"
            bot.send_message(msg.chat.id, doc_msg, parse_mode="Markdown")
            label = f"📄 {fname} (अभ्यास नोट्स)"

        show_format_menu(msg.chat.id, label)
    except Exception as e:
        bot.edit_message_text(f"❌ फाईल वाचताना त्रुटी: {str(e)}", msg.chat.id, status.message_id)

def show_single_mcq_instant_menu(cid, mcq, mid=None):
    """Shows instant 1-click As-Is Quiz Poll menu with auto-detected question number and 1-click number editing."""
    sess = user_sessions.get(cid, {})
    q_num = sess.get("inst_num") or mcq.get("q_num") or 1
    sess["inst_num"] = q_num
    corr_char = chr(65 + mcq["correct_option_id"])

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("⚡ जसा आहे तसा थेट पोस्ट करा (Instant Post)", callback_data="inst_post_ch"),
        types.InlineKeyboardButton(f"🔢 प्रश्नाचा नंबर बदला (चालू: Q{q_num})", callback_data="inst_change_num"),
        types.InlineKeyboardButton("🛠️ प्रश्न / पर्याय एडिट किंवा शफल करा", callback_data="inst_mcq_edit"),
        types.InlineKeyboardButton("❌ रद्द करा", callback_data="can_")
    )
    text = (
        f"🎯 **हा १ थेट प्रश्न आढळला आहे (Q{q_num})!**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📌 *प्रश्न (Q{q_num}):*\n{mcq['question']}\n\n"
        f"1️⃣ {mcq['options'][0]}\n"
        f"2️⃣ {mcq['options'][1]}\n"
        f"3️⃣ {mcq['options'][2]}\n"
        f"4️⃣ {mcq['options'][3]}\n\n"
        f"✅ *अचूक उत्तर:* **पर्याय {corr_char}**\n"
        f"💡 *स्पष्टीकरण:* _{mcq['explanation']}_\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👇 **कोणती कृती करायची आहे? निवडा:**"
    )
    if mid:
        try:
            bot.edit_message_text(text, cid, mid, reply_markup=markup, parse_mode="Markdown")
            return
        except Exception:
            pass
    bot.send_message(cid, text, reply_markup=markup, parse_mode="Markdown")

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
    markup.add(
        types.InlineKeyboardButton("🔄 हा प्रश्न AI कडून नव्याने बनवा", callback_data=f"regen_q_{post_id}_{q_idx}"),
        types.InlineKeyboardButton("🔀 पर्याय शफल करा (Shuffle Order)", callback_data=f"shuf_opt_{post_id}_{q_idx}")
    )
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
# 5. STEP-BY-STEP FLOW WITH ASYNC BACKGROUND PUBLISHING & SMART TWO-PART CARDS
# ------------------------------------------------------------------------------
def publish_in_background(post_id, cid, mid, item):
    """Executes posting with Two-Part Cards ONLY for genuine multi-statement questions, and native polls for direct ones."""
    target_id = item["channel_id"]
    sess = user_sessions.get(cid, {})
    ch_info = CHANNELS.get(sess.get("ch"), {})
    is_eng_ch = (ch_info.get("lang") == "English") or (sess.get("lang") == "english") or (target_id != "@sidhu_sir_official")
    try:
        if item["type"] == "quiz":
            quizzes = item["data"]
            total_q = len(quizzes)
            timer_sec = item.get("timer")
            brand = "\n\n🎯 Join: @sidhu_sir_official"
            posted_count = 0
            last_err = ""

            start_num = item.get("start_num", 1)
            total_display = item.get("total_series_cnt", (start_num + total_q - 1) if start_num > 1 else total_q)

            for i, q in enumerate(quizzes):
                curr_num = start_num + i
                exp = q.get("explanation", "")
                if len(exp) + len(brand) <= 200:
                    exp += brand
                exp = exp[:200]

                raw_q = q['question'].strip()
                is_large = is_multi_statement_card(q)

                is_eng_ch = (ch_info.get("lang") == "English") or (sess.get("lang") == "english")
                if not exp:
                    exp = "Correct answer as per standard reference notes." if is_eng_ch else "संदर्भ नोट्सनुसार अचूक उत्तर."

                if is_large:
                    formatted_q = format_statements_cleanly(raw_q)
                    q_badge = f"Question {curr_num}/{total_display}" if is_eng_ch else f"प्रश्न {curr_num}/{total_display}"
                    f_guide = "Select the correct option in the poll below:" if is_eng_ch else "खालील पोलमध्ये अचूक पर्याय निवडा:"
                    card_text = (
                        f"📋 **[{q_badge}]**\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"{formatted_q}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"👇 **{f_guide}**"
                    )
                    try:
                        bot.send_message(target_id, card_text, parse_mode="Markdown")
                    except Exception:
                        bot.send_message(target_id, card_text)
                    time.sleep(1.2)

                    poll_q = f"[{curr_num}/{total_display}] Select the correct option for the question above:" if is_eng_ch else f"[{curr_num}/{total_display}] वरील प्रश्नाचे अचूक उत्तर निवडा:"
                else:
                    poll_q = f"[{curr_num}/{total_display}] {raw_q}" if total_display > 1 else raw_q

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

                if posted_count > 0 and posted_count % 10 == 0 and posted_count < total_q:
                    try:
                        bot.send_message(cid, f"⏳ **प्रगती:** `{posted_count}/{total_q}` प्रश्न `{target_id}` वर पोस्ट झाले आहेत...")
                    except Exception:
                        pass

                time.sleep(2.5)

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
            notes_raw = item["data"]
            html_text = format_notes_for_telegram(notes_raw)
            footer = "\n\n━━━━━━━━━━━━━━━\n📢 <b>अधिक तयारीसाठी जॉईन करा:</b> @sidhusirofficial"
            full_msg = html_text + footer

            chunks = []
            while len(full_msg) > 3800:
                s_idx = full_msg.rfind("\n\n", 0, 3800)
                if s_idx == -1:
                    s_idx = 3800
                chunks.append(full_msg[:s_idx].strip())
                full_msg = full_msg[s_idx:].strip()
            if full_msg:
                chunks.append(full_msg)

            try:
                for c in chunks:
                    try:
                        bot.send_message(target_id, c, parse_mode="HTML")
                    except Exception:
                        bot.send_message(target_id, c)
                    time.sleep(1)
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

    # Instant Single MCQ flow - 100% direct posting
    elif call.data == "inst_post_ch":
        show_instant_channel_menu(cid, mid)

    elif call.data == "inst_change_num":
        sess["waiting_inst_num"] = mid
        bot.edit_message_text(
            f"🔢 **या प्रश्नाचा नंबर कोणता ठेवायचा आहे?**\n*(उदा. 1, 21, 51, 101 टाइप करून पाठवा):*",
            cid, mid, parse_mode="Markdown"
        )

    elif call.data == "back_to_inst_q":
        q_item = sess.get("direct_mcq")
        if q_item:
            show_single_mcq_instant_menu(cid, q_item, mid)
        else:
            bot.edit_message_text("🔄 कृपया प्रश्न पुन्हा पाठवा.", cid, mid)

    elif call.data.startswith("instpub_"):
        ch_key = call.data.replace("instpub_", "")
        ch_target = CHANNELS.get(ch_key, {}).get("id", "@sidhu_sir_official")
        ch_title = CHANNELS.get(ch_key, {}).get("title", ch_target)
        q_item = sess.get("direct_mcq")

        if not q_item:
            bot.answer_callback_query(call.id, "प्रश्न सापडला नाही. कृपया पुन्हा पाठवा.")
            return

        bot.answer_callback_query(call.id, "🚀 थेट चॅनेलवर पोस्ट करत आहे...")
        raw_q = q_item["question"].strip()
        opts = [opt[:100] for opt in q_item["options"][:4]]
        corr_id = q_item["correct_option_id"] if 0 <= q_item["correct_option_id"] <= 3 else 0
        exp_txt = q_item.get("explanation", "").strip()[:180]

        try:
            is_eng_ch = (CHANNELS.get(ch_key, {}).get("lang") == "English") or (sess.get("lang") == "english")
            if not exp_txt:
                exp_txt = "Correct answer as per standard reference notes." if is_eng_ch else "संदर्भ नोट्सनुसार अचूक उत्तर."

            curr_num = sess.get("inst_num") or q_item.get("q_num") or 1
            num_prefix = f"Q{curr_num}. "

            if is_multi_statement_card(q_item):
                formatted_q = format_statements_cleanly(raw_q)
                q_badge = f"Question {curr_num}" if is_eng_ch else f"प्रश्न {curr_num}"
                f_guide = "Select the correct option in the poll below:" if is_eng_ch else "खालील पोलमध्ये अचूक पर्याय निवडा:"
                card_text = (
                    f"📋 **[{q_badge}]**\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{formatted_q}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👇 **{f_guide}**"
                )
                bot.send_message(ch_target, card_text, parse_mode="Markdown")
                time.sleep(1.2)
                poll_q = f"[{q_badge}] {f_guide}"
            else:
                poll_q = f"{num_prefix}{raw_q}"[:300]

            bot.send_poll(
                chat_id=ch_target,
                question=poll_q,
                options=opts,
                type="quiz",
                correct_option_id=corr_id,
                explanation=exp_txt,
                is_anonymous=True
            )
            bot.edit_message_text(
                f"🎉 **अभिनंदन!** हा प्रश्न `{ch_title}` चॅनेलवर थेट यशस्वीरीत्या पोस्ट झाला आहे!",
                cid, mid, parse_mode="Markdown"
            )
        except Exception as pub_err:
            bot.edit_message_text(
                f"❌ **पोस्ट करताना त्रुटी आली:** `{pub_err}`\n\nबॉट `{ch_target}` चा Admin आहे का ते तपासा.",
                cid, mid
            )

    elif call.data == "inst_mcq_edit":
        q_item = sess.get("direct_mcq")
        if q_item:
            post_id = str(mid)
            pending_posts[post_id] = {
                "type": "quiz",
                "channel_id": "@sidhu_sir_official",
                "data": [q_item],
                "start_num": 1,
                "total_series_cnt": 1
            }
            show_question_edit_menu(cid, mid, post_id, 0)
        else:
            show_channel_menu(cid, mid)

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
            threading.Thread(target=run_content_generation, args=(cid, mid, sess), daemon=True).start()

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
                "👇 **तुम्हाला किती प्रश्न तयार/पोस्ट करायचे आहेत? संख्या टाईप करून पाठवा:**\n*(उदा. 40, 50, 63, 100, 150)*",
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
        threading.Thread(target=run_content_generation, args=(cid, mid, sess), daemon=True).start()

    elif call.data == "back_to_timer":
        show_count_menu(cid, mid)

    # Range selection (1-20, 21-40, etc.)
    elif call.data.startswith("rng_"):
        parts = call.data.split("_")
        r_start = int(parts[1])
        r_end = int(parts[2])
        sess["range_start"] = r_start
        sess["range_end"] = r_end
        sess["cnt"] = (r_end - r_start + 1)
        sess["start_num"] = r_start
        show_timer_menu(cid, mid)

    # Set custom starting number
    elif call.data == "set_start_offset":
        sess["waiting_start_offset"] = mid
        bot.edit_message_text(
            "🔢 **नंबरिंग कुठून सुरू करायचे आहे? तो नंबर टाईप करून पाठवा:**\n*(उदा. 11, 21, 51, 101)*",
            cid, mid, parse_mode="Markdown"
        )

    # Regenerate single question in editor
    elif call.data.startswith("regen_q_"):
        parts = call.data.split("_")
        post_id = parts[2]
        q_idx = int(parts[3])
        if post_id in pending_posts and q_idx < len(pending_posts[post_id]["data"]):
            bot.answer_callback_query(call.id, "⏳ नवीन प्रश्न तयार होत आहे...")
            try:
                ch_info = CHANNELS[sess.get("ch", "mpsc_official")]
                lvl = sess.get("lvl", "combine")
                sub_name = ch_info.get("sub", "General Studies")
                tgt_lang = sess.get("lang", "marathi")
                regen_prompt = (
                    f"Generate exactly 1 brand new high-yield exam question for {sub_name} ({lvl} exam standard) in {tgt_lang}.\n"
                    "Ensure 100% historical/constitutional accuracy, 4 distinct choices, correct option (0-3), and 1-sentence explanation.\n"
                    "Output strictly a raw JSON object with keys: question, options, correct_option_id, explanation."
                )
                raw_new = ask_groq(regen_prompt, json_mode=True)
                new_q_data = parse_json_mcqs(raw_new)
                if new_q_data:
                    item_to_put = standardize_mcq_for_exam(new_q_data[0] if isinstance(new_q_data, list) else new_q_data, lvl)
                    pending_posts[post_id]["data"][q_idx] = item_to_put
                    bot.answer_callback_query(call.id, "✅ प्रश्न यशस्वीरित्या बदलला!")
            except Exception as re_err:
                bot.answer_callback_query(call.id, f"त्रुटी: {str(re_err)[:40]}", show_alert=True)
            show_question_edit_menu(cid, mid, post_id, q_idx)

    # Shuffle options in editor
    elif call.data.startswith("shuf_opt_"):
        parts = call.data.split("_")
        post_id = parts[2]
        q_idx = int(parts[3])
        if post_id in pending_posts and q_idx < len(pending_posts[post_id]["data"]):
            q_it = pending_posts[post_id]["data"][q_idx]
            old_opts = list(q_it["options"])
            corr_idx = q_it["correct_option_id"]
            if 0 <= corr_idx < len(old_opts):
                corr_val = old_opts[corr_idx]
                import random
                shuffled = list(old_opts)
                random.shuffle(shuffled)
                new_corr_idx = shuffled.index(corr_val)
                q_it["options"] = shuffled
                q_it["correct_option_id"] = new_corr_idx
                bot.answer_callback_query(call.id, "🔀 पर्याय शफल झाले! उत्तर सुरक्षित आहे.")
            show_question_edit_menu(cid, mid, post_id, q_idx)

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

        # If this was an instant single text question, return to instant menu!
        if sess.get("source_type") == "text_mcq" and post_id in pending_posts:
            q_data = pending_posts[post_id]["data"]
            if q_data:
                show_single_mcq_instant_menu(cid, q_data[0], mid)
                return

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

def show_instant_channel_menu(cid, mid):
    """Channel selector for Instant Single MCQ posting - 1 tap directly publishes!"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(CHANNELS["upsc_polity"]["title"], callback_data="instpub_upsc_polity"),
        types.InlineKeyboardButton(CHANNELS["upsc_history"]["title"], callback_data="instpub_upsc_history")
    )
    markup.add(
        types.InlineKeyboardButton(CHANNELS["upsc_geo"]["title"], callback_data="instpub_upsc_geo"),
        types.InlineKeyboardButton(CHANNELS["upsc_economy"]["title"], callback_data="instpub_upsc_economy")
    )
    markup.add(
        types.InlineKeyboardButton(CHANNELS["upsc_env"]["title"], callback_data="instpub_upsc_env"),
        types.InlineKeyboardButton(CHANNELS["upsc_sci"]["title"], callback_data="instpub_upsc_sci")
    )
    markup.add(
        types.InlineKeyboardButton(CHANNELS["mpsc_official"]["title"], callback_data="instpub_mpsc_official")
    )
    markup.add(
        types.InlineKeyboardButton(CHANNELS["vachal_tar_vachal"]["title"], callback_data="instpub_vachal_tar_vachal"),
        types.InlineKeyboardButton(CHANNELS["ebooks_lab"]["title"], callback_data="instpub_ebooks_lab")
    )
    markup.add(types.InlineKeyboardButton("🔙 मागे जा (Back)", callback_data="back_to_inst_q"))
    text = "👇 **कोणत्या चॅनेलवर पोस्ट करायचे आहे?**\n*(चॅनेल निवडताच १ सेकंदात थेट पोल जाईल!)*"
    if mid:
        bot.edit_message_text(text, cid, mid, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(cid, text, reply_markup=markup, parse_mode="Markdown")

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
    markup.add(
        types.InlineKeyboardButton(CHANNELS["vachal_tar_vachal"]["title"], callback_data="ch_vachal_tar_vachal"),
        types.InlineKeyboardButton(CHANNELS["ebooks_lab"]["title"], callback_data="ch_ebooks_lab")
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
        types.InlineKeyboardButton("🚩 फक्त शुद्ध मराठी (Pure Marathi)", callback_data="lng_marathi"),
        types.InlineKeyboardButton("🔤 मराठी + इंग्रजी की-वर्ड्स (कंसात संज्ञा)", callback_data="lng_marathi_eng_kw"),
        types.InlineKeyboardButton("🇬🇧 Only English", callback_data="lng_english"),
        types.InlineKeyboardButton("🔙 मागे जा (Back)", callback_data="back_to_lang"))
    bot.edit_message_text("👇 **कोणत्या भाषेत कन्टेन्ट हवा आहे?**", cid, mid, reply_markup=markup, parse_mode="Markdown")

def show_count_menu(cid, mid):
    sess = user_sessions.get(cid, {})
    total_file_q = sess.get("total_mcqs", 0)
    markup = types.InlineKeyboardMarkup(row_width=2)

    if total_file_q > 0:
        markup.add(types.InlineKeyboardButton(f"🚀 सर्व {total_file_q} प्रश्न सलग पोस्ट करा (Zero Loss)", callback_data=f"cnt_{total_file_q}"))
        if total_file_q > 15:
            # Add range batches: 1-20, 21-40, 41-60...
            row = []
            for r_start in range(1, total_file_q + 1, 20):
                r_end = min(r_start + 19, total_file_q)
                row.append(types.InlineKeyboardButton(f"📑 प्रश्न {r_start} ते {r_end}", callback_data=f"rng_{r_start}_{r_end}"))
                if len(row) == 2:
                    markup.add(*row)
                    row = []
            if row:
                markup.add(*row)

    markup.add(
        types.InlineKeyboardButton("⚡ ५ प्रश्न", callback_data="cnt_5"),
        types.InlineKeyboardButton("🔥 १० प्रश्न", callback_data="cnt_10")
    )
    markup.add(
        types.InlineKeyboardButton("🏆 २५ प्रश्न", callback_data="cnt_25"),
        types.InlineKeyboardButton("🎯 ५० प्रश्न", callback_data="cnt_50")
    )
    markup.add(
        types.InlineKeyboardButton("🔢 सुरुवातीचा नंबर बदला (Start No)", callback_data="set_start_offset"),
        types.InlineKeyboardButton("✍️ स्वतः संख्या टाका (Custom)", callback_data="cnt_custom")
    )
    markup.add(types.InlineKeyboardButton("🔙 मागे जा (Back)", callback_data="back_to_cnt"))
    cur_start = sess.get("start_num", 1)
    prompt_txt = f"👇 **किती प्रश्न पोस्ट करायचे आहेत?**\n(सध्या सुरुवातीचा नंबर: **Q{cur_start}** आहे)"
    bot.edit_message_text(prompt_txt, cid, mid, reply_markup=markup, parse_mode="Markdown")

def show_timer_menu(cid, mid):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("♾️ नॉर्मल क्विझ (कायम चालू - कधीही सोडवता येईल)", callback_data="tmr_none"),
        types.InlineKeyboardButton("⏱️ लाईव्ह टेस्ट (४५ सेकंदांचा उलटा टायमर)", callback_data="tmr_45"),
        types.InlineKeyboardButton("🔙 मागे जा (Back)", callback_data="back_to_timer")
    )
    bot.edit_message_text("👇 **क्विझ प्रकार (Quiz Mode) निवडा:**", cid, mid, reply_markup=markup, parse_mode="Markdown")

def run_content_generation(cid, mid, sess):
    ch_key = sess.get("ch", "mpsc_official")
    ch_info = CHANNELS.get(ch_key, CHANNELS["mpsc_official"])
    topic = sess["topic"]
    fmt = sess["fmt"]
    lang = sess["lang"]
    qmode = sess.get("quiz_source_mode", "ai_gen")

    bot.edit_message_text("⏳ **AI द्वारे प्रक्रिया सुरू आहे...** (मोठ्या संचासाठी १०-१५ सेकंद लागू शकतात)...", cid, mid, parse_mode="Markdown")
    try:
        lang_str = "BILINGUAL (English / Marathi)" if lang == "bilingual" else ("Marathi only" if lang == "marathi" else "English only")
        post_id = str(mid)

        if fmt == "quiz":
            cnt = sess.get("cnt", 1)
            lvl = sess.get("lvl", "combine")
            all_mcqs = []

            # Strategy A: If As-Is mode, extract verbatim and solve any missing answers/explanations via AI!
            if qmode == "as_is":
                direct_extracted = parse_all_document_mcqs(topic)
                if direct_extracted:
                    key_dict = extract_answer_key_dict(topic)
                    if key_dict:
                        logging.info(f"Answer Key successfully detected with {len(key_dict)} answers!")
                    for i, q in enumerate(direct_extracted):
                        q_no = q.get("q_num")
                        if q_no is not None and (q_no - 1) in key_dict:
                            q["correct_option_id"] = key_dict[q_no - 1]
                            q["has_detected_answer"] = True
                        elif i in key_dict:
                            q["correct_option_id"] = key_dict[i]
                            q["has_detected_answer"] = True

                    # Set language-aware default explanation
                    def_exp = "Correct answer as per standard reference notes." if lang == "english" else "संदर्भ नोट्सनुसार अचूक उत्तर."
                    for q in direct_extracted:
                        if not q.get("has_detected_exp"):
                            q["explanation"] = def_exp

                    # If questions in document lacked inline answers, auto-solve via AI in target language!
                    unsolved = [q for q in direct_extracted[:cnt] if not q.get("has_detected_answer")]
                    if unsolved:
                        try:
                            bot.edit_message_text(
                                f"⏳ **प्रश्नांची खरी उत्तरे व स्पष्टीकरणे पडताळत आहे...**",
                                cid, mid, parse_mode="Markdown"
                            )
                        except Exception:
                            pass
                        try:
                            solve_batches = get_batch_sizes(len(unsolved), max_per_batch=12)
                            curr_idx = 0
                            for _, _, b_sz in solve_batches:
                                batch_items = unsolved[curr_idx:curr_idx + b_sz]
                                solve_payload = [
                                    {"id": idx, "question": it["question"][:400], "options": it["options"]}
                                    for idx, it in enumerate(batch_items)
                                ]
                                solve_prompt = (
                                    f"You are an expert exam paper evaluator for {ch_info['sub']}.\n"
                                    f"Solve each MCQ below with 100% precision. Evaluate all 4 options independently and determine which option letter (A, B, C, or D) is factually correct.\n"
                                    f"Input MCQs:\n{json.dumps(solve_payload)}\n\n"
                                    f"CRITICAL RULES:\n"
                                    f"1. Choose the genuine correct option letter: 'A', 'B', 'C', or 'D' based on factual examination truth. Do NOT choose the same option for all questions!\n"
                                    f"2. Provide a 1-sentence factual explanation in {lang_str}.\n"
                                    f"Output strictly a JSON object:\n"
                                    f"{{\n  \"answers\": [\n    {{\"id\": 0, \"correct_letter\": \"C\", \"explanation\": \"Factual explanation here.\"}}\n  ]\n}}"
                                )
                                solve_res = ask_groq(solve_prompt, json_mode=True)
                                solve_data = parse_solve_json(solve_res)
                                for s_item in solve_data:
                                    s_id = s_item.get("id")
                                    if s_id is not None and 0 <= s_id < len(batch_items):
                                        target_q = batch_items[s_id]
                                        let = str(s_item.get("correct_letter") or s_item.get("correct_option") or "").strip().upper()
                                        if let in "ABCD":
                                            c_id = ord(let) - ord("A")
                                        elif "correct_option_id" in s_item:
                                            c_id = int(s_item["correct_option_id"])
                                        else:
                                            c_id = 0
                                        target_q["correct_option_id"] = c_id if 0 <= c_id <= 3 else 0
                                        target_q["has_detected_answer"] = True
                                        s_exp = s_item.get("explanation", "").strip()
                                        if s_exp:
                                            target_q["explanation"] = s_exp[:140]
                                curr_idx += b_sz
                        except Exception as se:
                            logging.warning(f"AI Auto-solver fallback: {se}")

                    r_st = sess.get("range_start")
                    r_en = sess.get("range_end")
                    if r_st and r_en and r_st <= len(direct_extracted):
                        all_mcqs = direct_extracted[r_st - 1 : r_en]
                    elif len(direct_extracted) >= cnt:
                        all_mcqs = direct_extracted[:cnt]
                    else:
                        all_mcqs = list(direct_extracted)

            # Strategy B: If not enough questions or AI Generate mode, run safe batched AI calls
            if len(all_mcqs) < cnt:
                needed = cnt - len(all_mcqs)
                batches = get_batch_sizes(needed, max_per_batch=15)

                for b_start, b_end, b_sz in batches:
                    if len(batches) > 1:
                        try:
                            bot.edit_message_text(
                                f"⏳ **AI द्वारे प्रश्न तयार होत आहेत...** ({len(all_mcqs)}/{cnt} प्रश्न पूर्ण)...",
                                cid, mid, parse_mode="Markdown"
                            )
                        except Exception:
                            pass

                    # Intelligently locate the actual chapter in large documents instead of always taking the first 12,000 chars
                    f_name = sess.get("file_name", "")
                    clean_doc_topic = re.sub(r"^(?:\d+[\s\.\-_]+)?", "", f_name)
                    clean_doc_topic = re.sub(r"(?i)(?:by\s+.*|\.docx|\.pdf|\.doc)", "", clean_doc_topic).strip()

                    chunk_text = topic[:15000]
                    if clean_doc_topic and len(clean_doc_topic) >= 3:
                        match_pos = topic.find(clean_doc_topic)
                        if match_pos != -1 and match_pos > 2000:
                            start_p = max(0, match_pos - 200)
                            chunk_text = topic[start_p : start_p + 15000]

                    if qmode == "as_is":
                        pattern_instruction = (
                            "TASK: EXTRACT QUESTIONS AND OPTIONS AS-IS FROM SOURCE MATERIAL.\n"
                            f"Source Material containing Question Bank / PYQs:\n'''\n{chunk_text}\n'''\n\n"
                            f"RULES:\n"
                            f"1. Extract up to {b_sz} questions verbatim from the source material without altering or rephrasing.\n"
                            f"2. Statements MUST be preserved inside the question sentence.\n"
                            f"3. Extract the exact question text, the 4 choices, correct answer (0-3), and explanation.\n"
                        )
                    else:
                        if lvl == "upsc":
                            pattern_instruction = (
                                "EXAM LEVEL: UPSC Civil Services Examination (CSE) Prelims Standard.\n"
                                "QUESTION FORMAT & VARIETY (MANDATORY UPSC CSE GUIDELINES):\n"
                                "1. STRICT DIVERSITY OF CORRECT ANSWERS (RANDOMIZE!):\n"
                                "   - The correct answers MUST BE EVENLY DISTRIBUTED across (a), (b), (c), and (d) (indices 0, 1, 2, 3)!\n"
                                "   - NEVER make every question '(c) Both 1 and 2' or index 2! Distribute answers evenly across A, B, C, D.\n"
                                "2. REALISTIC EXAM TRAPS & FALSE STATEMENTS:\n"
                                "   - In real UPSC Prelims, at least 40% to 50% of statements are FALSE or contain subtle exam traps (e.g. swapped organs/bones/functions, wrong articles, reversed causes, incorrect years, exaggerated absolutes like 'solely' or 'always').\n"
                                "   - Introduce false statements so that (a) 1 only, (b) 2 only, or (d) Neither 1 nor 2 are frequently correct!\n"
                                "3. MIX MULTIPLE QUESTION FORMATS ACROSS THE BATCH:\n"
                                "   - Format A: 2 or 3 Statements ('Consider the following statements... Which of the statements given above is/are correct?').\n"
                                "   - Format B: Inverted Questions ('Which of the statements given above is/are NOT correct?').\n"
                                "   - Format C: Pairs Matching ('Consider the following pairs... How many pairs are correctly matched? (a) Only one pair, (b) Only two pairs, (c) All three pairs, (d) None').\n"
                                "   - Format D: Chronological Order / Sequence ('Arrange in correct order...').\n"
                                "   - Format E: Direct 1-liner factual MCQs for discoveries, scientific laws, or terms.\n"
                                "   - Statements in the question text MUST be numbered: 1., 2., 3. with newlines.\n"
                                "   - Options MUST be lettered in English: (a) ..., (b) ..., (c) ..., (d) ...\n"
                            )
                        elif lvl == "rajyaseva":
                            pattern_instruction = (
                                "EXAM LEVEL: MPSC राज्यसेवा (Civil Services) पूर्व परीक्षा Standard.\n"
                                "QUESTION FORMAT & VARIETY (MANDATORY MPSC RAJYASEVA GUIDELINES):\n"
                                "1. उत्तरांची विविधता (STRICT DIVERSITY & RANDOMIZATION):\n"
                                "   - प्रत्येक प्रश्नाचे अचूक उत्तर फक्त एकच (उदा. नेहमी ३ किंवा ४) नसावे! अचूक उत्तरे १), २), ३), ४) (indices 0, 1, 2, 3) मध्ये समान विभागलेली असावीत.\n"
                                "2. परीक्षा-स्तरीय ट्रॅप्स आणि अयोग्य विधाने (EXAM TRAPS):\n"
                                "   - एमपीएससीच्या ४०% ते ५०% विधानांमध्ये सूक्ष्म चुका, चुकीची कलमे, बदललेल्या तारखा किंवा फॅक्ट्स असतात, जेणेकरून 'फक्त अ', 'फक्त ब', किंवा 'एकही नाही' हे पर्याय अचूक ठरतील.\n"
                                "3. विविध प्रकारच्या प्रश्नांचे मिश्रण (MIX FORMATS):\n"
                                "   - प्रकार १: बहुविधानात्मक ('खालील विधाने विचारात घ्या... योग्य विधान/ने निवडा').\n"
                                "   - प्रकार २: अयोग्य विधान ओळखा ('खालीलपैकी कोणते विधान चुकीचे/अयोग्य आहे?').\n"
                                "   - प्रकार ३: जोड्या लावा / कालानुक्रम ('योग्य कालानुक्रम लावा...').\n"
                                "   - प्रकार ४: थेट फॅक्ट्युअल प्रश्न (पुरस्कार, खेळ, पुस्तके, दिनविशेष यासाठी विधाने न लावता थेट प्रश्न व ४ पर्याय).\n"
                                "   - विधाने MUST be lettered in Marathi: (अ), (ब), (क), (ड) with newlines.\n"
                                "   - खालील ४ पर्याय MUST be numbered in Marathi digits: १) ..., २) ..., ३) ..., ४) ...\n"
                            )
                        elif lvl == "combine":
                            pattern_instruction = (
                                "EXAM LEVEL: MPSC गट ब व गट क संयुक्त (Combine Group B & C) Standard.\n"
                                "QUESTION FORMAT (MANDATORY MPSC COMBINE STYLE):\n"
                                "- विधानात्मक + थेट वस्तुनिष्ठ संमिश्र प्रश्न (कलमे, घटनादुरुस्त्या, समित्या, तारखा).\n"
                                "- थेट प्रश्नांसाठी विधाने न लावता थेट प्रश्न आणि ४ पर्याय बनवा.\n"
                                "- खालील ४ पर्याय MUST be numbered: १) ..., २) ..., ३) ..., ४) ...\n"
                            )
                        else: # bharti
                            pattern_instruction = (
                                "EXAM LEVEL: पोलीस भरती / तलाठी / सरळसेवा परीक्षा Standard.\n"
                                "QUESTION FORMAT (MANDATORY BHARTI STYLE):\n"
                                "- थेट १-ओळी (One-liner) वस्तुनिष्ठ प्रश्न. कोणतीही विधाने नको.\n"
                                "- खालील ४ पर्याय MUST be numbered: १) ..., २) ..., ३) ..., ४) ...\n"
                            )

                        topic_guard = ""
                        if clean_doc_topic and len(clean_doc_topic) >= 3:
                            topic_guard = (
                                f"MANDATORY CHAPTER / TOPIC REQUIREMENT:\n"
                                f"- The document is specifically titled: '{clean_doc_topic}'.\n"
                                f"- All questions MUST strictly test the core concepts, articles, systems, and features of '{clean_doc_topic}'.\n"
                                f"- DO NOT drift into basic introductory history or other topics (like Making of Constitution) unless that is the exact title!\n"
                            )

                        pattern_instruction += (
                            f"Subject: {ch_info['sub']}. Topic: {clean_doc_topic or 'General'}. Language: {lang_str}.\n"
                            f"{topic_guard}"
                            f"Source Material / Notes:\n'''\n{chunk_text}\n'''\n\n"
                            f"Generate exactly {b_sz} high-yield MCQs (Batch {b_start} to {b_end}).\n"
                        )

                    prompt = (
                        f"{pattern_instruction}\n"
                        f"CONSTRAINTS (STRICT FOR TELEGRAM POLLS):\n"
                        f"1. 'question' contains question and statements (DO NOT put option letters A/B/C/D inside question).\n"
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

                    try:
                        raw = ask_groq(prompt, json_mode=True)
                        b_data = parse_json_mcqs(raw)
                        all_mcqs.extend(b_data)
                    except Exception as be:
                        logging.error(f"Batch generation error: {be}")
                        if not all_mcqs:
                            raise be
                        break

            raw_data = all_mcqs[:cnt] if all_mcqs else []
            if not raw_data:
                raise Exception("दिलेल्या फाईलमधून प्रश्न काढता आले नाहीत.")

            data = [standardize_mcq_for_exam(q, lvl) for q in raw_data]

            r_st = sess.get("range_start")
            default_start = r_st if r_st else sess.get("start_num", 1)
            tot_cnt = sess.get("total_mcqs", len(data))
            pending_posts[post_id] = {
                "type": "quiz",
                "channel_id": ch_info["id"],
                "data": data,
                "timer": sess.get("timer"),
                "start_num": default_start,
                "total_series_cnt": tot_cnt if tot_cnt > len(data) else (default_start + len(data) - 1 if default_start > 1 else len(data))
            }

        elif fmt == "mnemonic":
            prompt = f"Create a memorable MNEMONIC / SHORT TRICK in {lang_str} for subject '{ch_info['sub']}' on topic '{topic[:12000]}'. Ensure 100% historical accuracy. Use emojis, bold text, clear breakdown."
            text = ask_groq(prompt, json_mode=False)
            pending_posts[post_id] = {"type": "mnemonic", "channel_id": ch_info["id"], "data": text}

        else: # notes
            notes_style = sess.get("notes_style", "hybrid")
            if notes_style == "table":
                style_inst = "Format strictly as a comprehensive, well-aligned Markdown Table comparing key dimensions, articles, bodies, or provisions."
            elif notes_style == "bullet":
                style_inst = "Format in clean, structured bullet points following the natural chronological / conceptual flow of the topic."
            else: # hybrid / viral 3.4 lakh subscriber style
                style_inst = (
                    "VIRAL TELEGRAM CURRENT AFFAIRS CARD FORMAT (MANDATORY 3.4 LAKH SUBSCRIBERS STYLE):\n"
                    "Format each news event as a unified, beautiful shaded Telegram Blockquote Card using this syntax:\n"
                    "emoji **[ठळक आकर्षक शीर्षक]**\n"
                    ">■ **[विशिष्ट घटक]** - [तपशील]\n\n"
                    "CRITICAL ATTRIBUTE LABELING RULE (STRICT):\n"
                    "1. DO NOT USE SLASH-SEPARATED TEMPLATES! Never write 'अध्यक्ष / व्यक्ती / मंत्रालय' or 'उद्देश / वैशिष्ट्ये'!\n"
                    "2. Choose ONLY ONE natural, single, relevant Marathi word per line that fits the fact:\n"
                    "   - If sports/event: use '■ **खेळाडू** - ...', '■ **बोली / रक्कम** - ...', '■ **संघ** - ...', '■ **स्थान** - ...'\n"
                    "   - If government scheme: use '■ **मंत्रालय** - ...', '■ **सुरुवात** - ...', '■ **उद्देश** - ...'\n"
                    "   - If appointment/meeting: use '■ **अध्यक्ष** - ...', '■ **ठिकाण** - ...', '■ **सहभाग** - ...'\n"
                    "   - Other clean single labels: '■ **कालावधी** - ...', '■ **आयोजक** - ...', '■ **विशेष नोंद** - ...'\n"
                    "3. COHESIVE CARD: Group all related points of the event into ONE unified card (do not split 1 event into 6 tiny repetitive fragments!).\n"
                    "4. Every attribute line MUST start with '>■ ' so Telegram renders the shaded card box!\n"
                    "5. End with footer: ✍️ **संकलन :** ©सिधू सर ऑफिशियल | @sidhu_sir_official"
                )

            prompt = (
                f"You are a master faculty for UPSC & MPSC exams ({ch_info['sub']}).\n"
                f"Create a high-yield, structured Revision Note in {lang_str} on:\n'''\n{topic[:12000]}\n'''\n\n"
                f"{style_inst}\n\n"
                f"STRICT RULES:\n"
                f"- Zero loss of key exam facts.\n"
                f"- 100% accurate historical & constitutional facts.\n"
                f"- Use bold text and clean spacing for easy reading on mobile."
            )
            text = ask_groq(prompt, json_mode=False)
            pending_posts[post_id] = {"type": "notes", "channel_id": ch_info["id"], "data": text}

        render_preview_message(cid, mid, post_id, sess)

    except Exception as e:
        bot.edit_message_text(f"❌ त्रुटी: {str(e)}", cid, mid)

def render_preview_message(cid, mid, post_id, sess):
    if post_id not in pending_posts:
        return
    item = pending_posts[post_id]
    ch_key = sess.get("ch", "mpsc_official")
    ch_info = CHANNELS.get(ch_key, CHANNELS["mpsc_official"])
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
                preview += f"*(...आणि उर्वरित {len(data) - idx} प्रश्न थेट चॅनेलवर पोस्ट होतील)*\n"
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
        # Add 1-click WhatsApp Share button for notes with safe URL length (under 150 chars to prevent 400 reply markup error)
        try:
            import urllib.parse
            sub_lbl = ch_info.get("sub", "MPSC/UPSC")
            wa_summary = f"📚 {sub_lbl} Revision Notes by Sidhu Sir\n👉 Join Telegram: @sidhusirofficial"
            wa_url = "https://api.whatsapp.com/send?text=" + urllib.parse.quote_plus(wa_summary)
            markup.add(types.InlineKeyboardButton("📲 WhatsApp वर शेअर करा (Share to WhatsApp)", url=wa_url))
        except Exception:
            pass
    markup.add(types.InlineKeyboardButton("❌ रद्द करा (Cancel)", callback_data="can_"))

    p_mode = "HTML" if fmt in ["notes", "mnemonic"] else "Markdown"
    try:
        bot.edit_message_text(preview, cid, mid, reply_markup=markup, parse_mode=p_mode)
    except Exception:
        try:
            bot.send_message(cid, preview, reply_markup=markup, parse_mode=p_mode)
        except Exception:
            bot.send_message(cid, preview, reply_markup=markup)

# ------------------------------------------------------------------------------
# 6. RUN BOT (CLEAN INFINITY POLLING WITH AUTO-RESTART)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    print("🚀 Sidhu Sir's Bot is online 24/7!")
    time.sleep(3) # Grace period for previous container shutdown to prevent 409
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10, logger_level=logging.INFO)
        except Exception as e:
            logging.error(f"Polling loop restart after error: {e}")
            time.sleep(3)
