from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

BOT_TOKEN = "7986033726:AAHyB1I77N68Z53-YOj1B5uhJLXEuB7XdEU"

async def test_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот жив!")

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, test_handler))
app.run_polling()