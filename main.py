import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler.ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context): 
    await update.message.reply_text(
        "🤖 Bot activo.\n\nPróximamente: análisis y alertas de fútbol ⚽"
    )

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

if __name__ == "__main__":
    main()
