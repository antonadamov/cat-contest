# Description: Rating class for calculating new ratings based on the Elo rating system

DEFAULT_RATING = 1400

def calculate_new_ratings(winner_rating, loser_rating):
    K = 32
    expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
    expected_loser = 1 / (1 + 10 ** ((winner_rating - loser_rating) / 400))
    new_winner_rating = winner_rating + K * (1 - expected_winner)
    new_loser_rating = loser_rating + K * (0 - expected_loser)
    return new_winner_rating, new_loser_rating