import boto3
import logging
from botocore.exceptions import BotoCoreError, ClientError
from moderation.moderation_interface import ImageModerationService

class AmazonRekognitionModerationService(ImageModerationService):
    def __init__(self, aws_access_key, aws_secret_key, region_name):
        self.client = boto3.client(
            'rekognition',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=region_name
        )

    def moderate_image(self, image_path):
        try:
            with open(image_path, 'rb') as image_file:
                image_bytes = image_file.read()

            if self._contains_inappropriate_content(image_bytes):
                return False, "Image is inappropriate"
            if self._contains_cat(image_bytes):
                return True, "Cat found, image is appropriate"
            return False, "No cat found"
        except IOError as e:
            logging.error(f"Failed to read image: {e}")
            return False, f"Failed to read image: {e}"
        except (BotoCoreError, ClientError) as e:
            logging.error(f"Failed to moderate image: {e}")
            return False, f"Failed to moderate image: {e}"
    
    def _contains_inappropriate_content(self, image_bytes):
        try:
            response = self.client.detect_moderation_labels(
                Image={'Bytes': image_bytes}
            )
            for label in response['ModerationLabels']:
                if label['Confidence'] > 90: 
                    return True
            return False
        except (BotoCoreError, ClientError) as e:
            logging.error(f"Failed to detect moderation labels: {e}")
            return False

    def _contains_cat(self, image_bytes):
        try:
            response = self.client.detect_labels(
                Image={'Bytes': image_bytes},
                MaxLabels=10,
                MinConfidence=75
            )
            for label in response['Labels']:
                if label['Name'].lower() == 'cat' and label['Confidence'] > 75:
                    return True
            return False
        except (BotoCoreError, ClientError) as e:
            logging.error(f"Failed to detect labels: {e}")
            return False