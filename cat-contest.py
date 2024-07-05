import logging
import argparse
import os
import random
import re
from bson import ObjectId
from telegram import InlineKeyboardButton, InputMediaPhoto, Update, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from pymongo import MongoClient
import gridfs
from PIL import Image
from typing import List
from moderation.amazon_moderation import AmazonRekognitionModerationService
from db.mongo_database import MongoCatVotingDatabase

# Set up argument parser
parser = argparse.ArgumentParser(description='Start the bot with a token and AWS parameters.')
parser.add_argument('--token', type=str, required=True, help='Bot API token')
parser.add_argument('--aws_access_key', type=str, required=True, help='AWS Access Key')
parser.add_argument('--aws_secret_key', type=str, required=True, help='AWS Secret Key')
parser.add_argument('--aws_region', type=str, required=True, help='AWS Region Name')
parser.add_argument('--db_host', type=str, required=True, help='MongoDB host')
parser.add_argument('--db_port', type=int, required=True, help='MongoDB port')
parser.add_argument('--db_name', type=str, required=True, help='MongoDB database name')
args = parser.parse_args()

# Extract values from arguments
TOKEN = args.token
AWS_ACCESS_KEY = args.aws_access_key
AWS_SECRET_KEY = args.aws_secret_key
AWS_REGION_NAME = args.aws_region
DB_HOST = args.db_host
DB_PORT = args.db_port
DB_NAME = args.db_name

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Initialize the moderation service
moderation_service = AmazonRekognitionModerationService(AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION_NAME)
db = MongoCatVotingDatabase(DB_HOST, DB_PORT, DB_NAME)


# Elo rating constants
K = 32
DEFAULT_RATING = 1400



def calculate_new_ratings(winner_rating, loser_rating):
    expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
    expected_loser = 1 / (1 + 10 ** ((winner_rating - loser_rating) / 400))
    new_winner_rating = winner_rating + K * (1 - expected_winner)
    new_loser_rating = loser_rating + K * (0 - expected_loser)
    return new_winner_rating, new_loser_rating



def update_ratings(winner_id, loser_id):
    winner = db.cat_collection.find_one({"_id": ObjectId(winner_id)})
    loser = db.cat_collection.find_one({"_id": ObjectId(loser_id)})

    if not winner or not loser:
        logging.error(f"Cannot find cat entries for winner_id: {winner_id} or loser_id: {loser_id}")
        return

    winner_rating = winner.get("rating", DEFAULT_RATING)
    loser_rating = loser.get("rating", DEFAULT_RATING)

    new_winner_rating, new_loser_rating = calculate_new_ratings(winner_rating, loser_rating)

    db.update_winner(winner_id, new_winner_rating)
    db.update_loser(loser_id, new_loser_rating)
    
def get_text(lang_code, key, **kwargs):
    texts = {
        "en": {
            "vote_cat_1": "Cat on the left",
            "vote_cat_2": "Cat on the right",
            "show_results": "Show Results",
            "continue_voting": "Continue voting",
            "vote_prompt": "Choose the cat you like the most:",
            "next_action_prompt": "What would you like to do next?",
            "thanks_voting": "Thanks for voting! You voted for {winner}.",
            "add_photo": "Add my cat photo",
            "send_photo_prompt": "Please send me the photo of your cat.",
            "photo_added": "Your photo has been added to the contest!",
            "photo_declined": "Your photo cannot be added. Reason: {message}"
        },
        "ru": {
            "vote_cat_1": "Кот слева",
            "vote_cat_2": "Кот справа",
            "show_results": "Показать результаты",
            "continue_voting": "Продолжить голосование",
            "vote_prompt": "Выбирете кота который вам больше нравится:",
            "next_action_prompt": "Что бы вы хотели сделать дальше?",
            "thanks_voting": "Спасибо за голосование! Вы проголосовали за {winner}.",
            "add_photo": "Добавить фото моего кота",
            "send_photo_prompt": "Пожалуйста, пришлите мне фото вашего кота.",
            "photo_added": "Фото вашего кота добавлено!",
            "photo_declined": "Ваше фото не может быть добавлено. Причина: {message}"
        }
    }
    text = texts.get(lang_code, texts["en"]).get(key, key)
    return text.format(**kwargs)

def preprocess_image(image_path, output_size=(800, 600)):
    with Image.open(image_path) as img:
        # Resize the image to the desired size, maintaining aspect ratio
        img.thumbnail(output_size, Image.Resampling.LANCZOS)  # Updated to use Image.Resampling.LANCZOS
        
        # Save the processed image to a temporary path or in-memory bytes object
        temp_path = image_path.replace(".jpg", "") + "-resized.jpg"
        img.save(temp_path)
        
        return temp_path

def sanitize_filename(filename):
    return re.sub(r'[^a-zA-Z0-9]', '', filename)

# Define a function to handle the /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    user_info = {
        "_id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "language_code": user.language_code,
        "photos": []
    }

    logging.info(f"New user logged in {user_info}")
    db.user_collection.update_one({"_id": user.id}, {"$set": user_info}, upsert=True)

    await update.message.reply_text('Hello! I am your bot.')
    await vote(update, context, user.language_code)

async def vote(update: Update, context: ContextTypes.DEFAULT_TYPE, lang_code: str = "en") -> None:
    cat_pictures = fetch_cat_pictures(limit=10)
    
    if len(cat_pictures) < 2:
        await send_not_enough_pictures_message(update, lang_code)
        return

    selected_cats = select_random_cats(cat_pictures, count=2)
    media_group = prepare_media_group(selected_cats)
    reply_markup = create_keyboard(selected_cats, lang_code)

    await send_media_and_message(context, update.effective_chat.id, media_group, lang_code, reply_markup)

def fetch_cat_pictures(limit: int) -> List[dict]:
    return list(db.cat_collection.find().sort("total_votes", 1).limit(limit))

async def send_not_enough_pictures_message(update: Update, lang_code: str) -> None:
    keyboard = [[InlineKeyboardButton(get_text(lang_code, "add_photo"), callback_data='add_photo')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(get_text(lang_code, "not_enough_pictures"), reply_markup=reply_markup)

def select_random_cats(cat_pictures: List[dict], count: int) -> List[dict]:
    return random.sample(cat_pictures, count)

def prepare_media_group(cats: List[dict]) -> List[InputMediaPhoto]:
    return [InputMediaPhoto(db.fs.get(cat["_id"]).read(), caption=f"Cat {i+1}") for i, cat in enumerate(cats)]

def create_keyboard(cats: List[dict], lang_code: str) -> InlineKeyboardMarkup:
    cat1, cat2 = cats
    keyboard = [
        [InlineKeyboardButton(get_text(lang_code, "vote_cat_1"), callback_data=f'vote_{cat1["_id"]}_{cat2["_id"]}_1'),
         InlineKeyboardButton(get_text(lang_code, "vote_cat_2"), callback_data=f'vote_{cat1["_id"]}_{cat2["_id"]}_2')],
        [InlineKeyboardButton(get_text(lang_code, "show_results"), callback_data='show_results')],
        [InlineKeyboardButton(get_text(lang_code, "add_photo"), callback_data='add_photo')]
    ]
    return InlineKeyboardMarkup(keyboard)

async def send_media_and_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, media_group: List[InputMediaPhoto], lang_code: str, reply_markup: InlineKeyboardMarkup) -> None:
    await context.bot.send_media_group(chat_id=chat_id, media=media_group)
    await context.bot.send_message(chat_id=chat_id, text=get_text(lang_code, "vote_prompt"), reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    # Process the vote
    data = query.data
    user_lang = query.from_user.language_code
    if data == 'show_results':
        await show_results(update, context)
        return
    elif data == 'continue_voting':
        await vote(update, context, user_lang)
        return
    elif data == 'add_photo':
        await prompt_for_photo(query, user_lang, context)
        return

    await process_vote(query, data, user_lang, update, context)

async def prompt_for_photo(query, user_lang, context) -> None:
    await query.message.reply_text(get_text(user_lang, "send_photo_prompt"))
    context.user_data["awaiting_photo"] = True

async def process_vote(query, data, user_lang, update, context) -> None:
    _, cat1_id, cat2_id, winner_index = data.split('_')
    if winner_index == '1':
        update_ratings(cat1_id, cat2_id)
        winner = get_text(user_lang, "vote_cat_1")
        logging.info(f"User {query.from_user.id} voted for cat {cat1_id}")
    else:
        update_ratings(cat2_id, cat1_id)
        winner = get_text(user_lang, "vote_cat_2")
        logging.info(f"User {query.from_user.id} voted for cat {cat2_id}")

    await query.edit_message_text(text=get_text(user_lang, "thanks_voting", winner=winner))
    await vote(update, context, user_lang)

async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    top_cats = list(db.cat_collection.find().sort("rating", -1).limit(3))

    if not top_cats:
        await update.callback_query.message.reply_text("No votes yet.")
        return

    places = ["1st Place", "2nd Place", "3rd Place"]
    for idx, cat in enumerate(top_cats):
        cat_image_path = db.fs.get(cat["_id"]).read()
        wins = cat.get("wins", 0)
        losses = cat.get("losses", 0)
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=cat_image_path,
            caption=f"{places[idx]} - Wins: {wins}, Losses: {losses}"
        )
    logging.info(f"Top cats sent to the user {update.callback_query.from_user.id}")
    user_lang = update.callback_query.from_user.language_code
    await send_next_action_prompt(update, context, user_lang)

async def send_next_action_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, user_lang) -> None:
    keyboard = [
        [InlineKeyboardButton(get_text(user_lang, "continue_voting"), callback_data='continue_voting')],
        [InlineKeyboardButton(get_text(user_lang, "add_photo"), callback_data='add_photo')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=get_text(user_lang, "next_action_prompt"), reply_markup=reply_markup)

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("awaiting_photo"):
        photo_file = await update.message.photo[-1].get_file()
        sanitized_filename = sanitize_filename(f"{update.message.from_user.id}{photo_file.file_id}.jpg")
        await photo_file.download_to_drive(sanitized_filename)
        logging.info(f"Photo downloaded for user {update.message.from_user.id}")
        processed_image_path = preprocess_image(sanitized_filename)
        user_lang = update.message.from_user.language_code
        try:
            is_appropriate, message = moderation_service.moderate_image(processed_image_path)
            if not is_appropriate:
                await insert_declined_photo_db(update, sanitized_filename, processed_image_path, message)
                await update.message.reply_text(get_text(user_lang, "photo_declined", message=message))
            else:
                await insert_accepted_photo_db(update, sanitized_filename, processed_image_path)
                await update.message.reply_text(get_text(user_lang, "photo_added"))
            await send_next_action_prompt(update, context, user_lang)
        except Exception as e:
            logging.error(f"Error handling photo: {str(e)}")
        finally:
            await cleanup_files(sanitized_filename, processed_image_path)
            context.user_data["awaiting_photo"] = False

async def cleanup_files(*files):
    for file in files:
        os.remove(file)

async def insert_declined_photo_db(update, sanitized_filename, processed_image_path, message):
    with open(processed_image_path, 'rb') as f:
        image_id = db.fs.put(f, filename=sanitized_filename, user_id=update.message.from_user.id)
    db.insert_declined_photo(image_id, sanitized_filename, update.message.from_user.id, message)

async def insert_accepted_photo_db(update, sanitized_filename, processed_image_path):
    with open(processed_image_path, 'rb') as f:
        image_id = db.fs.put(f, filename=sanitized_filename, user_id=update.message.from_user.id)
    db.insert_accepted_photo(image_id, sanitized_filename, update.message.from_user.id, DEFAULT_RATING)

def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("vote", vote))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))

    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()