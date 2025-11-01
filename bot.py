from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import logging
import os
import json
from dotenv import load_dotenv

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

load_dotenv()  # Load variables from .env

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
google_creds = os.getenv("GOOGLE_CREDS_JSON")

if google_creds:
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(google_creds), scope)
    client = gspread.authorize(creds)
    sheet = client.open("PresenceMatic Orders").sheet1
else:
    sheet = None

# Store user states (simple memory session)
user_sessions = {}


@app.route("/bot", methods=["POST"])
def bot():
    # Safely access form data
    form = request.form or {}
    user_msg = (form.get("Body") or "").strip()
    user_num = form.get("From") or "unknown"
    resp = MessagingResponse()
    msg = resp.message()

    if not user_msg:
        msg.body("Sorry, I didn't receive any message. Type *Hi* to start your order.")
        return str(resp)

    # normalize for comparisons but keep original for storing
    user_msg_l = user_msg.lower()

    # Start Conversation
    if user_msg_l in ["hi", "hello", "hey"]:
        msg.body("👋 Hi! Welcome to *PresenceMatic Café*.\nWould you like to see our menu? (yes/no)")
        user_sessions[user_num] = {"stage": "menu"}
        return str(resp)

    # Menu display
    if user_sessions.get(user_num, {}).get("stage") == "menu" and user_msg_l == "yes":
        menu = "🍽️ *Menu*\n1️⃣ Cold Coffee ₹120\n2️⃣ Paneer Roll ₹110\n3️⃣ Veg Sandwich ₹90\n\nReply with item numbers (e.g. 1,3)."
        msg.body(menu)
        user_sessions[user_num]["stage"] = "order"
        return str(resp)

    # Taking order
    if user_sessions.get(user_num, {}).get("stage") == "order":
        user_sessions[user_num]["items"] = user_msg
        msg.body("Great choice 😋! Please share your delivery address 🏠")
        user_sessions[user_num]["stage"] = "address"
        return str(resp)

    # Taking address and storing data
    if user_sessions.get(user_num, {}).get("stage") == "address":
        address = user_msg
        items = user_sessions[user_num].get("items", "")

        # Prepare row and attempt to append to Google Sheets if available
        row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_num, items, address, "Pending"]
        if sheet:
            try:
                sheet.append_row(row)
            except Exception as e:
                logging.warning("Failed to append row to Google Sheets: %s", e)
        else:
            logging.info("Sheet not available; order not saved to Google Sheets: %s", row)

        msg.body("✅ Thank you! Your order has been received.\nOur team will call you shortly for confirmation ☎️.")
        user_sessions[user_num]["stage"] = "done"
        return str(resp)

    # Default fallback
    msg.body("Type *Hi* to start your order again 😊")
    return str(resp)


if __name__ == "__main__":
    app.run(debug=True)
