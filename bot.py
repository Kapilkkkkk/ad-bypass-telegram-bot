import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import aiohttp

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# In-memory storage for links
links = []

# Command: /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands = (
        "/add <link> - Add a new link\n"
        "/links - View stored links\n"
        "/check - Check all links\n"
        "/delete <index> - Delete a specific link by its index"
    )
    await update.message.reply_text(f"Welcome! Here are the available commands:\n{commands}")

# Command: /add
async def add_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to add links.")
        return

    if context.args:
        url = context.args[0].strip()
        if url.startswith("https://mega.nz/") or "t.me/" in url:
            links.append(url)
            await update.message.reply_text("Link stored successfully.")
        else:
            await update.message.reply_text("Only MEGA or Telegram links are allowed.")
    else:
        await update.message.reply_text("Please provide a link. Usage: /add <link>")

# Command: /links
async def view_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to view links.")
        return

    if not links:
        await update.message.reply_text("No links saved.")
        return

    keyboard = [
        [InlineKeyboardButton("Check Links", callback_data='check')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = "\n".join([f"{idx + 1}. {link}" for idx, link in enumerate(links)])
    await update.message.reply_text(message, reply_markup=reply_markup)

# Callback Query Handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Acknowledge the callback query

    if query.data == "check":
        await check_links(update, context)

# Command: /check
async def check_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not links:
        await update.message.reply_text("No links to check.")
        return

    results = []
    async with aiohttp.ClientSession() as session:
        for link in links:
            try:
                async with session.head(link, timeout=10) as resp:
                    if resp.status == 200:
                        results.append(f"✅ {link} is working.")
                    else:
                        results.append(f"❌ {link} is not working (Status Code: {resp.status}).")
            except Exception as e:
                results.append(f"❌ {link} could not be reached. Error: {str(e)}")

    await update.message.reply_text("\n".join(results))

# Command: /delete
async def delete_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to delete links.")
        return

    if context.args:
        try:
            index = int(context.args[0]) - 1
            if 0 <= index < len(links):
                removed_link = links.pop(index)
                await update.message.reply_text(f"Deleted link: {removed_link}")
            else:
                await update.message.reply_text("Invalid index.")
        except ValueError:
            await update.message.reply_text("Please provide a valid index number.")
    else:
        await update.message.reply_text("Please provide the index of the link to delete. Usage: /delete <index>")

# Main Function
def main():
    if not BOT_TOKEN or not ADMIN_ID:
        logger.error("BOT_TOKEN or ADMIN_ID is not set.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_link))
    app.add_handler(CommandHandler("links", view_links))
    app.add_handler(CommandHandler("check", check_links))
    app.add_handler(CommandHandler("delete", delete_link))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
