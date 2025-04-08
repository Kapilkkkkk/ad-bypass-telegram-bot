import logging
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from playwright.async_api import async_playwright

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send me a link, and I'll try to bypass the ads for you.")

async def bypass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    await update.message.reply_text("⏳ Bypassing ads, please wait...")

    try:
        final_url = await get_final_url(url)
        await update.message.reply_text(f"✅ Final Link:\n{final_url}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def get_final_url(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, timeout=60000)
        await page.wait_for_load_state('load')
        await page.wait_for_timeout(5000)  # wait for ads/redirects
        final_url = page.url
        await browser.close()
        return final_url

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bypass))
    app.run_polling()

if __name__ == "__main__":
    main()
