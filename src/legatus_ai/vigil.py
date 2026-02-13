import logging
from typing import List, Dict, Any, Optional

from sentence_transformers import SentenceTransformer, util

from .config import AppConfig
from .constants import DEFAULT_EMBEDDING_MODEL, DEFAULT_SIMILARITY_THRESHOLD

# A simple type alias for clarity
Article = Dict[str, Any]

_model_cache: Optional[SentenceTransformer] = None


def _get_embedding_model(model_name: str) -> SentenceTransformer:
    """
    Loads and caches the SentenceTransformer model.

    Args:
        model_name: The name of the model to load from Hugging Face.

    Returns:
        An instance of the SentenceTransformer model.
    """
    global _model_cache
    if _model_cache is None or _model_cache.model_name_or_path != model_name:
        logging.info(f"Loading embedding model '{model_name}'... (This may take a moment on first run)")
        try:
            _model_cache = SentenceTransformer(model_name)
        except Exception as e:
            logging.error(f"Failed to load SentenceTransformer model '{model_name}'. Error: {e}")
            raise
    return _model_cache


def filter_articles(articles: List[Article], context: Dict[str, Any], config: AppConfig) -> List[Article]:
    """
    Filters a list of articles using semantic similarity between their embeddings
    and the project's context embedding.

    Args:
        articles: A list of article dictionaries gathered by the Scout module.
        context: The project context dictionary, which must contain an 'embedding'.
        config: The validated application configuration.

    Returns:
        A deduplicated list of articles that are semantically relevant.
    """
    logging.info("=" * 80)
    logging.info("Vigilum Module: Performing semantic pre-filtering...")
    logging.info("=" * 80)

    if not articles:
        logging.info("No articles to filter.")
        return []

    project_embedding = context.get('embedding')
    if project_embedding is None:
        logging.error("Project context embedding not found. Skipping filtering.")
        return articles

    model_name = config.ai_settings.embedding_model
    similarity_threshold = config.analysis_rules.vigil_similarity_threshold

    try:
        model = _get_embedding_model(model_name)
    except Exception:
        return articles

    article_texts = [f"{article.get('title', '')}. {article.get('summary', '')}" for article in articles]
    logging.info(f"Generating embeddings for {len(article_texts)} articles using '{model_name}'...")

    # Generate embeddings in batches for efficiency, especially with many articles
    article_embeddings = model.encode(article_texts, convert_to_tensor=True, show_progress_bar=False)
    logging.info("Embeddings generated successfully.")

    # Compute cosine similarity between the project and all articles.
    cosine_scores = util.cos_sim(project_embedding, article_embeddings)[0]

    relevant_articles: List[Article] = []
    logging.info(f"Filtering with a similarity threshold of {similarity_threshold:.2f}...")
    for i, article in enumerate(articles):
        score = cosine_scores[i].item()
        if score >= similarity_threshold:
            logging.info(f"-> PASS: Article '{article['title']}' is semantically relevant (Score: {score:.2f})")
            article['relevance_score'] = score  # Add score for potential downstream use
            relevant_articles.append(article)
        else:
            logging.debug(f"-> FAIL: Article '{article['title']}' is not relevant (Score: {score:.2f})")

    # Deduplicate the list of articles based on their URL link, keeping the one that appeared first.
    # This is important if the same article is found in multiple RSS feeds.
    unique_articles_map: Dict[str, Article] = {}
    for article in relevant_articles:
        link = article.get('link')
        if link and link not in unique_articles_map:
            unique_articles_map[link] = article

    final_list = list(unique_articles_map.values())

    logging.info(
        f"Vigilum finished. Kept {len(final_list)} of {len(articles)} articles after filtering and deduplication.")
    return final_list
