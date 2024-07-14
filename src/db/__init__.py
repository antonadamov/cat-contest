from .database_interface import CatVotingDatabaseInterface
from .mongo_database import MongoCatVotingDatabase

__all__ = ['CatVotingDatabaseInterface', 'MongoCatVotingDatabase']