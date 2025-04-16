import logging
import os
from datetime import datetime
from typing import Any, Dict

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from mcp import StdioServerParameters
from mcpadapt.core import MCPAdapt
from mcpadapt.crewai_adapter import CrewAIAdapter

# Configure logging
logger = logging.getLogger(__name__)

@CrewBase
class ComponentDocumentationCrew:
    """
    Crew responsible for monitoring component documentation changes and generating changelogs.
    It analyzes Git history and Readme.md files in specified repositories.
    """

    def __init__(self, inputs=None):
        """
        Initialize the ComponentDocumentationCrew.

        Args:
            inputs (dict, optional): A dictionary containing necessary inputs,
                                     e.g., {'repository_url': '...'}. Defaults to None.
        """

        skill_registry_token = os.getenv("SKILL_REGISTRY_TOKEN")
        if not skill_registry_token:
            raise ValueError("SKILL_REGISTRY_TOKEN not found in environment variables")

        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError(
                "OPENAI_API_KEY is not set. Create a .env file at the root of the project with OPENAI_API_KEY=<your-api-key>"
            )

        print("Starting MCP connection for ComponentDocumentationCrew...")

        # Setup MCP connection to potentially access GitHub tools
        # Ensure the MCP server provides the necessary tools for Git/GitHub operations
        self._mcp_adapt_docs = MCPAdapt(
            StdioServerParameters(
                command="uvx", # Example command, adjust if needed
                args=[
                    "--from",
                    "keboola-skill-registry-mcp", # Example skill registry
                    "keboola-sr-mcp",
                    "--transport",
                    "stdio",
                    "--log-level",
                    "DEBUG",
                    "--api-url",
                    "https://ksr.canary-orion.keboola.dev/api", # Example API URL
                ],
                env={
                    "UV_PYTHON": "3.12",
                    "SKILL_REGISTRY_TOKEN": skill_registry_token,
                    **os.environ,
                },
            ),
            CrewAIAdapter(),
        )

        print("Attempting to connect to MCP server for ComponentDocumentationCrew...")
        try:
            self.mcp_tools = self._mcp_adapt_docs.__enter__()
            print("Successfully connected to MCP server for ComponentDocumentationCrew!")

            # Print available tools for debugging
            print("Available tools for ComponentDocumentationCrew:")
            if self.mcp_tools:
                for tool in self.mcp_tools:
                    print(f"- {tool.name}: {tool.description}")
            else:
                print("- No tools loaded via MCP.")
                # Consider raising an error or warning if specific tools are expected

        except Exception as e:
            print(f"Failed to connect to MCP server or load tools: {e}")
            # Ensure cleanup happens even if connection fails during init
            self._mcp_adapt_docs.__exit__(type(e), e, e.__traceback__)
            raise

        self.inputs = inputs or {}
        logger.info(f"ComponentDocumentationCrew initialized with inputs: {self.inputs}")

    def __del__(self):
        """Ensure MCP Adapter is properly closed on object destruction."""
        if hasattr(self, "_mcp_adapt_docs"):
            try:
                self._mcp_adapt_docs.__exit__(None, None, None)
                print("MCP connection closed for ComponentDocumentationCrew.")
            except RuntimeError as e:
                # Ignore potential 'Cannot close a running event loop' errors during shutdown
                logger.warning(f"Ignoring error during MCP close: {e}")
            except Exception as e:
                 logger.error(f"Error closing MCP connection: {e}")


    @agent
    def documentation_research_agent(self) -> Agent:
        """
        Defines the agent responsible for researching documentation changes.

        Returns:
            Agent: An instance of the documentation research agent.
        """
        return Agent(
            role="Component Documentation Analyst",
            goal="Identify documentation changes in component repositories and generate a concise changelog.",
            backstory="An expert agent specializing in analyzing Git repositories and Readme files to track documentation updates meticulously.",
            verbose=True,
            # Tools are loaded from the MCP connection
            tools=self.mcp_tools or [], # Use empty list if no tools loaded
        )

    @task
    def component_documentation_task(self) -> Task:
        """
        Creates the task for analyzing documentation changes and generating a changelog.

        Raises:
            ValueError: If the required 'repository_url' input is missing.

        Returns:
            Task: An instance of the documentation analysis task.
        """
        repository_url = self.inputs.get("repository_url")
        if not repository_url:
            raise ValueError("repository_url is required for component_documentation_task")

        logger.info(f"Creating documentation task for repository: {repository_url}")

        # Step-by-step description for the agent
        task_description = f"""
Analyze the component repository at '{repository_url}' for documentation changes in `Readme.md` and generate a changelog. Follow these steps:

1.  **Identify Recent Commits:** Use available tools to check for new commits since the last analysis (or a defined recent period). Focus on the component repository specified.
2.  **Access Readme.md:** Retrieve the latest version of the `Readme.md` file from the main branch (or specified branch).
3.  **Compare Documentation:** Use available tools (e.g., Git diff tool) to compare the current `Readme.md` with its previous version (the version before the latest commit affecting it).
4.  **Analyze Changes:** If differences are found in `Readme.md`:
    *   Carefully examine the 'diff' output.
    *   Identify the sections that were added, modified, or deleted.
    *   Focus on understanding the *meaning* of the documentation changes.
5.  **Generate Changelog:**
    *   Create a concise, human-readable changelog entry summarizing the documentation updates.
    *   Highlight the key changes made to the documentation.
    *   Example format: "- Updated installation instructions.", "- Added details on API endpoint X.", "- Removed outdated configuration section."
6.  **Output:**
    *   If changes were found, provide the generated changelog entry as the final answer.
    *   If no changes were found in `Readme.md` related to recent commits, state clearly: "No significant documentation changes found in Readme.md for recent commits."
7.  **Tool Usage:** Use the provided tools for Git operations (checking commits, fetching files, getting diffs) as needed. Follow tool instructions carefully.
"""
# Note: True HITL might require specific callbacks or manager agents depending on CrewAI version and desired interaction points.
# This task currently relies on the agent's ability to follow instructions and use tools.

        return Task(
            description=task_description,
            agent=self.documentation_research_agent(),
            human_input=True,
            expected_output="A concise changelog summarizing documentation changes in Readme.md, or a confirmation that no changes were found.",
        )

    @crew
    def component_documentation_crew(self) -> Crew:
        """
        Creates and configures the Component Documentation Crew.

        Returns:
            Crew: An instance of the Component Documentation Crew.
        """
        logger.info(f"Initializing Component Documentation Crew with inputs: {self.inputs}")
        return Crew(
            agents=[self.documentation_research_agent()],
            tasks=[self.component_documentation_task()],
            verbose=True,
            # Using sequential process for this single-agent, single-task flow.
            # For more complex scenarios or explicit HITL control points,
            # consider Process.hierarchical with a manager_llm or custom callbacks.
            process=Process.sequential,
        )

# Example usage (optional, for testing)
# if __name__ == "__main__":
#     # Load environment variables (e.g., from .env file)
#     # from dotenv import load_dotenv
#     # load_dotenv()
#
#     print("## Component Documentation Crew Example")
#     # Provide necessary inputs, especially the repository URL
#     inputs = {'repository_url': 'YOUR_COMPONENT_REPO_URL_HERE'} # Replace with a real URL
#
#     if 'YOUR_COMPONENT_REPO_URL_HERE' in inputs.values():
#          print("Please replace 'YOUR_COMPONENT_REPO_URL_HERE' with an actual repository URL in test_crew3.py")
#     else:
#         try:
#             doc_crew = ComponentDocumentationCrew(inputs=inputs)
#             result = doc_crew.component_documentation_crew().kickoff(inputs=inputs)
#             print("

########################")
#             print("## Crew Final Result:")
#             print("########################")
#             print(result)
#         except ValueError as e:
#             print(f"Error initializing or running crew: {e}")
#         except Exception as e:
#             print(f"An unexpected error occurred: {e}")
#             logger.exception("Unexpected error during crew execution:") 