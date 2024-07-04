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
from moderation.amazon_moderation import AmazonRekognitionModerationService

# Set up argument parser
parser = argparse.ArgumentParser(description='Start the bot with a token and AWS parameters.')
parser.add_argument('--token', type=str, required=True, help='Bot API token')
parser.add_argument('--aws_access_key', type=str, required=True, help='AWS Access Key')
parser.add_argument('--aws_secret_key', type=str, required=True, help='AWS Secret Key')
parser.add_argument('--aws_region', type=str, required=True, help='AWS Region Name')
args = parser.parse_args()

# Extract values from arguments
TOKEN = args.token
AWS_ACCESS_KEY = args.aws_access_key
AWS_SECRET_KEY = args.aws_secret_key
AWS_REGION_NAME = args.aws_region

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Initialize the moderation service
moderation_service = AmazonRekognitionModerationService(AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION_NAME)


# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['cat_voting']
cat_collection = db['cat_pictures']
fs = gridfs.GridFS(db)

# Elo rating constants
K = 32
DEFAULT_RATING = 1400

def get_rating(cat_id):
    cat = cat_collection.find_one({"_id": ObjectId(cat_id)})
    if cat:
        return cat.get("rating", DEFAULT_RATING)
    else:
        logging.warning(f"Rating not found for cat ID: {cat_id}, returning default rating.")
        return DEFAULT_RATING

def update_ratings(winner_id, loser_id):
    winner = cat_collection.find_one({"_id": ObjectId(winner_id)})
    loser = cat_collection.find_one({"_id": ObjectId(loser_id)})

    if not winner or not loser:
        logging.error(f"Cannot find cat entries for winner_id: {winner_id} or loser_id: {loser_id}")
        return

    winner_rating = winner.get("rating", DEFAULT_RATING)
    loser_rating = loser.get("rating", DEFAULT_RATING)

    expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
    expected_loser = 1 / (1 + 10 ** ((winner_rating - loser_rating) / 400))

    new_winner_rating = winner_rating + K * (1 - expected_winner)
    new_loser_rating = loser_rating + K * (0 - expected_loser)

    cat_collection.update_one(
        {"_id": ObjectId(winner_id)},
        {"$set": {"rating": new_winner_rating}, "$inc": {"wins": 1, "total_votes": 1}}
    )

    cat_collection.update_one(
        {"_id": ObjectId(loser_id)},
        {"$set": {"rating": new_loser_rating}, "$inc": {"losses": 1, "total_votes": 1}}
    )
    
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
            "send_photo_prompt": "Please send me the photo of your cat."
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
            "send_photo_prompt": "Пожалуйста, пришлите мне фото вашего кота."
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
    user_info = f"User ID: {user.id}\nFirst Name: {user.first_name}\n"
    if user.last_name:
        user_info += f"Last Name: {user.last_name}\n"
    if user.username:
        user_info += f"Username: @{user.username}\n"
    if user.language_code:
        user_info += f"Language Code: {user.language_code}\n"

    logging.info(user_info)

    await update.message.reply_text('Hello! I am your bot.')
    await vote(update, context, user.language_code)

async def vote(update: Update, context: ContextTypes.DEFAULT_TYPE, lang_code: str = "en") -> None:
    # Get images with the least number of votes (wins + losses)
    cat_pictures = list(cat_collection.find().sort("total_votes", 1).limit(10))

    if len(cat_pictures) < 2:
        keyboard = [[InlineKeyboardButton(get_text(lang_code, "add_photo"), callback_data='add_photo')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Not enough cat pictures to vote on.", reply_markup=reply_markup)
        return

    # If there are more than two pictures with the minimum number of votes, randomly select two from them
    cat_pictures = random.sample(cat_pictures, 2)

    cat1, cat2 = cat_pictures

    cat_image_1_path = fs.get(cat1["_id"]).read()
    cat_image_2_path = fs.get(cat2["_id"]).read()

    media_group = [
        InputMediaPhoto(cat_image_1_path, caption="Cat 1"),
        InputMediaPhoto(cat_image_2_path, caption="Cat 2")
    ]

    keyboard = [
        [InlineKeyboardButton(get_text(lang_code, "vote_cat_1"), callback_data=f'vote_{cat1["_id"]}_{cat2["_id"]}_1'),
         InlineKeyboardButton(get_text(lang_code, "vote_cat_2"), callback_data=f'vote_{cat1["_id"]}_{cat2["_id"]}_2')],
        [InlineKeyboardButton(get_text(lang_code, "show_results"), callback_data='show_results')],
        [InlineKeyboardButton(get_text(lang_code, "add_photo"), callback_data='add_photo')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_media_group(chat_id=update.effective_chat.id, media=media_group)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=get_text(lang_code, "vote_prompt"), reply_markup=reply_markup)

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
        await query.message.reply_text(get_text(user_lang, "send_photo_prompt"))
        context.user_data["awaiting_photo"] = True
        return

    _, cat1, cat2, winner_index = data.split('_')
    if winner_index == '1':
        update_ratings(cat1, cat2)
        winner = get_text(user_lang, "vote_cat_1")
    else:
        update_ratings(cat2, cat1)
        winner = get_text(user_lang, "vote_cat_2")

    await query.edit_message_text(text=get_text(user_lang, "thanks_voting", winner=winner))
    
    # Suggest the next pair of photos for voting
    await vote(update, context, user_lang)

async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    top_cats = list(cat_collection.find().sort("rating", -1).limit(3))

    if not top_cats:
        await update.callback_query.message.reply_text("No votes yet.")
        return

    places = ["1st Place", "2nd Place", "3rd Place"]
    for idx, cat in enumerate(top_cats):
        cat_image_path = fs.get(cat["_id"]).read()
        wins = cat.get("wins", 0)
        losses = cat.get("losses", 0)
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=cat_image_path,
            caption=f"{places[idx]} - Wins: {wins}, Losses: {losses}"
        )

    user_lang = update.callback_query.from_user.language_code
    keyboard =  [
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

        # Preprocess the image
        processed_image_path = preprocess_image(sanitized_filename)

        # Moderate the image
        is_appropriate = moderation_service.moderate_image(processed_image_path)
        if not is_appropriate:
            await update.message.reply_text("Your photo was found to be inappropriate or does not contain a cat and cannot be added.")
            os.remove(sanitized_filename)
            os.remove(processed_image_path)
            return
        
        with open(processed_image_path, 'rb') as f:
            image_id = fs.put(f, filename=sanitized_filename, user_id=update.message.from_user.id)

        # Add entry to MongoDB
        cat_collection.insert_one({
            "_id": image_id,
            "filename": sanitized_filename,
            "user_id": update.message.from_user.id,
            "rating": DEFAULT_RATING,
            "wins": 0,
            "losses": 0,
            "total_votes": 0
        })

        # Remove the original downloaded image
        os.remove(sanitized_filename)
        os.remove(processed_image_path)

        context.user_data["awaiting_photo"] = False
        await update.message.reply_text("Your photo has been added to the contest!")
        await vote(update, context, update.message.from_user.language_code)

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