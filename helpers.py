import re
import os
from PIL import Image

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
        img.thumbnail(output_size, Image.Resampling.LANCZOS)
        
        # Save the processed image to a temporary path or in-memory bytes object
        temp_path = image_path.replace(".jpg", "-resized.jpg")
        img.save(temp_path)
        
        return temp_path

def sanitize_filename(filename):
    name, ext = os.path.splitext(filename)
    sanitized_name = re.sub(r'[^a-zA-Z0-9]', '', name)
    return sanitized_name + ext