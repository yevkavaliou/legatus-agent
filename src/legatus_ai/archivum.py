import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Any, Set

# --- Schema Definition ---
TABLE_NAME = "articles"
SCHEMA = f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        link TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        criticality_score INTEGER,
        reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""
# A simple type alias for clarity
AnalysisResult = Dict[str, Any]


def get_db_connection(db_path: Path) -> sqlite3.Connection:
    """
    Establishes a connection to the SQLite database.

    Args:
        db_path: The path to the SQLite database file.

    Returns:
        A sqlite3.Connection object.

    Raises:
        sqlite3.Error: If a connection cannot be established.
    """
    try:
        # The parent directory will be created if it doesn't exist.
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path, check_same_thread=False)
        logging.info(f"Database connection established at '{db_path}'")
        return conn
    except sqlite3.Error as e:
        logging.error(f"Database connection error at '{db_path}': {e}")
        raise


def initialize_database(db_path: Path):
    """
    Creates the database and the articles table if they don't exist.

    Args:
        db_path: The path to the SQLite database file.

    Raises:
        sqlite3.Error: If the table cannot be created.
    """
    try:
        with get_db_connection(db_path) as conn:
            conn.execute(SCHEMA)
            conn.commit()
            logging.info(f"Database schema '{TABLE_NAME}' initialized successfully.")
    except sqlite3.Error as e:
        logging.error(f"Database error during schema initialization: {e}")
        raise


def add_articles_to_archive(db_path: Path, analysis_results: List[AnalysisResult]):
    """

    Adds a list of successfully analyzed articles to the database.

    Args:
        db_path: The path to the SQLite database file.
        analysis_results: A list of analysis result dictionaries.
    """
    if not analysis_results:
        return

    articles_to_insert: List[Tuple] = []
    for result in analysis_results:
        analysis = result.get('analysis', {})
        score = analysis.get('criticality_score')
        try:
            criticality_score = int(score) if score is not None else None
        except (ValueError, TypeError):
            criticality_score = None

        articles_to_insert.append((
            result.get('link'),
            result.get('title'),
            criticality_score
        ))

    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            query = f"INSERT OR IGNORE INTO {TABLE_NAME} (link, title, criticality_score) VALUES (?, ?, ?)"
            cursor.executemany(query, articles_to_insert)
            conn.commit()
            logging.info(f"Archived {cursor.rowcount} new articles in the database.")
    except sqlite3.Error as e:
        logging.error(f"Failed to add articles to archive: {e}")


def filter_new_articles(db_path: Path, articles: List[AnalysisResult]) -> List[AnalysisResult]:
    """
    Filters a list of articles, returning only those not already in the database.

    Args:
        db_path: The path to the SQLite database file.
        articles: A list of candidate articles to check against the archive.

    Returns:
        A list of articles that are not present in the archive.
    """
    if not articles:
        return []

    links_to_check: Set[str] = {article['link'] for article in articles if 'link' in article}
    if not links_to_check:
        return []

    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            placeholders = ', '.join('?' for _ in links_to_check)
            query = f"SELECT link FROM articles WHERE link IN ({placeholders})"

            cursor.execute(query, tuple(links_to_check))
            existing_links: Set[str] = {row[0] for row in cursor.fetchall()}
    except sqlite3.Error as e:
        logging.error(f"Could not query archive for existing articles: {e}. Assuming all are new.")
        return articles

    new_articles = [
        article for article in articles if article['link'] not in existing_links
    ]

    logging.info(f"Archive check: Found {len(new_articles)} new articles out of {len(articles)} relevant candidates.")
    return new_articles
