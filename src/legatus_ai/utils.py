import logging
import os
import ssl
from pathlib import Path
from typing import List, Union, Optional
from urllib.parse import urlparse

import certifi

# --- SSL Context Caching ---
# We cache the secure SSL context because it's the same for all secure requests.
# This avoids the small overhead of recreating it every time.
_secure_ssl_context: Optional[ssl.SSLContext] = None


def _get_secure_ssl_context() -> ssl.SSLContext:
    """
    Creates and caches a secure SSL context using the certifi certificate bundle.

    Using certifi ensures we have an up-to-date set of trusted Certificate Authorities.

    Returns:
        A secure ssl.SSLContext object.
    """
    global _secure_ssl_context
    if _secure_ssl_context is None:
        _secure_ssl_context = ssl.create_default_context(cafile=certifi.where())
    return _secure_ssl_context


def should_verify_ssl_for_url(url: str, domains_to_skip: List[str]) -> Union[ssl.SSLContext, bool]:
    """
    Determines the appropriate SSL context for a given URL based on security settings.

    If the URL's domain is in the 'domains_to_skip' list, this function
    returns False, DISABLING SSL verification for that request. This is a
    security risk and should be used with caution.

    For all other domains, it returns a secure, cached SSL context.

    Args:
        url: The URL to be checked.
        domains_to_skip: A list of domain strings for which to disable SSL verification.

    Returns:
        An ssl.SSLContext object for secure connections, or False to disable verification.
    """
    if not domains_to_skip:
        return _get_secure_ssl_context()

    try:
        # urlparse is more robust than simple string matching
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
    except Exception:
        # If URL parsing fails for some reason, default to being secure.
        return _get_secure_ssl_context()

    # Using a generator expression with any() is a clean and efficient way to check for membership.
    if any(skip_domain in domain for skip_domain in domains_to_skip):
        logging.warning(
            f"Disabling SSL certificate verification for URL '{url}' as its domain '{domain}' "
            "matches a domain in the skip list. This is a security risk and should only be "
            "used for trusted sites with known certificate issues."
        )
        return False

    return _get_secure_ssl_context()


def get_project_root() -> Path:
    """
    Determines the project root path.

    If the 'RUNNING_IN_DOCKER' environment variable is set, it assumes the root
    is '/app'. Otherwise, it calculates the root relative to this file's location,
    making it suitable for local development.

    (This file is in /src/legatus_ai/, so root is two levels up).
    """
    if os.getenv("RUNNING_IN_DOCKER"):
        return Path("/app")
    else:
        return Path(__file__).resolve().parent.parent.parent