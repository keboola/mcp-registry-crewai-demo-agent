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
        It connects to MCP to access necessary tools (like GitHub tools).

        Args:
            inputs (dict, optional): A dictionary for potential future configurations.
                                     Defaults to None.
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
        Defines the agent responsible for researching documentation changes across multiple repositories.

        Returns:
            Agent: An instance of the documentation research agent.
        """
        return Agent(
            role="Component Documentation Analyst",
            goal="Discover component repositories, analyze documentation changes in their PRs/branches by comparing Readme.md files, and generate an aggregated changelog.",
            backstory="An expert agent specializing in analyzing Git repositories and Readme files across an organization to track documentation updates meticulously.",
            verbose=True,
            # Tools are loaded from the MCP connection (expected to include GitHub/Git tools)
            tools=self.mcp_tools or [], # Use empty list if no tools loaded
        )

    @task
    def component_documentation_task(self) -> Task:
        """
        Creates the task for discovering repositories, analyzing documentation changes in their PRs,
        and generating an aggregated changelog.

        Returns:
            Task: An instance of the documentation analysis task.
        """
        # No longer requires repository_url input
        logger.info(f"Creating documentation task with inputs: {self.inputs}")

        # Updated step-by-step description for the agent
        task_description = f"""
Analyze documentation changes in `Readme.md` across multiple component repositories and generate an aggregated changelog. Follow these steps:

1.  **Discover Repositories:** Use available tools (e.g., a GitHub tool) to list all accessible component repositories. Filter or identify repositories designated as 'components' if possible based on naming conventions or available metadata.
2.  **Iterate Through Repositories:** For each identified component repository:
    a. **Identify Relevant PRs/Branches:** Use tools to list open Pull Requests (PRs) or recently updated feature branches (e.g., updated in the last week). You might need to define 'relevant' based on common branch naming patterns (like 'feature/...').
    b. **Iterate Through PRs/Branches:** For each relevant PR or branch found in the repository:
        i.  **Get Base Readme.md:** Retrieve the content of the `Readme.md` file from the main/master branch of the repository.
        ii. **Get PR/Branch Readme.md:** Retrieve the content of the `Readme.md` file from the specific PR or feature branch.
        iii.**Compare Documentation:** Use available tools (e.g., a diff tool or function) to compare the content of the PR/branch `Readme.md` against the base (main/master) `Readme.md`.
        iv. **Analyze Changes:** If differences are found:
            *   Carefully examine the differences ('diff').
            *   Identify the sections added, modified, or deleted.
            *   Focus on understanding the *meaning* of the documentation changes.
        v.  **Generate Changelog Entry (if changed):**
            *   If changes were found, create a concise, human-readable changelog entry specific to this PR/branch and repository.
            *   Include the repository name and PR/branch name in the entry.
            *   Example: "[Repo: my-component | PR: #123] - Updated installation instructions."
            *   Store this entry.
3.  **Aggregate Changelog:** Combine all the generated changelog entries from the different repositories and PRs/branches into a single report.
4.  **Output:**
    *   Provide the aggregated changelog report as the final answer.
    *   If no documentation changes were found across any repositories/PRs, state clearly: "No significant documentation changes found in Readme.md files for observed repositories and PRs/branches."
5.  **Tool Usage:** You MUST use the provided tools for discovering repositories, listing PRs/branches, fetching file contents (Readme.md from different branches), and potentially comparing files. Follow tool instructions carefully.
"""
# Note: True HITL might require specific callbacks or manager agents depending on CrewAI version and desired interaction points.
# This task currently relies on the agent's ability to follow instructions and use tools for discovery and comparison.

        return Task(
            description=task_description,
            agent=self.documentation_research_agent(),
            expected_output="An aggregated changelog report summarizing Readme.md changes across relevant repositories and their PRs/branches, or a confirmation that no changes were found.",
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
#     # Inputs might be empty or used for other configs in the future
#     inputs = {}
#
#     try:
#         doc_crew = ComponentDocumentationCrew(inputs=inputs)
#         # Kickoff no longer needs specific repo URL in inputs for the task itself
#         result = doc_crew.component_documentation_crew().kickoff(inputs=inputs)
#         print("\n\n########################")
#         print("## Crew Final Result:")
#         print("########################")
#         print(result)
#     except ValueError as e:
#         print(f"Error initializing or running crew: {e}")
#     except Exception as e:
#         print(f"An unexpected error occurred: {e}")
#         logger.exception("Unexpected error during crew execution:") 