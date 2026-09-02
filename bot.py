import os
import json
import re
from datetime import date

from dotenv import load_dotenv
from pyrogram import Client, filters
from openai import OpenAI


# =========================
# Load Environment
# =========================

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

USERS_FILE = "users.json"


# =========================
# AI Client
# =========================

ai = OpenAI(
    base_url="https://aimodelapi.onrender.com/v1",
    api_key=GEMINI_API_KEY
)


# =========================
# Users Database
# =========================

def load_users():

    if not os.path.exists(USERS_FILE):

        with open(
            USERS_FILE,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                {},
                f,
                ensure_ascii=False,
                indent=2
            )

        return {}

    try:

        with open(
            USERS_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)

    except Exception:

        return {}


def save_users():

    with open(
        USERS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            users,
            f,
            ensure_ascii=False,
            indent=2
        )


users = load_users()


# =========================
# User State
# =========================

def get_user(user_id):

    user_id = str(user_id)
    today = str(date.today())

    if user_id not in users:

        users[user_id] = {
            "state": "idle",
            "request": "",
            "sites_today": 0,
            "last_date": today
        }

        save_users()

    user = users[user_id]

    # New day → reset limit
    if user.get("last_date") != today:

        user["sites_today"] = 0
        user["last_date"] = today
        user["state"] = "idle"
        user["request"] = ""

        save_users()

    return user


# =========================
# Telegram Bot
# =========================

app = Client(
    "domain_maker_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# =========================
# Generate Website
# =========================

def generate_website(description):

    prompt = f"""
You are Domain Maker, an expert web developer.

Create a complete modern website based on the user's description.

USER DESCRIPTION:
{description}

IMPORTANT RULES:

1. Return ONLY the complete HTML document.
2. Do NOT use Markdown code fences.
3. The result MUST start with <!DOCTYPE html>.
4. Put all CSS inside a <style> tag.
5. Put all JavaScript inside a <script> tag.
6. Everything must be inside ONE HTML file.
7. Do not use external files.
8. Make the website responsive on phones and computers.
9. Make the design polished, modern and visually appealing.
10. Use semantic HTML where appropriate.
11. Do not explain the code.
12. Do not write anything before or after the HTML.
"""

    response = ai.chat.completions.create(

        model="gemini-2.5-flash-lite",

        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    html = response.choices[0].message.content

    if not html:
        raise Exception("AI returned empty response")

    html = html.strip()

    # Remove accidental Markdown code fences
    html = re.sub(
        r"^```html\s*",
        "",
        html,
        flags=re.IGNORECASE
    )

    html = re.sub(
        r"^```\s*",
        "",
        html
    )

    html = re.sub(
        r"\s*```$",
        "",
        html
    )

    html = html.strip()

    if "<!DOCTYPE html>" not in html.upper():

        raise Exception(
            "AI did not return a valid HTML document"
        )

    return html


# =========================
# /start
# =========================

@app.on_message(filters.command("start"))
async def start(client, message):

    user = get_user(
        message.from_user.id
    )

    if user["sites_today"] >= 2:

        await message.reply_text(
            "سلام 👋\n\n"
            "❌ سهمیه امروزت تموم شده.\n"
            "هر کاربر روزانه حداکثر ۲ سایت می‌تونه بسازه."
        )

        return

    user["state"] = "waiting_description"
    user["request"] = ""

    save_users()

    await message.reply_text(
        "سلام 👋🌐\n\n"
        "من Domain Maker هستم.\n\n"
        "توضیح سایتی که می‌خوای رو بفرست.\n\n"
        "مثلاً:\n"
        "یه سایت گیمینگ با تم مشکی و قرمز، "
        "منوی بالا و دکمه شروع بساز.\n\n"
        f"سهمیه امروز: {user['sites_today']}/2"
    )


# =========================
# User Messages
# =========================

@app.on_message(
    filters.text
    & ~filters.command(["start"])
)
async def receive_message(client, message):

    user = get_user(
        message.from_user.id
    )

    # User isn't currently making a website
    if user["state"] != "waiting_description":

        return

    # Daily limit
    if user["sites_today"] >= 2:

        await message.reply_text(
            "❌ سهمیه امروزت تموم شده!\n\n"
            "هر کاربر روزانه فقط ۲ سایت می‌تونه بسازه."
        )

        return

    description = message.text.strip()

    if not description:

        await message.reply_text(
            "❌ لطفاً توضیح سایتت رو بنویس."
        )

        return

    # Save this user's request
    user["request"] = description
    user["state"] = "generating"

    save_users()

    status = await message.reply_text(
        "⏳ توضیحت دریافت شد.\n"
        "دارم سایتت رو می‌سازم..."
    )

    try:

        # Generate HTML
        html = generate_website(
            user["request"]
        )

        # Temporary filename
        filename = (
            f"index_{message.from_user.id}.html"
        )

        # Write HTML file
        with open(
            filename,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(html)

        # Count the generated website
        user["sites_today"] += 1

        user["state"] =