import re
from collections import Counter

from core.logger import get_logger

logger = get_logger("KeywordExtractor")


STOPWORDS = {

    "the","and","with","from","this","that","have","will",
    "your","about","into","using","how","what","when",
    "where","which","while","their","there","these"

}


def tokenize(text):

    text = text.lower()

    words = re.findall(r"\b[a-z]{3,}\b", text)

    words = [w for w in words if w not in STOPWORDS]

    return words


def extract_keywords(posts, top_k=10):

    tokens = []

    for post in posts:

        title = post.get("title","")

        words = tokenize(title)

        tokens.extend(words)

    counter = Counter(tokens)

    keywords = counter.most_common(top_k)

    result = [k for k,_ in keywords]

    logger.info(f"Extracted keywords: {result}")

    return result
