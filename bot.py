from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import logging
import os
import json
from dotenv import load_dotenv

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

sheet = None
try:
    google_creds = os.getenv("GOOGLE_CREDS_JSON")

    if google_creds:
        # Parse the JSON credentials stored in .env
        creds_dict = json.loads(google_creds)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("PresenceMatic Orders").sheet1
        logging.info("✅ Connected to Google Sheets successfully.")
    else:
        logging.warning("❌ GOOGLE_CREDS_JSON not found in environment variables.")

except Exception as e:
    logging.warning("⚠️ Google Sheets setup failed: %s", e)

# In-memory user sessions
user_sessions = {}


@app.route("/bot", methods=["POST"])
def bot():
    """Main WhatsApp bot logic"""
    form = request.form or {}
    user_msg = (form.get("Body") or "").strip()
    user_num = form.get("From") or "unknown"

    resp = MessagingResponse()
    msg = resp.message()

    if not user_msg:
        msg.body("Sorry, I didn't receive any message. Type *Hi* to start your order.")
        return str(resp)

    user_msg_l = user_msg.lower()

    # Start conversation
    if user_msg_l in ["hi", "hello", "hey"]:
        msg.body("👋 Hi! Welcome to *PresenceMatic Café*.\nWould you like to see our menu? (yes/no)")
        user_sessions[user_num] = {"stage": "menu"}
        return str(resp)

    # Show menu
    if user_sessions.get(user_num, {}).get("stage") == "menu" and user_msg_l == "yes":
        menu = (
            "🍽️ *Menu*\n"
            "1️⃣ Cold Coffee ₹120\n"
            "2️⃣ Paneer Roll ₹110\n"
            "3️⃣ Veg Sandwich ₹90\n\n"
            "Reply with item numbers (e.g. 1,3)."
        )
        msg.body(menu)
        user_sessions[user_num]["stage"] = "order"
        return str(resp)

    # Take order
    if user_sessions.get(user_num, {}).get("stage") == "order":
        user_sessions[user_num]["items"] = user_msg
        msg.body("Great choice 😋! Please share your delivery address 🏠")
        user_sessions[user_num]["stage"] = "address"
        return str(resp)

    # Take address and save to Google Sheet
    if user_sessions.get(user_num, {}).get("stage") == "address":
        address = user_msg
        items = user_sessions[user_num].get("items", "")

        # Prepare data row
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_num,
            items,
            address,
            "Pending"
        ]

        # Try saving order to Google Sheets
        if sheet:
            try:
                sheet.append_row(row)
                logging.info("✅ Order saved to Google Sheets: %s", row)
            except Exception as e:
                logging.warning("⚠️ Failed to save order to Google Sheets: %s", e)
        else:
            logging.info("⚠️ Sheet not available; order not saved: %s", row)

        msg.body("✅ Thank you! Your order has been received.\nOur team will call you shortly for confirmation ☎️.")
        user_sessions[user_num]["stage"] = "done"
        return str(resp)

    # Fallback
    msg.body("Type *Hi* to start your order again 😊")
    return str(resp)


if __name__ == "__main__":
    app.run(debug=True)
