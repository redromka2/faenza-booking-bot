# -*- coding: utf-8 -*-

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from datetime import datetime, timedelta
import csv
import os
TOKEN = os.getenv("TOKEN")
OWNER_CHAT_ID = 1130114131

user_states = {}
BOOKINGS_FILE = "prenotazioni.csv"

def load_bookings():
    bookings = []
    if os.path.isfile(BOOKINGS_FILE):
        with open(BOOKINGS_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                bookings.append(row)
    return bookings

def save_booking(name, phone, date, time):
    file_exists = os.path.isfile(BOOKINGS_FILE)
    with open(BOOKINGS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Nome", "Telefono", "Data", "Orario"])
        writer.writerow([name, phone, date, time])

def is_time_available(date, time):
    bookings = load_bookings()
    for b in bookings:
        if b["Data"] == date and b["Orario"] == time:
            return False
    return True

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Prenotazione", callback_data="book")],
        [InlineKeyboardButton("💶 Prezzi", callback_data="prices")],
        [InlineKeyboardButton("📍 Indirizzo", callback_data="address")]
    ])

def date_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Oggi", callback_data="oggi"),
         InlineKeyboardButton("Domani", callback_data="domani")],
        [InlineKeyboardButton("Dopodomani", callback_data="dopodomani")]
    ])

def time_menu(date):
    times = ["09:00","10:00","11:00","14:00","15:00","16:00"]
    keyboard = []
    row = []
    for t in times:
        if is_time_available(date, t):
            row.append(InlineKeyboardButton(t, callback_data=t))
        else:
            row.append(InlineKeyboardButton(f"❌ {t}", callback_data="busy"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

def start(update, context):
    update.message.reply_text(
        "Benvenuto 👋\nSistema professionale di prenotazione.",
        reply_markup=main_menu()
    )

def admin(update, context):
    if update.message.chat_id != OWNER_CHAT_ID:
        update.message.reply_text("Accesso negato.")
        return

    bookings = load_bookings()
    if not bookings:
        update.message.reply_text("Nessuna prenotazione.")
        return

    text = "📋 Prenotazioni:\n\n"
    for b in bookings:
        text += f"{b['Data']} {b['Orario']} - {b['Nome']} ({b['Telefono']})\n"

    update.message.reply_text(text)

def button_handler(update, context):
    query = update.callback_query
    query.answer()
    data = query.data
    chat_id = query.message.chat_id

    if data == "book":
        user_states[chat_id] = "name"
        query.message.reply_text("Inserisci il tuo nome:")

    elif data == "prices":
        query.edit_message_text(
            "💶 Prezzi:\nTaglio - 20€\nBarba - 10€\nTaglio+Barba - 25€",
            reply_markup=main_menu()
        )

    elif data == "address":
        query.edit_message_text(
            "📍 Via Roma 10, Faenza",
            reply_markup=main_menu()
        )

    elif data in ["oggi","domani","dopodomani"]:
        today = datetime.now()
        if data == "oggi":
            date = today.strftime("%d %B %Y")
        elif data == "domani":
            date = (today + timedelta(days=1)).strftime("%d %B %Y")
        else:
            date = (today + timedelta(days=2)).strftime("%d %B %Y")

        context.user_data["date"] = date
        user_states[chat_id] = "time"
        query.message.reply_text("Seleziona orario:", reply_markup=time_menu(date))

    elif data == "busy":
        query.answer("Orario già occupato ❌")

    elif ":" in data:
        date = context.user_data.get("date")
        if not is_time_available(date, data):
            query.answer("Orario già occupato ❌")
            return

        context.user_data["time"] = data
        name = context.user_data.get("name")
        phone = context.user_data.get("phone")

        save_booking(name, phone, date, data)

        owner_msg = (
            f"📌 Nuova prenotazione\n\n"
            f"{date} {data}\n"
            f"{name}\n{phone}"
        )

        context.bot.send_message(chat_id=OWNER_CHAT_ID, text=owner_msg)

        query.message.reply_text(
            "✅ Prenotazione confermata! Ti contatteremo presto.",
            reply_markup=main_menu()
        )

        user_states[chat_id] = "menu"

def text_handler(update, context):
    chat_id = update.message.chat_id
    state = user_states.get(chat_id)

    if state == "name":
        context.user_data["name"] = update.message.text
        user_states[chat_id] = "phone"
        update.message.reply_text("Inserisci telefono:")

    elif state == "phone":
        context.user_data["phone"] = update.message.text
        user_states[chat_id] = "date"
        update.message.reply_text("Seleziona data:", reply_markup=date_menu())

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("admin", admin))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, text_handler))

    print("ULTRA Bot avviato...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
