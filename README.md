# Cat Contest Telegram Bot

A Telegram bot that lets users vote on cat photos, upload their own, and view rankings. 
It uses an Elo-style rating system, AWS Rekognition for content moderation, and MongoDB/GridFS for storage.

## Features

- Pairwise voting on cat photos (left vs. right)
- Users can upload their cats to compete
- Real-time leaderboard/rating
- Balances votes so each cat gets similar exposure
- Avoids repeating cats in pairs
- Moderation via Amazon Rekognition (pluggable interface — easy to add your own)
- Stores photos and data in MongoDB (pluggable storage interface)

## Requirements

- Python 3.8+
- Telegram Bot API token ([@BotFather](https://t.me/BotFather))
- MongoDB instance (local or remote)
- AWS credentials for moderation (Amazon Rekognition)

## Installation

1. Clone the repo:  
   ```bash
   git clone https://github.com/antonadamov/cat-contest.git
   cd cat-contest
   ```

2. Create and activate a virtual environment:  
   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux/macOS
   venv\Scripts\activate      # Windows
   ```

3. Install dependencies:  
   ```bash
   pip install python-telegram-bot pillow pymongo boto3 pytest
   ```

## Configuration

Set the following environment variables (or pass as CLI args):

| Variable            | Description                          |
|---------------------|--------------------------------------|
| TELEGRAM_TOKEN      | Your Telegram bot API token          |
| AWS_ACCESS_KEY      | AWS access key for Rekognition       |
| AWS_SECRET_KEY      | AWS secret key for Rekognition       |
| AWS_REGION          | AWS region (e.g. us-east-1)          |
| DB_HOST             | MongoDB host (e.g. localhost)        |
| DB_PORT             | MongoDB port (e.g. 27017)            |
| DB_NAME             | MongoDB database name (e.g. cats)    |


3. **Run the bot:**  
   Start the bot using command line arguments for all configuration parameters:

   ```bash
   python main.py \
     --token <BOT_API_TOKEN> \
     --aws_access_key <AWS_ACCESS_KEY> \
     --aws_secret_key <AWS_SECRET_KEY> \
     --aws_region <AWS_REGION_NAME> \
     --db_host <MONGODB_HOST> \
     --db_port <MONGODB_PORT> \
     --db_name <MONGODB_DB_NAME>
   ```

## Commands & Interaction

- /start – welcome message & begin voting  
- Inline buttons:  
  - “Cat on the left” / “Cat on the right” to vote  
  - “Show Results” to view top cats  
  - “Display my photos” to see your uploads  
  - “Add my cat photo” to upload  

After voting or viewing, choose “Continue voting” or “Add my cat photo.”

## Extensibility

- **Moderation:** The bot uses an interface for photo moderation. By default, Amazon Rekognition is supported. You can implement your own provider by creating a new class with the same interface.
- **Storage:** The bot stores images and metadata in MongoDB. The storage layer is abstracted and can be replaced by implementing the storage interface.

## Testing

All core logic is covered by pytest under tests/. Run:

```bash
pytest
```
