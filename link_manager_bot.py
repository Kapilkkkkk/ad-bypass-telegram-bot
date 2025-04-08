import os
import sqlite3
import logging
import asyncio
import re
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Basic logging configuration
logging.basicConfig(level=logging.INFO)

# Retrieve sensitive data from environment variables.
BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
except (TypeError, ValueError):
    ADMIN_ID = None  # Without this, the bot will ignore commands.

DB_NAME = "links.db"
PAGE_SIZE = 5  # Number of links to display per page

# ------------------ Database Functions ------------------

def init_db():
    """Initialize SQLite database if it doesn't exist."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            type TEXT,
            added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def add_link(url: str):
    """Store the link in the database, categorizing it as 'telegram', 'mega', or 'other'."""
    if "t.me" in url:
        link_type = "telegram"
    elif "mega.nz" in url:
        link_type = "mega"
    else:
        link_type = "other"
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO links (url, type) VALUES (?, ?)", (url, link_type))
    conn.commit()
    conn.close()

def get_links(page: int):
    """Return a list of stored links for the given page."""
    offset = (page - 1) * PAGE_SIZE
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, url, type, added FROM links ORDER BY id ASC LIMIT ? OFFSET ?", (PAGE_SIZE, offset))
    rows = c.fetchall()
    conn.close()
    return rows

def count_links():
    """Return the total count of stored links."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM links")
    count = c.fetchone()[0]
    conn.close()
    return count

# ------------------ URL Checking Function ------------------

def check_url(url: str) -> str:
    """Perform a GET request to the URL and return whether it's working."""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code in [200, 301, 302]:
            return "Working"
        else:
            return f"Error: HTTP {response.status_code}"
    except Exception as e:
        return f"Failed: {str(e)}"

# ------------------ Command Handlers ------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /start command and shows an inline keyboard with buttons."""
    if update.effective_user.id != ADMIN_ID:
        return  # Only the admin can interact with the bot.
    
    keyboard = [
        [InlineKeyboardButton("View Links", callback_data="view_links")],
        [InlineKeyboardButton("Check Links", callback_data="check_links")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = (
        "Welcome to your Private Link Manager Bot.\n\n"
        "• Send me a Telegram channel link (contains t.me) or a Mega link (contains mega.nz) to store it privately.\n"
        "• Use the buttons below to view stored links or to check the status of stored links."
    )
    await update.message.reply_text(msg, reply_markup=reply_markup)

async def store_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stores a link if the message text contains a Telegram or Mega link."""
    if update.effective_user.id != ADMIN_ID:
        return
    text = update.message.text.strip()
    if "t.me" in text or "mega.nz" in text:
        add_link(text)
        await update.message.reply_text("Link stored privately.")
    else:
        await update.message.reply_text("This message doesn't appear to contain a Telegram or Mega link. Ignored.")

async def viewlinks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /viewlinks command by sending the first page of stored links."""
    if update.effective_user.id != ADMIN_ID:
        return
    await send_link_page(update, 1)

async def send_link_page(update_or_callback, page: int):
    """Helper to send a paginated list of links with Next/Previous buttons."""
    links = get_links(page)
    total = count_links()
    text = f"Stored Links (Page {page}):\n\n"
    if not links:
        text += "No links stored."
    else:
        for link in links:
            text += f"ID: {link[0]} | Type: {link[2]}\nURL: {link[1]}\nAdded: {link[3]}\n\n"
    keyboard = []
    if page > 1:
        keyboard.append(InlineKeyboardButton("Previous", callback_data=f"page_{page - 1}"))
    if total > page * PAGE_SIZE:
        keyboard.append(InlineKeyboardButton("Next", callback_data=f"page_{page + 1}"))
    reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None

    # Depending on whether this is a message or callback, send appropriately:
    if hasattr(update_or_callback, "callback_query") and update_or_callback.callback_query:
        await update_or_callback.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
    else:
        await update_or_callback.message.reply_text(text, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles callback queries from inline buttons."""
    query = update.callback_query
    data = query.data
    if data == "view_links":
        await send_link_page(update, 1)
    elif data == "check_links":
        # Directly call the checklinks handler
        await checklinks(update, context)
    else:
        # Handle pagination callbacks e.g. page_2, page_3, etc.
        match = re.match(r"page_(\d+)", data)
        if match:
            page = int(match.group(1))
            await send_link_page(update, page)

async def checklinks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Checks the status of all stored links and returns a report."""
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("Checking stored links. Please wait...")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, url FROM links ORDER BY id ASC")
    rows = c.fetchall()
    conn.close()

    results = ""
    for row in rows:
        link_id, url = row
        status = await asyncio.to_thread(check_url, url)
        results += f"ID: {link_id} | URL: {url}\nStatus: {status}\n\n"
    if not results:
        results = "No links stored."
    await update.message.reply_text(results)

# ------------------ Main Function ------------------

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("viewlinks", viewlinks))
    app.add_handler(CommandHandler("checklinks", checklinks))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, store_link))
    app.run_polling()

if __name__ == "__main__":
    main()
