import os
import json
import csv
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# =============================
# ENV VARIABLES
# =============================

TOKEN = os.getenv("TOKEN")
OWNER_CHAT_ID = int(os.getenv("OWNER_CHAT_ID", "1130114131"))
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

# =============================
# GOOGLE SHEETS SETUP
# =============================

scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds_dict = json.loads(GOOGLE_CREDENTIALS)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# =============================
# STATE
# =============================

user_states = {}

# =============================
# KEYBOARDS
# =============================

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

def time_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("09:00", callback_data="09:00"),
         InlineKeyboardButton("10:00", callback_data="10:00"),
         InlineKeyboardButton("11:00", callback_data="11:00")],
        [InlineKeyboardButton("14:00", callback_data="14:00"),
         InlineKeyboardButton("15:00", callback_data="15:00"),
         InlineKeyboardButton("16:00", callback_data="16:00")]
    ])

# =============================
# START
# =============================

def start(update, context):
    update.message.reply_text(
        "Benvenuto 👋\nSistema professionale di prenotazione.",
        reply_markup=main_menu()
    )

# =============================
# BUTTON HANDLER
# =============================

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

    elif data in ["oggi", "domani", "dopodomani"]:
        today = datetime.now()
        if data == "oggi":
            selected_date = today.strftime("%d %B %Y")
        elif data == "domani":
            selected_date = (today + timedelta(days=1)).strftime("%d %B %Y")
        else:
            selected_date = (today + timedelta(days=2)).strftime("%d %B %Y")

        context.user_data["date"] = selected_date
        user_states[chat_id] = "time"
        query.message.reply_text("Seleziona orario:", reply_markup=time_menu())

    elif ":" in data:
        name = context.user_data.get("name")
        phone = context.user_data.get("phone")
        date = context.user_data.get("date")
        time = data

        # Save to Google Sheets
        sheet.append_row([name, phone, date, time])

        owner_msg = (
            f"📌 Nuova prenotazione\n\n"
            f"{date} {time}\n"
            f"{name}\n{phone}"
        )

        context.bot.send_message(chat_id=OWNER_CHAT_ID, text=owner_msg)

        query.message.reply_text(
            "✅ Prenotazione registrata! Ti contatteremo presto.",
            reply_markup=main_menu()
        )

        user_states[chat_id] = "menu"

# =============================
# TEXT HANDLER
# =============================

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

# =============================
# MAIN
# =============================

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, text_handler))

    print("Bot con Google Sheets avviato...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
