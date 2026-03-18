from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans

from core.logger import get_logger
from trend_engine.embedding_cache import load_cache, save_cache

logger = get_logger("TopicClusterer")

model = SentenceTransformer("all-MiniLM-L6-v2")

cache = load_cache()


def embed(text):

    if text in cache:

        return cache[text]

    vec = model.encode(text)

    cache[text] = vec

    save_cache(cache)

    return vec


def cluster_topics(posts, n_clusters=10):

    titles = [p["title"] for p in posts]

    embeddings = [embed(t) for t in titles]

    kmeans = KMeans(n_clusters=n_clusters)

    labels = kmeans.fit_predict(embeddings)

    for i, post in enumerate(posts):

        post["cluster"] = int(labels[i])

    logger.info(f"Created {n_clusters} topic clusters")

    return posts
