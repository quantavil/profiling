import re

_CUSTOM_USER_AGENT = None

def set_custom_user_agent(ua: str):
    global _CUSTOM_USER_AGENT
    _CUSTOM_USER_AGENT = ua

def get_headers() -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
    }
    if _CUSTOM_USER_AGENT:
        headers["User-Agent"] = _CUSTOM_USER_AGENT
    return headers

REDDIT_BASE = "https://www.reddit.com"

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Minimal English stopword set for keyword extraction.
STOPWORDS = set("""
a an the and or but if then else for to of in on at by with without from up down
out over under again further is am are was were be been being have has had do does
did doing will would shall should can could may might must this that these those i
me my we our you your he him his she her it its they them their what which who whom
whose when where why how all any both each few more most other some such no nor not
only own same so than too very just also about into through during before after above
below between only get got like one really much even still way well thing things dont
im ive youre thats gonna wanna kinda sorta yeah nah lol edit https http www com reddit
amp x200b nbsp deleted removed [deleted] [removed]
""".split())

WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z'\-]{2,}")
