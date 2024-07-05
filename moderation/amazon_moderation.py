import boto3
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
        # Open the image file
        with open(image_path, 'rb') as image_file:
            image_bytes = image_file.read()

        # Check for inappropriate content
        response = self.client.detect_moderation_labels(
            Image={'Bytes': image_bytes}
        )
        
        for label in response['ModerationLabels']:
            if label['Confidence'] > 90:  # Confidence threshold
                return False,  "Image is inappropriate"

        # Check for presence of a cat
        response = self.client.detect_labels(
            Image={'Bytes': image_bytes},
            MaxLabels=10,
            MinConfidence=75
        )
        
        for label in response['Labels']:
            if label['Name'].lower() == 'cat' and label['Confidence'] > 75:
                return True, "Cat found, image is appropriate"

        return False, "No cat found"