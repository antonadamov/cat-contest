import json
import os

ratings_file = "cat_ratings.json"

if os.path.exists(ratings_file):
    with open(ratings_file, 'r') as f:
        cat_ratings = json.load(f)
else:
    cat_ratings = {}

K = 32
DEFAULT_RATING = 1400

def get_rating(cat):
    return cat_ratings.get(cat, DEFAULT_RATING)

def update_ratings(winner, loser):
    winner_rating = get_rating(winner)
    loser_rating = get_rating(loser)

    expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
    expected_loser = 1 / (1 + 10 ** ((winner_rating - loser_rating) / 400))

    cat_ratings[winner] = winner_rating + K * (1 - expected_winner)
    cat_ratings[loser] = loser_rating + K * (0 - expected_loser)

    save_ratings()

def save_ratings():
    with open(ratings_file, 'w') as f:
        json.dump(cat_ratings, f)