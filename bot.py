import asyncio
import psycopg2
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# PostgreSQL ulanish
conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT")
)
cursor = conn.cursor()

# --- Reply keyboard (buttonlar) ---
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Ismni yangilash")],
        [KeyboardButton(text="Telefon raqamini yangilash")],
        [KeyboardButton(text="Ma’lumotlarni ko‘rish")]
    ],
    resize_keyboard=True
)

statuslar = {
        'pending': "Qo'yish uchun olib qolindi",
        'start': "Inkubatorga qo'yildi",
        'finished': "Inkubatordan ochib chiqdi",
        'completed': "Egasi olib ketdi"
}

# --- User step tracking ---
user_steps = {}  # chat_id -> "name" yoki "phone" yoki None

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    chat_id = message.from_user.id

    # User bazada bormi tekshirish
    cursor.execute("SELECT id FROM orders_user WHERE chat_id = %s", (chat_id,))
    result = cursor.fetchone()
    if not result:
        cursor.execute("INSERT INTO orders_user (chat_id) VALUES (%s) RETURNING id", (chat_id,))
        conn.commit()
    user_steps[chat_id] = None
    await message.answer(
        "Xush kelibsiz! Quyidagi tugmalar orqali harakat qilishingiz mumkin:",
        reply_markup=keyboard
    )
    return

@dp.message()
async def echo_handler(message: types.Message) -> None:
    text = message.text
    chat_id = message.from_user.id

    if text == "Ismni yangilash":
        user_steps[chat_id] = "name"
        await message.answer("Ismingizni kiriting")
    elif text == "Telefon raqamini yangilash":
        user_steps[chat_id] = "phone"
        await message.answer("Telefon raqamingizni kiriting, masalan 99 999 99 99")
    elif text == "Ma’lumotlarni ko‘rish":
        cursor.execute("SELECT id, name, phone, description FROM orders_user WHERE chat_id = %s", (chat_id,))
        user_row = cursor.fetchone()
        if not user_row:
            await message.answer("Siz ro'yxatdan o'tmagansiz", reply_markup=keyboard)
        else:
            user_id = user_row[0]
            cursor.execute("SELECT egg_id, start_date, getting_count, status, putting_count from orders_order where user_id = %s ORDER BY created_at, start_date", (user_id, ))
            user_orders = cursor.fetchall()

            lines = []
            for order in user_orders:
                # Tuple ni index orqali oling
                egg_id = order[0]
                start_date = order[1] or "Aniqlanmagan"
                getting_count = order[2]
                status = order[3] or "Aniqlanmagan"
                putting_count = order[4]

                full_data = (f"🥚 Tuxum ID: {egg_id}\n📅Inkubatorga qo'yilgan Sana: {start_date}\n➕ Qo‘yilgan: {putting_count}"
                             f"\n➖ Olingan: {getting_count}\n📌 Status: {statuslar.get(status, "Noma'lum")}")

                days_on_inkubator = 0
                if start_date != "Aniqlanmagan":
                    days_on_inkubator = (datetime.datetime.now() - datetime.datetime.strptime(str(start_date), "%Y-%m-%d")).days
                    full_data += f"\n🥚 Inkubatordagi {days_on_inkubator + 1}-kun"

                lines.append(full_data)

            orders_text = "\n\n\n".join(lines)
            await message.answer(f"Sizga tegishli orderlar:\n\n{orders_text}", reply_markup=keyboard)
    else:
        if user_steps[chat_id] == "name":
            cursor.execute("UPDATE orders_user SET name = %s WHERE chat_id = %s", (text, chat_id))
            conn.commit()
            await message.answer(f"Ismingiz '{text}' ga o‘zgartirildi!", reply_markup=keyboard)
            user_steps[chat_id] = None
        elif user_steps[chat_id] == "phone":
            cursor.execute("UPDATE orders_user SET phone = %s WHERE chat_id = %s", (text, chat_id))
            conn.commit()
            await message.answer(f"Telefon raqamingiz '{text}' ga o‘zgartirildi!", reply_markup=keyboard)
            user_steps[chat_id] = None
        elif user_steps[chat_id] == "info":
            cursor.execute("SELECT id, name, phone, description FROM orders_user WHERE chat_id = %s", (chat_id,))
            user_row = cursor.fetchone()
            if not user_row:
                await message.answer("Siz ro'yxatdan o'tmagansiz", reply_markup=keyboard)


# --- Botni ishga tushirish ---
async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())