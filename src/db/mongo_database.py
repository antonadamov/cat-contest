import gridfs
from pymongo import MongoClient, errors
from bson import ObjectId
import random
import logging
from db import CatVotingDatabaseInterface
from utils import calculate_new_ratings, DEFAULT_RATING

class MongoCatVotingDatabase(CatVotingDatabaseInterface):
    def __init__(self, host, port, db_name):
        try:
            self.client = MongoClient(host, port)
            self.db = self.client[db_name]
            self.cat_collection = self.db['cat_pictures']
            self.declined_collection = self.db['declined_pictures']
            self.user_collection = self.db['user_info']
            self.fs = gridfs.GridFS(self.db)
        except errors.PyMongoError as e:
            logging.error(f"MongoDB connection error: {e}")
            raise

    def add_user(self, user):
        try:
            user_info = {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "language_code": user.language_code
            }

            self.user_collection.update_one(
                {"_id": user.id},
                {
                    "$set": user_info,
                    "$setOnInsert": {"accepted_photos": [],
                                     "declined_photos": []}
                },
                upsert=True
            )
            logging.info(f"User {user_info} added to database.")
        except errors.PyMongoError as e:
            logging.error(f"Error adding user {user.id}: {e}")

    def get_cats_for_voting(self):
        try:
            cat_pictures = list(self.cat_collection.find().sort("total_votes", 1).limit(10))
            return random.sample(cat_pictures, 2)
        except errors.PyMongoError as e:
            logging.error(f"Error fetching cats for voting: {e}")
            return []
    
    def get_user_photos_with_votes(self, user_id):
        try:
            user_photos = self._get_user_photos(user_id)
            photos_details = self._get_photos_details(user_photos)
            return photos_details
        except errors.PyMongoError as e:
            logging.error(f"Error fetching photos for user ID: {user_id}: {e}")
            return []

    def _get_user_photos(self, user_id):
        try:
            user_doc = self.user_collection.find_one({"_id": user_id})
            if not user_doc or "accepted_photos" not in user_doc:
                logging.debug(f"No accepted photos found for user ID: {user_id}")
                return []
            return user_doc["accepted_photos"]
        except errors.PyMongoError as e:
            logging.error(f"Error fetching photos for user ID: {user_id}: {e}")
            return []
        
    def _get_photos_details(self, photo_ids):
        photos_details = []
        try:
            for photo_id in photo_ids:
                photo_doc = self.cat_collection.find_one({"_id": photo_id}, {"rating": 1, "wins": 1, "losses": 1})
                if photo_doc:
                    photos_details.append({
                        "photo_id": photo_id,
                        "wins": photo_doc.get("wins", 0),
                        "losses": photo_doc.get("losses", 0)
                    })
            all_photos_sorted = list(self.cat_collection.find().sort("rating", -1))
            rankings = {photo["_id"]: rank + 1 for rank, photo in enumerate(all_photos_sorted)}

            # Attach rank to each accepted photo
            for photo in photos_details:
                photo["rank"] = rankings.get(photo["photo_id"], None)
            return photos_details
        except errors.PyMongoError as e:
            logging.error(f"Error fetching details for photos: {e}")
            return photos_details


    def get_rating(self, cat_id):
        try:
            cat = self.cat_collection.find_one({"_id": ObjectId(cat_id)})
            if cat:
                return cat.get("rating", DEFAULT_RATING)
            else:
                logging.warning(f"Rating not found for cat ID: {cat_id}, returning default rating.")
                return DEFAULT_RATING
        except errors.PyMongoError as e:
            logging.error(f"Error fetching rating for cat ID: {cat_id}: {e}")
            return DEFAULT_RATING
        
    def update_ratings(self, winner_id, loser_id):
        try:
            winner = self.cat_collection.find_one({"_id": ObjectId(winner_id)})
            loser = self.cat_collection.find_one({"_id": ObjectId(loser_id)})

            if not winner or not loser:
                logging.error(f"Cannot find cat entries for winner_id: {winner_id} or loser_id: {loser_id}")
                return

            winner_rating = winner.get("rating", DEFAULT_RATING)
            loser_rating = loser.get("rating", DEFAULT_RATING)

            new_winner_rating, new_loser_rating = calculate_new_ratings(winner_rating, loser_rating)

            self.update_winner(winner_id, new_winner_rating)
            self.update_loser(loser_id, new_loser_rating)
        except errors.PyMongoError as e:
            logging.error(f"Error updating ratings for winner ID: {winner_id} and loser ID: {loser_id}: {e}")

    def update_winner(self, winner_id, new_winner_rating):
        try:
            self.cat_collection.update_one(
                {"_id": ObjectId(winner_id)},
                {"$set": {"rating": new_winner_rating}, "$inc": {"wins": 1, "total_votes": 1}}
            )
            logging.debug(f"Winner cat ID: {winner_id} updated with new rating: {new_winner_rating}")
        except errors.PyMongoError as e:
            logging.error(f"Error updating winner cat ID: {winner_id}: {e}")

    def update_loser(self, loser_id, new_loser_rating):
        try:
            self.cat_collection.update_one(
                {"_id": ObjectId(loser_id)},
                {"$set": {"rating": new_loser_rating}, "$inc": {"losses": 1, "total_votes": 1}}
            )
            logging.debug(f"Loser cat ID: {loser_id} updated with new rating: {new_loser_rating}")
        except errors.PyMongoError as e:
            logging.error(f"Error updating loser cat ID: {loser_id}: {e}")

    def insert_declined_photo(self, image_id, sanitized_filename, user_id, message):
        try:
            self.declined_collection.insert_one({
                "_id": image_id,
                "filename": sanitized_filename,
                "user_id": user_id,
                "reason": message
            })
            logging.info(f"Declined photo ID: {image_id} inserted into database.")
            self.user_collection.update_one(
                {"_id": user_id},
                {"$push": {"declined_photos": image_id}}
            )
        except errors.PyMongoError as e:
            logging.error(f"Error inserting declined photo ID: {image_id}: {e}")

    def insert_accepted_photo(self, image_id, sanitized_filename, user_id):
        try:
            self.cat_collection.insert_one({
                "_id": image_id,
                "filename": sanitized_filename,
                "user_id": user_id,
                "rating": DEFAULT_RATING,
                "wins": 0,
                "losses": 0,
                "total_votes": 0
            })
            self.user_collection.update_one(
                {"_id": user_id},
                {"$push": {"accepted_photos": image_id}}
            )
            logging.info(f"Accepted photo ID: {image_id} inserted into database.")
        except errors.PyMongoError as e:
            logging.error(f"Error inserting accepted photo ID: {image_id}: {e}")