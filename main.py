import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Función que responde a /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 ¡Hola! Soy el bot Gol con Cabeza ⚽🧠\n\n"
        "Estoy funcionando correctamente 🚀"
    )

def main():
    # Leer el token desde la variable de entorno
    TOKEN = os.getenv("BOT_TOKEN")

    if not TOKEN:
        raise ValueError("❌ BOT_TOKEN no está definido en las variables de entorno")

    # Crear la aplicación
    app = ApplicationBuilder().token(TOKEN).build()

    # Registrar el comando /start
    app.add_handler(CommandHandler("start", start))

    # Comandos /asmr y /asmr_ayuda (creador de vídeos ASMR)
    try:
        import asmr_bot
        asmr_bot.registrar(app)
    except ImportError as e:
        print(f"⚠️ Módulo ASMR desactivado: {e}")

    print("🤖 Bot iniciado correctamente")
    app.run_polling()

if __name__ == "__main__":
    main()
