import gridfs
from pymongo import MongoClient
from bson import ObjectId
import logging
from db.database_interface import CatVotingDatabaseInterface

class MongoCatVotingDatabase(CatVotingDatabaseInterface):
    def __init__(self, host, port, db_name):
        self.client = MongoClient(host, port)
        self.db = self.client[db_name]
        self.cat_collection = self.db['cat_pictures']
        self.declined_collection = self.db['declined_pictures']
        self.user_collection = self.db['user_info']
        self.fs = gridfs.GridFS(self.db)
    
    def get_rating(self, cat_id, default_rating):
        cat = self.cat_collection.find_one({"_id": ObjectId(cat_id)})
        if cat:
            return cat.get("rating", default_rating)
        else:
            logging.warning(f"Rating not found for cat ID: {cat_id}, returning default rating.")
            return default_rating

    def update_winner(self, winner_id, new_winner_rating):
        self.cat_collection.update_one(
            {"_id": ObjectId(winner_id)},
            {"$set": {"rating": new_winner_rating}, "$inc": {"wins": 1, "total_votes": 1}}
        )

    def update_loser(self, loser_id, new_loser_rating):
        self.cat_collection.update_one(
            {"_id": ObjectId(loser_id)},
            {"$set": {"rating": new_loser_rating}, "$inc": {"losses": 1, "total_votes": 1}}
        )

    def insert_declined_photo(self, image_id, sanitized_filename, user_id, message):
        self.declined_collection.insert_one({
            "_id": image_id,
            "filename": sanitized_filename,
            "user_id": user_id,
            "reason": message
        })
        self.user_collection.update_one(
            {"_id": user_id},
            {"$push": {"declined_photos": image_id}}
        )

    def insert_accepted_photo(self, image_id, sanitized_filename, user_id, default_rating):
        self.cat_collection.insert_one({
            "_id": image_id,
            "filename": sanitized_filename,
            "user_id": user_id,
            "rating": default_rating,
            "wins": 0,
            "losses": 0,
            "total_votes": 0
        })
        self.user_collection.update_one(
            {"_id": user_id},
            {"$push": {"accepted_photos": image_id}}
        )