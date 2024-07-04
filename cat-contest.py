import logging
import argparse
import os
import random
import json
from telegram import InlineKeyboardButton, InputMediaPhoto, Update, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ApplicationBuilder, CommandHandler, ContextTypes
from PIL import Image

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

# Ratings storage
ratings_file = "cat_ratings.json"
if os.path.exists(ratings_file):
    with open(ratings_file, 'r') as f:
        cat_ratings = json.load(f)
else:
    cat_ratings = {}

# Elo rating constants
K = 32
DEFAULT_RATING = 1400

def get_rating(cat):
    return cat_ratings.get(cat, DEFAULT_RATING)

def update_ratings(winner, loser):
    winner_rating = get_rating(winner)
    loser_rating = get_rating(loser)

    expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
    expected_loser = 1 / (1 + 10 ** ((winner_rating - loser_rating) / 400))

    cat_ratings[winner] = winner_rating + K * (1 - expected_winner)
    cat_ratings[loser] = loser_rating + K * (0 - expected_loser)

    save_ratings()

def save_ratings():
    with open(ratings_file, 'w') as f:
        json.dump(cat_ratings, f)

# Define a function to handle the /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Hello! I am your bot.')
    await vote(update, context)

async def vote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cat_pictures_folder = "cat-pictures-final"
    cat_pictures = os.listdir(cat_pictures_folder)

    if len(cat_pictures) < 2:
        await update.message.reply_text("Not enough cat pictures to vote on.")
        return

    # Select two random cat images
    cat_image_1, cat_image_2 = random.sample(cat_pictures, 2)

    # Full path to the cat images
    cat_image_1_path = os.path.join(cat_pictures_folder, cat_image_1)
    cat_image_2_path = os.path.join(cat_pictures_folder, cat_image_2)

    
    # Prepare the media group with both cat images
    media_group = [
        InputMediaPhoto(open(cat_image_1_path, 'rb'), caption="Cat 1"),
        InputMediaPhoto(open(cat_image_2_path, 'rb'), caption="Cat 2")
    ]

    # Voting buttons
    cat_image_1_short = os.path.basename(cat_image_1_path).split('.')[0][:10]
    cat_image_2_short = os.path.basename(cat_image_2_path).split('.')[0][:10]

    keyboard = [
        [InlineKeyboardButton("Vote Cat 1", callback_data=f'vote_{cat_image_1_short}_{cat_image_2_short}_1'),
         InlineKeyboardButton("Vote Cat 2", callback_data=f'vote_{cat_image_1_short}_{cat_image_2_short}_2')],
        [InlineKeyboardButton("Show Results", callback_data='show_results')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send both cat images in one message with voting buttons
    await context.bot.send_media_group(chat_id=update.effective_chat.id, media=media_group)
    await context.bot.send_message(chat_id=update.effective_chat.id, text='Vote for your favorite cat:', reply_markup=reply_markup)

def preprocess_image(image_path, output_size=(800, 600)):
    with Image.open(image_path) as img:
        # Resize the image to the desired size, maintaining aspect ratio
        img.thumbnail(output_size, Image.Resampling.LANCZOS)
        
        # Save the processed image to a temporary path or in-memory bytes object
        temp_path = image_path + "-temp.jpg"
        img.save(temp_path)
        
        return temp_path

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    # Process the vote
    data = query.data
    if data == 'show_results':
        await show_results(update, context)
        return
    elif data == 'continue_voting':
        await vote(update, context)
        return

    _, cat1, cat2, winner_index = data.split('_')
    cat1 += ".jpg"
    cat2 += ".jpg"
    if winner_index == '1':
        update_ratings(cat1, cat2)
        winner = "Cat 1"
    else:
        update_ratings(cat2, cat1)
        winner = "Cat 2"

    await query.edit_message_text(text=f"Thanks for voting! You voted for {winner}.")
    
    # Suggest the next pair of photos for voting
    await vote(update, context)

async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not cat_ratings:
        await update.callback_query.message.reply_text("No votes yet.")
        return

    # Sort cats by rating and get the top 3
    top_3_cats = sorted(cat_ratings.items(), key=lambda item: item[1], reverse=True)[:3]
    cat_pictures_folder = "cat-pictures-final"

    places = ["1st Place", "2nd Place", "3rd Place"]
    for idx, (cat, rating) in enumerate(top_3_cats):
        cat_image_path = os.path.join(cat_pictures_folder, cat)
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=open(cat_image_path, 'rb'),
            caption=f"{places[idx]}, Rating: {rating:.2f}"
        )
    # Add "Continue voting" button
    keyboard = [[InlineKeyboardButton("Continue voting", callback_data='continue_voting')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=update.effective_chat.id, text="What would you like to do next?", reply_markup=reply_markup)

def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("vote", vote))
    application.add_handler(CallbackQueryHandler(button))

    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()