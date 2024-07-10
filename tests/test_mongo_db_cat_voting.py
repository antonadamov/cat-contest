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

if __name__ == '__main__':
    unittest.main()