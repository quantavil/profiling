from .base import fetch_listing_archive

def fetch_listing_arctic_shift(username, kind, limit=1000):
    return fetch_listing_archive(username, kind, limit, "arctic")
