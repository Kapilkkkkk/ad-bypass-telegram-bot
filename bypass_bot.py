import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from playwright.async_api import async_playwright

# Load bot token from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send me any ad-filled or redirecting link, and I'll bypass it for you!")

async def bypass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    await update.message.reply_text("⏳ Bypassing ads, please wait...")

    try:
        final_url = await get_final_url(url)
        if "t.me/" in final_url:
            await update.message.reply_text(f"📢 This link redirects to a Telegram group/channel:\n{final_url}")
        else:
            await update.message.reply_text(f"✅ Final URL:\n{final_url}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def get_final_url(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(url, wait_until="load", timeout=60000)
        await page.wait_for_timeout(4000)  # wait for any JS redirects
        final_url = page.url
        await browser.close()
        return final_url

def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not found in environment variables.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bypass))
    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
