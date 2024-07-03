import logging
import argparse
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Set up argument parser
parser = argparse.ArgumentParser(description='Start the bot with a token.')
parser.add_argument('--token', type=str, required=True, help='Bot API token')
args = parser.parse_args()

TOKEN = args.token


# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Define a function to handle the /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Hello! I am your bot.')


def main():
    # Create the Application and pass it your bot's token
    application = ApplicationBuilder().token(TOKEN).build()

    # Register the /start command handler
    application.add_handler(CommandHandler("start", start))

    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()