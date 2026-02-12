import asyncio
import logging
from collections import deque
from typing import List, Dict, Any, Deque

from dotenv import load_dotenv
from langchain_classic.agents import create_react_agent, AgentExecutor
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool, render_text_description
from langchain_ollama import ChatOllama
from rich.console import Console

from .config import AppConfig, ConfigError
from .paths import resolve_paths, ApplicationPaths
from .utils import get_project_root
from .tools import create_sql_query_tool, create_web_fetcher_tool


def initialize_llm(config: AppConfig) -> BaseLanguageModel:
    """Initializes the LLM based on the provided configuration."""
    agent_cfg = config.ai_settings.inquisitor_agent
    ollama_cfg = config.ai_settings.providers.ollama

    if not ollama_cfg.base_url:
        raise ValueError("Ollama base_url is not configured in config.yaml.")

    logging.info(f"Initializing Inquisitor LLM with Ollama at {ollama_cfg.base_url}")
    return ChatOllama(
        model=agent_cfg.model,
        base_url=ollama_cfg.base_url,
        temperature=agent_cfg.temperature,
        num_predict=2048
    )


def assemble_agent(llm: BaseLanguageModel, config: AppConfig, paths: ApplicationPaths) -> AgentExecutor:
    """
    Assembles the tools, prompt, and agent executor.

    Args:
        llm: The initialized language model.
        config: The validated application configuration.
        paths: The data class that holds app paths.

    Returns:
        A configured AgentExecutor instance.
    """
    logging.info("Assembling the Inquisitor's toolbox...")
    sql_tool = create_sql_query_tool(paths.database)
    web_tool = create_web_fetcher_tool(config)
    tools: List[BaseTool] = [sql_tool, web_tool]

    rendered_tools = render_text_description(tools)
    tool_names = ", ".join([t.name for t in tools])

    try:
        prompt_template_str = paths.inquisitor_prompt.read_text(encoding='utf-8')
    except FileNotFoundError:
        logging.critical(f"FATAL: Inquisitor prompt not found at '{paths.inquisitor_prompt}'. Cannot start agent.")
        raise

    prompt = ChatPromptTemplate.from_template(prompt_template_str)
    prompt = prompt.partial(tools=rendered_tools, tool_names=tool_names)

    def handle_parsing_errors(error: Exception) -> str:
        """A custom error handler to guide the agent on parsing failures."""
        response = str(error)
        if "AgentAction" in response:
            return (
                "Error: That was not a valid AgentAction. "
                "Remember to use the correct format with 'Action:' and 'Action Input:'."
            )
        return f"Error: {response}"

    logging.info("Creating ReAct agent...")
    agent = create_react_agent(llm, tools, prompt)

    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=config.debug,
        handle_parsing_errors=handle_parsing_errors,
        max_iterations=7
    )


async def interactive_loop(agent_executor: AgentExecutor, console: Console):
    """Handles the main interactive Q&A loop with the user."""
    console.print("\n--- Inquisitor AI Assistant ---", style="bold blue")
    console.print("Ask me anything about the archived articles. Type 'exit' to end.")

    # Get the current running event loop
    loop = asyncio.get_running_loop()
    chat_history: Deque[BaseMessage] = deque(maxlen=20)

    while True:
        try:
            user_query = await loop.run_in_executor(None, lambda: console.input("\n[bold green]> [/bold green]"))
            if user_query.lower() == 'exit':
                console.print("Exiting. Goodbye!", style="bold yellow")
                break

            if not user_query.strip():
                continue

            with console.status("[bold yellow]Inquisitor is thinking...[/bold yellow]", spinner="dots"):
                response = await agent_executor.ainvoke({
                    "input": user_query,
                    "chat_history": list(chat_history)  # Pass a copy
                })

            console.print(f"\n[bold blue]Inquisitor:[/bold blue] {response['output']}")
            chat_history.append(HumanMessage(content=user_query))
            chat_history.append(AIMessage(content=response['output']))

        except KeyboardInterrupt:
            console.print("\nExiting. Goodbye!", style="bold yellow")
            break
        except Exception as e:
            logging.error(f"An error occurred in the main loop: {e}", exc_info=True)
            console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")


def inquisitor_main():
    """The main entrypoint for the interactive Inquisitor agent."""
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)-8s - %(name)-12s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console = Console()

    try:
        paths = resolve_paths(get_project_root())
        config = AppConfig.from_yaml(paths.config)

        if not paths.database.exists():
            console.print(f"[bold yellow]Warning:[/bold yellow] Database file not found at '{paths.database}'. "
                  "SQL queries may fail. Run the Legatus agent first to create it.")

        llm = initialize_llm(config)
        agent_executor = assemble_agent(llm, config, paths)

        asyncio.run(interactive_loop(agent_executor, console))

    except (ConfigError, ValueError, FileNotFoundError) as e:
        logging.critical(f"A critical error occurred during setup: {e}")
        console.print(f"[bold red]FATAL ERROR:[/bold red] {e}")
    except Exception as e:
        logging.critical(f"The Inquisitor agent failed to run. Error: {e}", exc_info=True)
        console.print(f"[bold red]An unexpected fatal error occurred: {e}[/bold red]")


if __name__ == "__main__":
    inquisitor_main()
