import unittest
from unittest.mock import patch, MagicMock
from pymongo import errors
import gridfs
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from db.mongo_database import MongoCatVotingDatabase

class TestAddCatMethod(unittest.TestCase):
    @patch('db.mongo_database.MongoClient')
    @patch('db.mongo_database.gridfs.GridFS')
    def setUp(self, mock_gridfs, mock_mongo_client):
        self.mock_client = mock_mongo_client.return_value
        self.mock_db = self.mock_client.__getitem__.return_value
        self.mock_user_collection = self.mock_db['user_info']
        self.mock_cat_collection = self.mock_db['cat_pictures']
        self.mock_fs = mock_gridfs.return_value
        self.database = MongoCatVotingDatabase('localhost', 27017, 'test_db')

    def test_add_user_success(self):
        # Create a mock user object
        mock_user = MagicMock()
        mock_user.id = 'test_user_id'
        mock_user.first_name = 'John'
        mock_user.last_name = 'Doe'
        mock_user.username = 'johndoe'
        mock_user.language_code = 'en'

        # Call the method
        self.database.add_user(mock_user)

        # Check that the update_one method was called with the correct parameters
        self.mock_user_collection.update_one.assert_called_once_with(
            {"_id": mock_user.id},
            {
                "$set": {
                    "first_name": mock_user.first_name,
                    "last_name": mock_user.last_name,
                    "username": mock_user.username,
                    "language_code": mock_user.language_code
                },
                "$setOnInsert": {"accepted_photos": [], "declined_photos": []}
            },
            upsert=True
        )

    @patch('db.mongo_database.logging.error')
    def test_add_user_failure(self, mock_logging_error):
        # Simulate an exception being raised when calling update_one
        self.mock_user_collection.update_one.side_effect = errors.PyMongoError('Error')

        # Create a mock user object
        mock_user = MagicMock()
        mock_user.id = 'test_user_id'
        mock_user.first_name = 'John'
        mock_user.last_name = 'Doe'
        mock_user.username = 'johndoe'
        mock_user.language_code = 'en'

        # Call the method
        self.database.add_user(mock_user)

        # Check that the error was logged
        mock_logging_error.assert_called_once_with(f"Error adding user {mock_user.id}: Error")

    @patch('random.sample')
    def test_get_cats_for_voting_success(self, mock_random_sample):
        # Create mock cat documents
        mock_cats = [
            {"_id": "cat1", "total_votes": 5},
            {"_id": "cat2", "total_votes": 10},
            {"_id": "cat3", "total_votes": 15},
            {"_id": "cat4", "total_votes": 20},
            {"_id": "cat5", "total_votes": 25},
            {"_id": "cat6", "total_votes": 30},
            {"_id": "cat7", "total_votes": 35},
            {"_id": "cat8", "total_votes": 40},
            {"_id": "cat9", "total_votes": 45},
            {"_id": "cat10", "total_votes": 50},
        ]

        # Mock the find and sort operations
        self.mock_cat_collection.find.return_value.sort.return_value.limit.return_value = mock_cats

        # Mock the random.sample method
        mock_random_sample.return_value = mock_cats[:2]

        # Call the method
        result = self.database.get_cats_for_voting()

        # Check that find and sort were called correctly
        self.mock_cat_collection.find.assert_called_once()
        self.mock_cat_collection.find.return_value.sort.assert_called_once_with("total_votes", 1)
        self.mock_cat_collection.find.return_value.sort.return_value.limit.assert_called_once_with(10)

        # Check that random.sample was called correctly
        mock_random_sample.assert_called_once_with(mock_cats, 2)

        # Check the result
        self.assertEqual(result, mock_cats[:2])

    @patch('db.mongo_database.logging.error')
    def test_get_cats_for_voting_failure(self, mock_logging_error):
        # Simulate an exception being raised when calling find
        self.mock_cat_collection.find.side_effect = errors.PyMongoError('Error')

        # Call the method
        result = self.database.get_cats_for_voting()

        # Check that the error was logged
        mock_logging_error.assert_called_once_with("Error fetching cats for voting: Error")

        # Check the result
        self.assertEqual(result, [])

if __name__ == '__main__':
    unittest.main()