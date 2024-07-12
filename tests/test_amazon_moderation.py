import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from moderation.amazon_moderation import AmazonRekognitionModerationService

class TestAmazonRekognitionModerationService(unittest.TestCase):
    @patch('moderation.amazon_moderation.boto3.client')
    def setUp(self, mock_boto_client):
        self.mock_client = MagicMock()
        mock_boto_client.return_value = self.mock_client

        self.service = AmazonRekognitionModerationService(
            aws_access_key='fake_access_key',
            aws_secret_key='fake_secret_key',
            region_name='fake_region'
        )

    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data=b'test_image_data')
    def test_moderate_image_cat_found(self, mock_open):
        self.mock_client.detect_moderation_labels.return_value = {'ModerationLabels': []}
        self.mock_client.detect_labels.return_value = {
            'Labels': [{'Name': 'Cat', 'Confidence': 95}]
        }
        
        result, message = self.service.moderate_image('path/to/cat/image.jpg')
        self.assertTrue(result)
        self.assertEqual(message, "Cat found, image is appropriate")

    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data=b'test_image_data')
    def test_moderate_image_inappropriate_content(self, mock_open):
        self.mock_client.detect_moderation_labels.return_value = {
            'ModerationLabels': [{'Name': 'Explicit Nudity', 'Confidence': 95}]
        }
        self.mock_client.detect_labels.return_value = {'Labels': []}
        
        result, message = self.service.moderate_image('path/to/inappropriate/image.jpg')
        self.assertFalse(result)
        self.assertEqual(message, "Image is inappropriate")

    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data=b'test_image_data')
    def test_moderate_image_no_cat_found(self, mock_open):
        self.mock_client.detect_moderation_labels.return_value = {'ModerationLabels': []}
        self.mock_client.detect_labels.return_value = {'Labels': []}
        
        result, message = self.service.moderate_image('path/to/no_cat/image.jpg')
        self.assertFalse(result)
        self.assertEqual(message, "No cat found")

    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data=b'test_image_data')
    def test_moderate_image_io_error(self, mock_open):
        mock_open.side_effect = IOError("Unable to open file")
        
        result, message = self.service.moderate_image('path/to/error/image.jpg')
        self.assertFalse(result)
        self.assertIn("Failed to read image", message)

if __name__ == '__main__':
    unittest.main()