import logging
import os
import random
import re
from bson import ObjectId
from telegram import InlineKeyboardButton, InputMediaPhoto, Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from PIL import Image
from typing import List
from moderation.amazon_moderation import AmazonRekognitionModerationService
from db.mongo_database import MongoCatVotingDatabase



class CatContest:
# Elo rating constants
    DEFAULT_RATING = 1400

    def __init__(self, token, aws_access_key, aws_secret_key, aws_region, db_host, db_port, db_name):
        self.token = token
        self.moderation_service = AmazonRekognitionModerationService(aws_access_key, aws_secret_key, aws_region)
        self.db = MongoCatVotingDatabase(db_host, db_port, db_name)

    def calculate_new_ratings(self, winner_rating, loser_rating):
        K = 32
        expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
        expected_loser = 1 / (1 + 10 ** ((winner_rating - loser_rating) / 400))
        new_winner_rating = winner_rating + K * (1 - expected_winner)
        new_loser_rating = loser_rating + K * (0 - expected_loser)
        return new_winner_rating, new_loser_rating

    def update_ratings(self, winner_id, loser_id):
        
        winner = self.db.cat_collection.find_one({"_id": ObjectId(winner_id)})
        loser = self.db.cat_collection.find_one({"_id": ObjectId(loser_id)})

        if not winner or not loser:
            logging.error(f"Cannot find cat entries for winner_id: {winner_id} or loser_id: {loser_id}")
            return

        winner_rating = winner.get("rating", self.DEFAULT_RATING)
        loser_rating = loser.get("rating", self.DEFAULT_RATING)

        new_winner_rating, new_loser_rating = self.calculate_new_ratings(winner_rating, loser_rating)

        self.db.update_winner(winner_id, new_winner_rating)
        self.db.update_loser(loser_id, new_loser_rating)
        
    def get_text(self, lang_code, key, **kwargs):
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

    def preprocess_image(self, image_path, output_size=(800, 600)):
        with Image.open(image_path) as img:
            # Resize the image to the desired size, maintaining aspect ratio
            img.thumbnail(output_size, Image.Resampling.LANCZOS)  # Updated to use Image.Resampling.LANCZOS
            
            # Save the processed image to a temporary path or in-memory bytes object
            temp_path = image_path.replace(".jpg", "") + "-resized.jpg"
            img.save(temp_path)
            
            return temp_path

    def sanitize_filename(self, filename):
        return re.sub(r'[^a-zA-Z0-9]', '', filename)

    # Define a function to handle the /start command
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.message.from_user
        logging.info(f"New user logged in {user.id}")

        self.db.add_user(user)

        await update.message.reply_text('Hello! I am your bot.')
        await self.vote(update, context, user.language_code)

    async def vote(self, update: Update, context: ContextTypes.DEFAULT_TYPE, lang_code: str = "en") -> None:
        cat_pictures = list(self.db.cat_collection.find().sort("total_votes", 1).limit(10))
        if len(cat_pictures) < 2:
            await self.send_not_enough_pictures_message(self, update, lang_code)
            return
        selected_cats = random.sample(cat_pictures, 2)
        media_group = [InputMediaPhoto(self.db.fs.get(cat["_id"]).read(), caption=f"Cat {i+1}") for i, cat in enumerate(selected_cats)]
        reply_markup = self.create_keyboard(selected_cats, lang_code)
        await self.send_media_and_message(context, update.effective_chat.id, media_group, lang_code, reply_markup)

    async def send_not_enough_pictures_message(self, update: Update, lang_code: str) -> None:
        keyboard = [[InlineKeyboardButton(self.get_text(lang_code, "add_photo"), callback_data='add_photo')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(self.get_text(lang_code, "not_enough_pictures"), reply_markup=reply_markup)

    def create_keyboard(self, cats: List[dict], lang_code: str) -> InlineKeyboardMarkup:
        cat1, cat2 = cats
        keyboard = [
            [InlineKeyboardButton(self.get_text(lang_code, "vote_cat_1"), callback_data=f'vote_{cat1["_id"]}_{cat2["_id"]}_1'),
            InlineKeyboardButton(self.get_text(lang_code, "vote_cat_2"), callback_data=f'vote_{cat1["_id"]}_{cat2["_id"]}_2')],
            [InlineKeyboardButton(self.get_text(lang_code, "show_results"), callback_data='show_results')],
            [InlineKeyboardButton(self.get_text(lang_code, "add_photo"), callback_data='add_photo')]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def send_media_and_message(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, media_group: List[InputMediaPhoto], lang_code: str, reply_markup: InlineKeyboardMarkup) -> None:
        await context.bot.send_media_group(chat_id=chat_id, media=media_group)
        await context.bot.send_message(chat_id=chat_id, text=self.get_text(lang_code, "vote_prompt"), reply_markup=reply_markup)

    async def button(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        # Process the vote
        data = query.data
        user_lang = query.from_user.language_code
        if data == 'show_results':
            await self.show_results(update, context)
            return
        elif data == 'continue_voting':
            await self.vote(update, context, user_lang)
            return
        elif data == 'add_photo':
            await self.prompt_for_photo(query, user_lang, context)
            return

        await self.process_vote(query, data, user_lang, update, context)

    async def prompt_for_photo(self, query, user_lang, context) -> None:
        await query.message.reply_text(self.get_text(user_lang, "send_photo_prompt"))
        context.user_data["awaiting_photo"] = True

    async def process_vote(self, query, data, user_lang, update, context) -> None:
        _, cat1_id, cat2_id, winner_index = data.split('_')
        if winner_index == '1':
            self.update_ratings(cat1_id, cat2_id)
            winner = self.get_text(user_lang, "vote_cat_1")
            logging.info(f"User {query.from_user.id} voted for cat {cat1_id}")
        else:
            self.update_ratings(cat2_id, cat1_id)
            winner = self.get_text(user_lang, "vote_cat_2")
            logging.info(f"User {query.from_user.id} voted for cat {cat2_id}")

        await query.edit_message_text(text=self.get_text(user_lang, "thanks_voting", winner=winner))
        await self.vote(update, context, user_lang)

    async def show_results(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        top_cats = list(self.db.cat_collection.find().sort("rating", -1).limit(3))

        if not top_cats:
            await update.callback_query.message.reply_text("No votes yet.")
            return

        places = ["1st Place", "2nd Place", "3rd Place"]
        for idx, cat in enumerate(top_cats):
            cat_image_path = self.db.fs.get(cat["_id"]).read()
            wins = cat.get("wins", 0)
            losses = cat.get("losses", 0)
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=cat_image_path,
                caption=f"{places[idx]} - Wins: {wins}, Losses: {losses}"
            )
        logging.info(f"Top cats sent to the user {update.callback_query.from_user.id}")
        user_lang = update.callback_query.from_user.language_code
        await self.send_next_action_prompt(update, context, user_lang)

    async def send_next_action_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_lang) -> None:
        keyboard = [
            [InlineKeyboardButton(self.get_text(user_lang, "continue_voting"), callback_data='continue_voting')],
            [InlineKeyboardButton(self.get_text(user_lang, "add_photo"), callback_data='add_photo')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=self.get_text(user_lang, "next_action_prompt"), reply_markup=reply_markup)

    async def photo_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if context.user_data.get("awaiting_photo"):
            sanitized_filename = processed_image_path = ""
            try:
                photo_file = await update.message.photo[-1].get_file()
                user_lang = update.message.from_user.language_code
                
                sanitized_filename, processed_image_path = await self.prepare_photo(photo_file, update.message.from_user.id)
                is_appropriate, message = self.moderation_service.moderate_image(processed_image_path)
                
                if not is_appropriate:
                    await self.insert_declined_photo_db(update, sanitized_filename, processed_image_path, message)
                    await update.message.reply_text(self.get_text(user_lang, "photo_declined", message=message))
                else:
                    await self.insert_accepted_photo_db(update, sanitized_filename, processed_image_path)
                    await update.message.reply_text(self.get_text(user_lang, "photo_added"))
                await self.send_next_action_prompt(update, context, user_lang)
            except Exception as e:
                logging.exception(f"Error handling photo: {str(e)}")
            finally:
                await self.cleanup_files(sanitized_filename, processed_image_path)
                context.user_data["awaiting_photo"] = False


    async def prepare_photo(self, photo_file, user_id):
        sanitized_filename = self.sanitize_filename(f"{user_id}{photo_file.file_id}.jpg")
        await photo_file.download_to_drive(sanitized_filename)
        logging.info(f"Photo downloaded for user {user_id}")
        processed_image_path = self.preprocess_image(sanitized_filename)
        return sanitized_filename, processed_image_path

    async def cleanup_files(self, *files):
        try:
            for file in files:
                os.remove(file)
        except Exception as e:
            logging.error(f"Error cleaning up files: {str(e)}")

    async def insert_declined_photo_db(self, update, sanitized_filename, processed_image_path, message):
        with open(processed_image_path, 'rb') as f:
            image_id = self.db.fs.put(f, filename=sanitized_filename, user_id=update.message.from_user.id)
        self.db.insert_declined_photo(image_id, sanitized_filename, update.message.from_user.id, message)

    async def insert_accepted_photo_db(self, update, sanitized_filename, processed_image_path):
        with open(processed_image_path, 'rb') as f:
            image_id = self.db.fs.put(f, filename=sanitized_filename, user_id=update.message.from_user.id)
        self.db.insert_accepted_photo(image_id, sanitized_filename, update.message.from_user.id, self.DEFAULT_RATING)