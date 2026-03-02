import os
import json
import smtplib
from email.mime.text import MIMEText
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

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")


# =============================
# GOOGLE SHEETS SETUP
# =============================

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = json.loads(GOOGLE_CREDENTIALS)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1


# =============================
# EMAIL FUNCTION
# =============================

def send_email_notification(subject, body):
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print("Email credentials missing")
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_ADDRESS  # можно заменить на другой email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print("Email error:", e)


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


def time_menu(selected_date):
    times = ["09:00","10:00","11:00","12:00","13:00",
             "14:00","15:00","16:00","17:00"]

    records = sheet.get_all_records()

    busy_times = [
        r["Orario"]
        for r in records
        if r["Data"] == selected_date
    ]

    keyboard = []
    row = []

    for t in times:
        if t in busy_times:
            row.append(
                InlineKeyboardButton(f"❌ {t}", callback_data="busy")
            )
        else:
            row.append(
                InlineKeyboardButton(t, callback_data=t)
            )

        if len(row) == 3:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    return InlineKeyboardMarkup(keyboard)


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
            "💶 Prezzi:\n"
            "Taglio - 20€\n"
            "Barba - 10€\n"
            "Taglio+Barba - 25€",
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

        query.message.reply_text(
            "Seleziona orario:",
            reply_markup=time_menu(selected_date)
        )

    elif data == "busy":
        query.answer("Orario già occupato ❌")

    elif ":" in data:

        name = context.user_data.get("name")
        phone = context.user_data.get("phone")
        date = context.user_data.get("date")
        time = data

        # повторная проверка
        records = sheet.get_all_records()
        for r in records:
            if r["Data"] == date and r["Orario"] == time:
                query.answer("Orario appena occupato ❌")
                return

        # запись в Google Sheets
        sheet.append_row([name, phone, date, time])

        # Telegram уведомление
        owner_msg = (
            f"📌 Nuova prenotazione\n\n"
            f"{date} {time}\n"
            f"{name}\n{phone}"
        )

        context.bot.send_message(chat_id=OWNER_CHAT_ID, text=owner_msg)

        # Email уведомление
        email_subject = "Nuova Prenotazione"
        email_body = f"""
Nuova prenotazione ricevuta

Data: {date}
Orario: {time}
Nome: {name}
Telefono: {phone}
"""
        send_email_notification(email_subject, email_body)

        query.message.reply_text(
            "✅ Prenotazione registrata!",
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
        update.message.reply_text(
            "Seleziona data:",
            reply_markup=date_menu()
        )


# =============================
# MAIN
# =============================

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, text_handler))

    print("Bot con Google Sheets + Email avviato...")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
