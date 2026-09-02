import os
import json
import re
from datetime import date

from dotenv import load_dotenv
from pyrogram import Client, filters
from openai import OpenAI


load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

USERS_FILE = "users.json"


ai = OpenAI(
    base_url="https://aimodelapi.onrender.com/v1",
    api_key=GEMINI_API_KEY
)


def load_users():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
        return {}

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_users():
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


users = load_users()


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

    if user.get("last_date") != today:
        user["sites_today"] = 0
        user["last_date"] = today
        user["state"] = "idle"
        user["request"] = ""
        save_users()

    return user


app = Client(
    "domain_maker_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


def generate_website(description):

    prompt = f"""
You are Domain Maker, an expert web developer.

Create a complete modern website based on this description:

{description}

RULES:

1. Return ONLY HTML code.
2. Do NOT use Markdown.
3. Do NOT use ```html.
4. Do NOT explain anything.
5. Everything must be inside ONE HTML file.
6. Include HTML, CSS and JavaScript in the same file.
7. Put CSS inside <style>.
8. Put JavaScript inside <script>.
9. Make it responsive.
10. Make the design modern and polished.
11. Start with <!DOCTYPE html>.
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

    html = re.sub(
        r"^```(?:html)?\s*",
        "",
        html,
        flags=re.IGNORECASE
    )

    html = re.sub(
        r"\s*```$",
        "",
        html
    )

    html = html.strip()

    lower = html.lower()

    doctype = lower.find("<!doctype html>")
    html_start = lower.find("<html")

    if doctype != -1:
        html = html[doctype:]

    elif html_start != -1:
        html = html[html_start:]
        html = "<!DOCTYPE html>\n" + html

    else:
        raise Exception("AI did not return HTML")

    if "<html" not in html.lower():
        raise Exception("AI did not return valid HTML")

    return html


@app.on_message(filters.command("start"))
async def start(client, message):

    user = get_user(message.from_user.id)

    if user["sites_today"] >= 2:
        await message.reply_text(
            "❌ سهمیه امروزت تموم شده.\n\n"
            "هر کاربر روزانه فقط ۲ سایت می‌تونه بسازه."
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
        "یه سایت گیمینگ با تم مشکی و قرمز بساز.\n\n"
        f"سهمیه امروز: {user['sites_today']}/2"
    )


@app.on_message(filters.command("site"))
async def site_command(client, message):

    user = get_user(message.from_user.id)

    if user["sites_today"] >= 2:
        await message.reply_text(
            "❌ سهمیه امروزت تموم شده.\n\n"
            "هر کاربر روزانه فقط ۲ سایت می‌تونه بسازه."
        )
        return

    user["state"] = "waiting_description"
    user["request"] = ""

    save_users()

    await message.reply_text(
        "🌐 توضیح سایتی که می‌خوای رو بفرست.\n\n"
        "مثلاً:\n"
        "یه سایت گیمینگ با تم مشکی و قرمز بساز.\n\n"
        f"سهمیه امروز: {user['sites_today']}/2"
    )


@app.on_message(
    filters.text
    & ~filters.command(["start", "site"])
)
async def receive_message(client, message):

    user = get_user(message.from_user.id)

    if user["state"] != "waiting_description":
        return

    if user["sites_today"] >= 2:
        await message.reply_text(
            "❌ سهمیه امروزت تموم شده!"
        )
        return

    description = message.text.strip()

    if not description:
        return

    user["request"] = description
    user["state"] = "generating"

    save_users()

    status = await message.reply_text(
        "⏳ توضیحت دریافت شد.\n"
        "دارم سایتت رو می‌سازم..."
    )

    try:

        html = generate_website(
            user["request"]
        )

        filename = f"index_{message.from_user.id}.html"

        with open(
            filename,
            "w",
            encoding="utf-8"
        ) as f:
            f.write(html)

        user["sites_today"] += 1
        user["state"] = "idle"
        user["request"] = ""

        save_users()

        try:
            await status.delete()
        except Exception:
            pass

        await message.reply_document(
            filename,
            caption=(
                "✅ سایتت آماده شد! 🌐\n\n"
                f"سهمیه امروز: "
                f"{user['sites_today']}/2"
            )
        )

        try:
            os.remove(filename)
        except OSError:
            pass

    except Exception as e:

        print("AI ERROR:", repr(e))

        user["state"] = "idle"
        user["request"] = ""

        save_users()

        try:
            await status.edit_text(
                "❌ هنگام ساخت سایت خطایی رخ داد.\n\n"
                "دوباره /site رو بزن."
            )
        except Exception:
            pass


print("🚀 Domain Maker Bot Started!")

app.run()
