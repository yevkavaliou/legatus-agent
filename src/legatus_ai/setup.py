import logging
import shutil
import sys

from src.legatus_ai.utils import get_project_root

APP_ROOT = get_project_root()
INTERNAL_CONFIG_EXAMPLE = APP_ROOT / "config.yaml.example"

# The target location where we will write files.
# We expect the user to mount their current directory to this path.
TARGET_DIR = APP_ROOT / "target"

logging.basicConfig(level=logging.INFO, format='%(message)s')


def bootstrap_project():
    """
    Scaffolds a new Legatus project in the mounted /target directory.
    """
    print(f"Initializing Legatus AI project in: {TARGET_DIR}\n")

    if not TARGET_DIR.exists():
        logging.error("   Error: /target directory does not exist.")
        logging.error("   You must mount your current directory to /target.")
        logging.error("   Example: docker run -v \"$(pwd):/target\" ...")
        sys.exit(1)

    # 1. Create Directory Structure
    dirs_to_create = [
        "data",
        "reports",
        "project_data"
    ]

    for dir_name in dirs_to_create:
        dir_path = TARGET_DIR / dir_name
        if not dir_path.exists():
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                logging.info(f"Created directory: {dir_name}/")
            except OSError as e:
                logging.error(f"Failed to create {dir_name}: {e}")
        else:
            logging.info(f"Directory already exists: {dir_name}/")

    # 2. Copy config example file
    target_config = TARGET_DIR / "config.yaml.example"
    if not target_config.exists():
        try:
            if INTERNAL_CONFIG_EXAMPLE.exists():
                shutil.copy(INTERNAL_CONFIG_EXAMPLE, target_config)
                logging.info(f"Created example config: config.yaml.example")
            else:
                logging.error(f"Internal config example missing at {INTERNAL_CONFIG_EXAMPLE}")
        except OSError as e:
            logging.error(f"Failed to copy config: {e}")
    else:
        logging.info(f"Config file already exists, skipping.")

    # 3. Create .env template
    target_env = TARGET_DIR / ".env"
    if not target_env.exists():
        try:
            with open(target_env, 'w') as f:
                f.write("# GitHub Token (Optional, if you are not worrying about API quota)\n")
                f.write("# GITHUB_TOKEN=\n\n")
                f.write("# Google Cloud Credentials (Optional)\n")
                f.write("# GOOGLE_APPLICATION_CREDENTIALS=/app/gcp-creds.json\n")
            logging.info(f"Created template .env file")
        except OSError as e:
            logging.error(f"Failed to create .env file: {e}")
    else:
        logging.info(f".env file already exists, skipping.")

    print("\nInitialization complete!")
    print("   1. Rename 'config.yaml.example' to 'config.yaml'.")
    print("   2. Open 'config.yaml' and configure your project details.")
    print("   3. Open '.env' and add tokens if you plan to extensively use Github or Gemini models.")
    print("   4. Place your version catalog in 'project_data/'.")
    print("   5. Run the agent!")


if __name__ == "__main__":
    bootstrap_project()
