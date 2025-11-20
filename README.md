# Legatus AI - AI-Powered Dependency Analyst

![Legatus AI Banner](https://i.imgur.com/2i6yIfQ.png)

**Legatus AI is an automated, AI-driven agent that scans the tech landscape for news, releases, and articles relevant to your project's specific technology stack, providing you with prioritized, actionable analysis.**

---

## ✨ Key Features

*   **🧠 Intelligent Semantic Analysis:** Legatus understands the *context* of your project and finds articles that are conceptually related to your stack.
*   **🎯 Prioritized Reporting:** Uses a LLM of your choice to analyze relevant articles, assigning a criticality so you can immediately focus on what's urgent.
*   **💬 Interactive Q&A Agent (`Inquisitor`):** Chat with your project's knowledge base! Ask natural language questions about the articles Legatus has archived, like "What was the most critical security issue found last month?" or "Summarize the latest Retrofit release."
*   **🔌 Pluggable & Configurable:** Easily configure data sources (RSS feeds, GitHub Releases), define your project's tech stack, and tune the AI's behavior, all from a simple `config.yaml` file.
*   **📦 Dockerized & Portable:** Runs anywhere as a self-contained Docker container. Keep your host machine clean and ensure a reproducible environment.
*   **🤖 LLM Agnostic:** Supports local models via Ollama (e.g., Llama 3.1, Mistral) for privacy and cost-savings, as well as cloud providers like Google Vertex AI (Gemini).

---

## 🚀 Getting Started (v0.7.+)

Legatus AI is designed to be run as a Docker container.

### Prerequisites

*   [Docker](https://www.docker.com/products/docker-desktop/) installed and running.
*   **[Optional]** A GitHub account and a [Personal Access Token](https://github.com/settings/tokens) (classic) with `public_repo` scope to avoid API rate-limiting.

### 🛸 Quick Start (Recommended)

Run this one-time command to automatically create the necessary folders and configuration files in your current directory.

**Linux/macOS:**
```bash
mkdir legatus-project && cd legatus-project
docker run --rm -v "$(pwd):/app/target" yevkavaliou/legatus-agent:latest python -m src.legatus_ai.setup
```

**Windows (PowerShell):**
```powershell
mkdir legatus-project; cd legatus-project
docker run --rm -v "${pwd}:/app/target" yevkavaliou/legatus-agent:latest python -m src.legatus_ai.setup
```

### 🚗 Manual Start (More control for you)

First, create a project directory on your local machine to store your configuration and the agent's data.

```bash
# Create the main project folder
mkdir legatus-project
cd legatus-project

# Create the directory structure the agent expects
mkdir data prompts reports project_data
```

You need to provide two files in your `legatus-project` directory: `config.yaml` and `.env`.

Copy the example configuration from the repository (`config.yaml.example`) and save it as `config.yaml` in your project folder.

Create a file named `.env` and add your GitHub token. If you plan to use Google Vertex AI, add your credentials path as well.

### 📄 Configuration

**A. `config.yaml`**

**➡️ Edit `config.yaml`:**
*   Update the `project_info` section to describe your project.
*   **Crucially**, if you have a Gradle Version Catalog (`libs.versions.toml`), place it inside the `project_data` directory and make sure the setting is enabled in your `config.yaml`:
    ```yaml
    # inside your config.yaml
    version_catalog_file:
      enabled: true
    ```
* Alternatively, you can mount your gradle folder as volume, the agent will look for `libs.version.toml` there. 

**B. `.env`**

```env
# Your GitHub token is required if you don't want to be stopped by Github API quota
GITHUB_TOKEN="ghp_YourSecretTokenGoesHere"

# For Google Vertex AI (optional)
# GOOGLE_APPLICATION_CREDENTIALS=/app/gcp-creds.json
```

### 🤖 Run the Agent

Navigate to your `legatus-project` directory in your terminal and run the appropriate command for your operating system.

#### On Linux or macOS

```bash
docker run --rm -it \
  --name legatus-agent \
  -v "$(pwd)/config.yaml:/app/config.yaml" \
  -v "$(pwd)/.env:/app/.env" \
  -v "$(pwd)/project_data:/app/project_data" \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/reports:/app/reports" \
  -v "$(pwd)/hf_cache:/app/hf_cache" \
  yevkavaliou/legatus-agent:latest
```

#### On Windows (PowerShell)

```powershell
docker run --rm -it `
  --name legatus-agent `
  -v "${pwd}/config.yaml:/app/config.yaml" `
  -v "${pwd}/.env:/app/.env" `
  -v "${pwd}/project_data:/app/project_data" `
  -v "${pwd}/data:/app/data" `
  -v "${pwd}/reports:/app/reports" `
  -v "${pwd}/hf_cache:/app/hf_cache" `
  yevkavaliou/legatus-agent:latest
```

The agent will now run its analysis pipeline. When it's finished, you will find the generated report in your `reports` folder and the SQLite database in your `data` folder.

---

## 🗣️ Using the Inquisitor (Q&A Agent)

To chat with the data that Legatus has collected, run the Inquisitor agent. The command is nearly identical, you just need to specify the Inquisitor entry point.

```bash
# On Linux/macOS
docker run --rm -it \
  --name inquisitor-agent \
  -v "$(pwd)/config.yaml:/app/config.yaml" \
  -v "$(pwd)/.env:/app/.env" \
  -v "$(pwd)/data:/app/data" \
  yevkavaliou/legatus-agent:latest python -m src.legatus_ai.inquisitor
```

```powershell
# Windows (powershell)
docker run --rm -it `
  --name inquisitor-agent `
  -v "${pwd}/config.yaml:/app/config.yaml" `
  -v "${pwd}/.env:/app/.env" `
  -v "${pwd}/data:/app/data" `
  yevkavaliou/legatus-agent:latest python -m src.legatus_ai.inquisitor
```

This will start an interactive session where you can ask questions about the archived articles.

---

## 🔧 Customization

*   **Prompts:** To override the default AI prompts, place your own `prompt_legatus.txt` or `prompt_inquisitor.txt` files inside your local `prompts` directory. The agent will automatically detect and use them when your provide `-v "$(pwd)/prompts:/app/prompts"` variable.
*   **Data Sources:** Add your favorite RSS feeds and GitHub repositories to the `data_sources` section in `config.yaml`.
*   **Analysis Tuning:** Adjust the `vigil_similarity_threshold` in `config.yaml` to make the initial filtering more or less strict.
*   **SSL security:** If you see that some of the RSS feeds domains doesn't work due to SSL errors, add the domain into list of exclusions `skip_ssl_verify` in `config.yaml`

---

## 🗺️ Roadmap & Future Vision

Legatus AI is actively developed. Our vision is to create a comprehensive, proactive assistant for tech leads. Key features planned for future releases include:

*   **Enhanced Context Generation:** Move beyond dependency lists to analyze Gradle build files and source code (`grep`-like functionality) for a richer, more accunderstanding of your project's capabilities and configuration.
*   **Workflow Integrations:** Automatically create Jira tickets for critical vulnerabilities or send notifications to Slack for high-priority updates, seamlessly integrating with your team's workflow.
*   **Broader Ecosystem Support:** Add support for other package managers and ecosystems, such as Maven, npm, and Python's `pyproject.toml`.
*   **Smarter Agent Memory:** Enable the Inquisitor agent to have persistent conversation history and learn from user interactions.
urate 
---

## 🤝 Contributing

Contributions are welcome! Whether it's a bug report, a new feature, or an improvement to the documentation, please feel free to open an issue or submit a pull request.

## 📜 License

This project is licensed under the **Apache License 2.0**. See the [LICENSE](LICENSE) file for details.
