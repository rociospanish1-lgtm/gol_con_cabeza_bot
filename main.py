from telegram.ext import ApplicationBuilder, CommandHandler
import os
import asyncio

TOKEN = os.getenv("BOT_TOKEN")

async def start(update, context):
    await update.message.reply_text("🤖 Bot activo")

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
