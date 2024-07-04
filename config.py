import argparse
import logging

def get_config():
    parser = argparse.ArgumentParser(description='Start the bot with a token.')
    parser.add_argument('--token', type=str, required=True, help='Bot API token')
    args = parser.parse_args()
    return args.token

def setup_logging():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )