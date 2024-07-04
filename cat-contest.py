import logging
import os
import random
from telegram import InlineKeyboardButton, InputMediaPhoto, Update, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from config import get_config, setup_logging
from helpers import get_text, preprocess_image, sanitize_filename
from ratings import cat_ratings, get_rating, update_ratings, save_ratings

TOKEN = get_config()

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
    cat_pictures_folder = "cat-pictures"
    cat_pictures = os.listdir(cat_pictures_folder)

    if len(cat_pictures) < 2:
        await update.message.reply_text("Not enough cat pictures to vote on.")
        return

    cat_image_1, cat_image_2 = random.sample(cat_pictures, 2)
    cat_image_1_path = os.path.join(cat_pictures_folder, cat_image_1)
    cat_image_2_path = os.path.join(cat_pictures_folder, cat_image_2)

    media_group = [
        InputMediaPhoto(open(cat_image_1_path, 'rb'), caption="Cat 1"),
        InputMediaPhoto(open(cat_image_2_path, 'rb'), caption="Cat 2")
    ]

    cat_image_1_short = os.path.basename(cat_image_1_path).split('.')[0][:10]
    cat_image_2_short = os.path.basename(cat_image_2_path).split('.')[0][:10]

    keyboard = [
        [InlineKeyboardButton(get_text(lang_code, "vote_cat_1"), callback_data=f'vote_{cat_image_1_short}_{cat_image_2_short}_1'),
         InlineKeyboardButton(get_text(lang_code, "vote_cat_2"), callback_data=f'vote_{cat_image_1_short}_{cat_image_2_short}_2')],
        [InlineKeyboardButton(get_text(lang_code, "show_results"), callback_data='show_results')],
        [InlineKeyboardButton(get_text(lang_code, "add_photo"), callback_data='add_photo')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_media_group(chat_id=update.effective_chat.id, media=media_group)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=get_text(lang_code, "vote_prompt"), reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

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
    cat1 += ".jpg"
    cat2 += ".jpg"
    if winner_index == '1':
        update_ratings(cat1, cat2)
        winner = get_text(user_lang, "vote_cat_1")
    else:
        update_ratings(cat2, cat1)
        winner = get_text(user_lang, "vote_cat_2")

    await query.edit_message_text(text=get_text(user_lang, "thanks_voting", winner=winner))
    await vote(update, context, user_lang)

async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not cat_ratings:
        await update.callback_query.message.reply_text("No votes yet.")
        return

    top_3_cats = sorted(cat_ratings.items(), key=lambda item: item[1], reverse=True)[:3]
    cat_pictures_folder = "cat-pictures"

    places = ["1st Place", "2nd Place", "3rd Place"]
    for idx, (cat, rating) in enumerate(top_3_cats):
        cat_image_path = os.path.join(cat_pictures_folder, cat)
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=open(cat_image_path, 'rb'),
            caption=f"{places[idx]}"
        )

    lang_code = update.callback_query.from_user.language_code
    keyboard = [
        [InlineKeyboardButton(get_text(lang_code, "show_results"), callback_data='show_results')],
        [InlineKeyboardButton(get_text(lang_code, "add_photo"), callback_data='add_photo')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=get_text(lang_code, "next_action_prompt"), reply_markup=reply_markup)

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("awaiting_photo"):
        photo_file = await update.message.photo[-1].get_file()
        sanitized_filename = sanitize_filename(f"{update.message.from_user.id}{photo_file.file_id}.jpg")
        await photo_file.download_to_drive(sanitized_filename)

        processed_image_path = preprocess_image(sanitized_filename)
        new_filename = os.path.join("cat-pictures", os.path.basename(processed_image_path))
        os.rename(processed_image_path, new_filename)
        os.remove(sanitized_filename)

        context.user_data["awaiting_photo"] = False
        await update.message.reply_text("Your photo has been added to the contest!")
        await vote(update, context, update.message.from_user.language_code)

def main():
    setup_logging()
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("vote", vote))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))

    application.run_polling()

if __name__ == '__main__':
    main()