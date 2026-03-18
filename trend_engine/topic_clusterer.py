try:
    from sentence_transformers import SentenceTransformer
    from sklearn.cluster import KMeans
except Exception:  # pragma: no cover - optional dependency fallback
    SentenceTransformer = None
    KMeans = None

from core.logger import get_logger
from trend_engine.embedding_cache import load_cache, save_cache

logger = get_logger("TopicClusterer")

model = SentenceTransformer("all-MiniLM-L6-v2") if SentenceTransformer else None

cache = load_cache()


def embed(text):
    if text in cache:
        return cache[text]

    if not model:
        return [0.0]

    vec = model.encode(text)

    cache[text] = vec

    save_cache(cache)

    return vec


def cluster_topics(posts, n_clusters=10):
    if not posts:
        return posts

    if not model or not KMeans:
        # Minimal fallback when ML dependencies are unavailable.
        fallback_clusters = max(1, min(n_clusters, len(posts)))
        for idx, post in enumerate(posts):
            post["cluster"] = int(idx % fallback_clusters)
        logger.warning("ML clustering dependencies missing; used fallback clustering")
        return posts

    titles = [p["title"] for p in posts]

    embeddings = [embed(t) for t in titles]

    kmeans = KMeans(n_clusters=n_clusters)

    labels = kmeans.fit_predict(embeddings)

    for i, post in enumerate(posts):

        post["cluster"] = int(labels[i])

    logger.info(f"Created {n_clusters} topic clusters")

    return posts
