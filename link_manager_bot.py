import os
import sqlite3
import logging
import asyncio
import datetime
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

# Logging setup
logging.basicConfig(level=logging.INFO)

# Get bot token and admin ID from environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
except (TypeError, ValueError):
    ADMIN_ID = None  # If not set correctly, the bot will not accept any commands

DB_NAME = "links.db"
PAGE_SIZE = 5  # Number of links per page

# ------------------ Database Setup ------------------

def init_db():
    """Initialize the SQLite database if it doesn't exist."""
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
    """Adds a link into the database with a determined type."""
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
    """Return a list of links for the given page."""
    offset = (page - 1) * PAGE_SIZE
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, url, type, added FROM links ORDER BY id ASC LIMIT ? OFFSET ?", (PAGE_SIZE, offset))
    rows = c.fetchall()
    conn.close()
    return rows

def count_links():
    """Return the total number of stored links."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM links")
    count = c.fetchone()[0]
    conn.close()
    return count

# ------------------ Link Checking ------------------

def check_url(url: str) -> str:
    """Check if a URL is working by sending a GET request."""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code in [200, 301, 302]:
            return "Working"
        else:
            return f"Error: {response.status_code}"
    except Exception as e:
        return f"Failed: {str(e)}"

# ------------------ Command Handlers ------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start command: Shows the welcome message."""
    if update.effective_user.id != ADMIN_ID:
        return  # Only admin can use the bot
    msg = (
        "Welcome to your Private Link Manager Bot.\n\n"
        "• Send me a Telegram channel link (contains t.me) or a Mega link (contains mega.nz) to store it privately.\n"
        "• Use /viewlinks to see stored links (with next and previous buttons).\n"
        "• Use /checklinks to check if all your stored links are working.\n"
    )
    await update.message.reply_text(msg)

async def store_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store a link sent by the admin."""
    if update.effective_user.id != ADMIN_ID:
        return
    text = update.message.text.strip()
    # Only store if it looks like a Telegram or Mega link
    if "t.me" in text or "mega.nz" in text:
        add_link(text)
        await update.message.reply_text("Link stored privately.")
    else:
        await update.message.reply_text("This link doesn't appear to be a Telegram or Mega link. Ignored.")

async def viewlinks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/viewlinks command: Shows a paginated list of stored links."""
    if update.effective_user.id != ADMIN_ID:
        return
    await send_link_page(update, 1)

async def send_link_page(update_or_callback, page: int):
    """Helper: Send a page of links with pagination buttons."""
    links = get_links(page)
    total = count_links()
    text = f"Stored Links (Page {page}):\n\n"
    if not links:
        text += "No links found."
    else:
        for link in links:
            text += f"ID: {link[0]} | Type: {link[2]}\nURL: {link[1]}\nAdded: {link[3]}\n\n"
    # Create pagination buttons
    keyboard = []
    if page > 1:
        keyboard.append(InlineKeyboardButton("Previous", callback_data=f"page_{page-1}"))
    if total > page * PAGE_SIZE:
        keyboard.append(InlineKeyboardButton("Next", callback_data=f"page_{page+1}"))
    reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None

    # If the update is a callback query, edit the message; otherwise send a new one.
    if hasattr(update_or_callback, "callback_query") and update_or_callback.callback_query:
        await update_or_callback.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
    else:
        await update_or_callback.message.reply_text(text, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pagination button presses."""
    query = update.callback_query
    if query:
        data = query.data
        match = re.match(r"page_(\d+)", data)
        if match:
            page = int(match.group(1))
            await send_link_page(update, page)

async def checklinks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check each stored link’s status."""
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("Checking stored links. Please wait...")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, url FROM links ORDER BY id ASC")
    rows = c.fetchall()
    conn.close()

    results = ""
    # Check each link (running the synchronous check_url in an executor)
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
    # All other text messages: attempt to store link if valid
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, store_link))
    app.run_polling()

if __name__ == "__main__":
    main()
