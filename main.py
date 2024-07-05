import logging
import argparse
from cat_contest import CatContest
from telegram.ext import CallbackQueryHandler, ApplicationBuilder, CommandHandler, MessageHandler, filters


# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def main():
    # Argument parsing
    parser = argparse.ArgumentParser(description='Start the bot with a token and AWS parameters.')
    parser.add_argument('--token', type=str, required=True, help='Bot API token')
    parser.add_argument('--aws_access_key', type=str, required=True, help='AWS Access Key')
    parser.add_argument('--aws_secret_key', type=str, required=True, help='AWS Secret Key')
    parser.add_argument('--aws_region', type=str, required=True, help='AWS Region Name')
    parser.add_argument('--db_host', type=str, required=True, help='MongoDB host')
    parser.add_argument('--db_port', type=int, required=True, help='MongoDB port')
    parser.add_argument('--db_name', type=str, required=True, help='MongoDB database name')
    args = parser.parse_args()

    cat_contest = CatContest(args.token, args.aws_access_key, args.aws_secret_key, args.aws_region, args.db_host, args.db_port, args.db_name)
    application = ApplicationBuilder().token(cat_contest.token).build()

    application.add_handler(CommandHandler("start", cat_contest.start))
    application.add_handler(CommandHandler("vote", cat_contest.vote))
    application.add_handler(CallbackQueryHandler(cat_contest.button))
    application.add_handler(MessageHandler(filters.PHOTO, cat_contest.photo_handler))

    application.run_polling()

if __name__ == '__main__':
    main()