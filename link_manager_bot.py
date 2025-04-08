import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import aiohttp

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Store links in memory (consider using a database for persistence)
links = []
current_page = 0

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands = (
        "/add <link> - Add a new link\n"
        "/links - View stored links\n"
        "/check - Check all links\n"
        "/delete <index> - Delete a specific link by its index"
    )
    await update.message.reply_text(f"👋 Welcome! Here are the available commands:\n{commands}")

async def add_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        return await update.message.reply_text("❌ You are not authorized to add links.")

    if context.args:
        url = context.args[0].strip()
        if url.startswith("https://mega.nz/") or "t.me/" in url:
            links.append(url)
            await update.message.reply_text("✅ Link stored securely.")
        else:
            await update.message.reply_text("❌ Only MEGA or Telegram links are allowed.")
    else:
        await update.message.reply_text("❌ Please provide a link. Usage: /add <link>")

async def view_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return await update.message.reply_text("❌ Not allowed.")

    if not links:
        return await update.message.reply_text("No links saved.")

    global current_page
    current_page = 0
    await show_page(update, context)

async def show_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not links:
        return await update.message.reply_text("No links saved.")

    start = current_page * 5
    end = start + 5
    page_links = links[start:end]
    text = "\n".join([f"{i+1+start}. {link}" for i, link in enumerate(page_links)])

    keyboard = [
        [
            InlineKeyboardButton("⬅️ Previous", callback_data='prev'),
            InlineKeyboardButton("➡️ Next", callback_data='next')
        ],
        [InlineKeyboardButton("🔍 Check Links", callback_data='check')],
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    global current_page

    if query.data == "next":
        if (current_page + 1) * 5 < len(links):
            current_page += 1
    elif query.data == "prev":
        if current_page > 0:
            current_page -= 1
    elif query.data == "check":
        return await check_links(update, context)

    await show_page(query, context)

async def check_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🔍 Checking links...\n"
    results = []
    async with aiohttp.ClientSession() as session:
        for link in links:
            try:
                async with session.get(link, timeout=10) as resp:
                    if resp.status == 200:
                        results.append(f"✅ Working: {link}")
                    else:
                        results.append(f"❌ Not Working ({resp.status}): {link}")
            except:
                results.append(f"❌ Error: {link}")

    await update.callback_query.message.reply_text("\n".join(results))

async def delete_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        return await update.message.reply_text("❌ You are not authorized to delete links.")

    if context.args:
        try:
            index = int(context.args[0]) - 1
            if 0 <= index < len(links):
                removed_link = links.pop(index)
                await update.message.reply_text(f"✅ Deleted link: {removed_link}")
            else:
                await update.message.reply_text("❌ Invalid index.")
        except ValueError:
            await update.message.reply_text("❌ Please provide a valid index number.")
    else:
        await update.message.reply_text("❌ Please provide the index of the link to delete. Usage: /delete <index>")

# --- Main ---

if __name__ == '__main__':
    if not BOT_TOKEN or not ADMIN_ID:
        print("Error: Missing BOT_TOKEN or ADMIN_ID in environment variables.")
        exit(1)

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_link))
    app.add_handler(CommandHandler("links", view_links))
    app.add_handler(CommandHandler("check", check_links))
    app.add_handler(CommandHandler("delete", delete_link))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_link))

    print("🤖 Bot is running...")
    app.run_polling()
