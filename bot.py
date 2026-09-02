import os
import json
import re
from datetime import date

from dotenv import load_dotenv
from pyrogram import Client, filters
from google import genai


# =========================
# تنظیمات
# =========================

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

USERS_FILE = "users.json"

gemini = genai.Client(api_key=GEMINI_API_KEY)


# =========================
# مدیریت کاربران
# =========================

def load_users():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

        return {}

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except (json.JSONDecodeError, OSError):
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

    # ریست سهمیه در روز جدید
    if user.get("last_date") != today:
        user["sites_today"] = 0
        user["last_date"] = today
        user["state"] = "idle"
        user["request"] = ""
        save_users()

    return user


# =========================
# ساخت بات
# =========================

app = Client(
    "domain_maker_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# =========================
# /start
# =========================

@app.on_message(filters.command("start"))
async def start(client, message):

    user = get_user(message.from_user.id)

    if user["sites_today"] >= 2:
        await message.reply_text(
            "سلام 👋\n\n"
            "سهمیه امروزت استفاده شده.\n"
            "هر کاربر روزانه حداکثر ۲ سایت می‌تونه بسازه."
        )
        return

    user["state"] = "waiting_description"
    user["request"] = ""

    save_users()

    await message.reply_text(
        "سلام 👋🌐\n\n"
        "توضیح سایتی که می‌خوای رو برام بفرست.\n\n"
        "مثلاً:\n"
        "یه سایت گیمینگ با تم مشکی و قرمز، "
        "منوی بالا و یک دکمه شروع بساز.\n\n"
        f"سهمیه امروز: {user['sites_today']}/2"
    )


# =========================
# تولید سایت
# =========================

async def generate_website(description):

    prompt = f"""
You are Domain Maker, an expert web developer.

Create a complete modern website based on the user's description below.

USER DESCRIPTION:
{description}

IMPORTANT RULES:

1. Return ONLY the complete HTML document.
2. Do NOT use Markdown code fences.
3. The result must start with <!DOCTYPE html>.
4. Put CSS inside a <style> tag.
5. Put JavaScript inside a <script> tag.
6. Everything must be inside ONE HTML file.
7. Make the website responsive for phones and computers.
8. Make the design polished and modern.
9. Do not explain the code.
10. Do not include anything before or after the HTML document.
"""

    response = gemini.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt
    )

    html = response.text.strip()

    # اگر مدل اشتباهی Markdown برگرداند
    html = re.sub(r"^```html\s*", "", html, flags=re.IGNORECASE)
    html = re.sub(r"^```\s*", "", html)
    html = re.sub(r"\s*```$", "", html)

    return html.strip()


# =========================
# دریافت درخواست کاربر
# =========================

@app.on_message(
    filters.text
    & ~filters.command(["start"])
)
async def receive_message(client, message):

    user = get_user(message.from_user.id)

    # فقط وقتی منتظر توضیح سایت هستیم
    if user["state"] != "waiting_description":
        return

    # بررسی سهمیه
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

    # ذخیره درخواست مخصوص همین کاربر
    user["request"] = description
    user["state"] = "generating"

    save_users()

    status = await message.reply_text(
        "⏳ درخواستت دریافت شد.\n"
        "دارم سایت رو با Gemini می‌سازم..."
    )

    try:

        html = await generate_website(
            user["request"]
        )

        # ساخت فایل مخصوص همین درخواست
        filename = f"index_{message.from_user.id}.html"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)

        # ثبت مصرف سهمیه
        user["sites_today"] += 1
        user["state"] = "waiting_description"
        user["request"] = ""

        save_users()

        await status.delete()

        await message.reply_document(
            filename,
            caption=(
                "✅ سایتت آماده شد! 🌐\n\n"
                f"سهمیه امروز: "
                f"{user['sites_today']}/2"
            )
        )

        # حذف فایل موقت
        try:
            os.remove(filename)
        except OSError:
            pass

    except Exception as e:

        print("Gemini Error:", e)

        user["state"] = "waiting_description"
        user["request"] = ""

        save_users()

        await status.edit_text(
            "❌ متأسفانه هنگام ساخت سایت خطایی رخ داد.\n"
            "دوباره امتحان کن."
        )


# =========================
# اجرای بات
# =========================

print("Domain Maker Bot Started!")

app.run()