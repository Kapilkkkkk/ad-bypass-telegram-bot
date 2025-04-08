import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from playwright.async_api import async_playwright

BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! Send me a link and I'll bypass the ads for you.")

async def bypass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    await update.message.reply_text("⏳ Bypassing ads, please wait...")

    try:
        final_url = await get_final_url(url)
        await update.message.reply_text(f"✅ Final Link:\n{final_url}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def get_final_url(url):
    # Using Playwright to control Chromium headless
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, timeout=60000)
        await page.wait_for_load_state('networkidle')
        # Wait a bit extra for any JS redirects to complete
        await asyncio.sleep(5)
        final_url = page.url
        await browser.close()
        return final_url

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bypass))
    app.run_polling()

if __name__ == '__main__':
    main()
