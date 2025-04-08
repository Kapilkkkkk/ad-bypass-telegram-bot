import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv
import requests

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Store links in memory (in production use database or file)
links = []
PAGE_SIZE = 5

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Unauthorized.")
        return

    commands = (
        "📌 Commands:\n"
        "/add <link> - Save a MEGA/Telegram link\n"
        "/links - View saved links\n"
        "/check - Check if links are working\n"
        "/delete <index> - Delete a specific link\n"
    )
    await update.message.reply_text(f"Welcome!\n{commands}")

async def add_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if context.args:
        link = context.args[0]
        links.append(link)
        await update.message.reply_text("✅ Link saved.")
    else:
        await update.message.reply_text("❗ Usage: /add <link>")

async def view_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await show_page(update, context, page=0)

async def show_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int):
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    sliced = links[start:end]
    if not sliced:
        await update.message.reply_text("📭 No links to show.")
        return
    text = "\n".join(f"{i + 1}. {link}" for i, link in enumerate(sliced, start=start))
    keyboard = [
        [
            InlineKeyboardButton("⬅️ Prev", callback_data=f"prev_{page}"),
            InlineKeyboardButton("➡️ Next", callback_data=f"next_{page}")
        ],
        [
            InlineKeyboardButton("🔍 Check Links", callback_data="check")
        ]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def check_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    broken_links = []
    for link in links:
        try:
            r = requests.head(link, timeout=10)
            if r.status_code >= 400:
                broken_links.append(link)
        except:
            broken_links.append(link)

    if broken_links:
        text = "❌ Broken Links:\n" + "\n".join(broken_links)
        keyboard = [[InlineKeyboardButton("🗑 Delete Broken", callback_data="delete_broken")]]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("✅ All links are working.")

async def delete_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if context.args:
        try:
            index = int(context.args[0]) - 1
            if 0 <= index < len(links):
                removed = links.pop(index)
                await update.message.reply_text(f"🗑 Deleted: {removed}")
            else:
                await update.message.reply_text("❗ Invalid index.")
        except:
            await update.message.reply_text("❗ Please provide a number.")
    else:
        await update.message.reply_text("❗ Usage: /delete <index>")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("prev_"):
        page = int(data.split("_")[1]) - 1
        await show_page(update, context, page=max(page, 0))
    elif data.startswith("next_"):
        page = int(data.split("_")[1]) + 1
        await show_page(update, context, page)
    elif data == "check":
        await check_links(update, context)
    elif data == "delete_broken":
        broken_links = []
        for link in links:
            try:
                r = requests.head(link, timeout=10)
                if r.status_code >= 400:
                    broken_links.append(link)
            except:
                broken_links.append(link)
        for link in broken_links:
            if link in links:
                links.remove(link)
        await query.edit_message_text("✅ Broken links deleted.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_link))
    app.add_handler(CommandHandler("links", view_links))
    app.add_handler(CommandHandler("check", check_links))
    app.add_handler(CommandHandler("delete", delete_link))
    app.add_handler(CallbackQueryHandler(callback_handler))
    print("Bot is running...")
    app.run_polling()
