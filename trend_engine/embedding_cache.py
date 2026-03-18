import pickle
import os

CACHE_FILE = "data/processed/embedding_cache.pkl"


def load_cache():

    if not os.path.exists(CACHE_FILE):

        return {}

    with open(CACHE_FILE, "rb") as f:

        return pickle.load(f)


def save_cache(cache):

    with open(CACHE_FILE, "wb") as f:

        pickle.dump(cache, f)
