from abc import ABC, abstractmethod

class CatVotingDatabaseInterface(ABC):

    @abstractmethod
    def get_rating(self, cat_id, default_rating):
        pass

    @abstractmethod
    def add_user(self, user):
        pass

    @abstractmethod
    def update_winner(self, winner_id, new_winner_rating):
        pass

    @abstractmethod
    def update_loser(self, loser_id, new_loser_rating):
        pass

    @abstractmethod
    def insert_declined_photo(self, image_id, sanitized_filename, user_id, message):
        pass

    @abstractmethod
    def insert_accepted_photo(self, image_id, sanitized_filename, user_id, default_rating):
        pass