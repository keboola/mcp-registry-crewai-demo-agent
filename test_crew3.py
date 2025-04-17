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
    Crew responsible for generating documentation updates based on changes
    between specific commits within a branch (`ref`). It analyzes Git history
    and Readme.md files based on 'before' and 'after' commit hashes provided.
    """

    def __init__(self, inputs=None):
        """
        Initialize the ComponentDocumentationCrew.
        Connects to MCP to access necessary tools (like GitHub/Git tools).

        Args:
            inputs (dict, optional): A dictionary for potential future static
                                     configurations. Runtime inputs like 'ref',
                                     'before', 'after', and 'repository_url'
                                     are expected to be passed during the
                                     `kickoff` method. Defaults to None.
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
    def repository_discovery_agent(self) -> Agent:
        """
        Defines the agent responsible for discovering or verifying repositories using available tools.
        It understands how to handle paginated results from repository listing tools.

        Returns:
            Agent: An instance of the repository discovery agent.
        """
        return Agent(
            role="Repository Discovery Specialist",
            goal=(
                "Utilize provided tools (e.g., GitHub API tools via MCP) to find or verify specific component repositories. "
                "If listing repositories, efficiently handle pagination: make the first request without a 'page' parameter, "
                "then, if more results exist, iterate using 'page=1', 'page=2', etc. (up to a limit of 10 pages), always using 'per_page=100'."
            ),
            backstory=(
                "An expert in navigating code hosting platforms via APIs. Skilled in searching, filtering, and handling large lists of repositories systematically, "
                "paying close attention to API limits and pagination requirements."
            ),
            verbose=True,
            tools=self.mcp_tools or [],
        )

    @agent
    def documentation_analysis_agent(self) -> Agent:
        """
        Defines the agent responsible for analyzing documentation changes between two specific commits *for a verified repository*.

        Returns:
            Agent: An instance of the documentation analysis agent.
        """
        return Agent(
            role="Documentation Change Analyst",
            goal="Analyze the changes in README.md between two specific commits (`before` and `after`) within a given branch (`ref`) for a *specific, verified* repository, and generate a concise changelog entry.",
            backstory="An expert agent focused on pinpointing documentation modifications within Git history for a known repository. It precisely compares file versions between commits to generate accurate documentation updates.",
            verbose=True,
            tools=self.mcp_tools or [],
        )

    @task
    def repository_verification_task(self) -> Task:
        """
        Creates the task for verifying the target repository provided via kickoff inputs.
        While this agent *can* list repositories with pagination, this task focuses on the single repo.

        Returns:
            Task: An instance of the repository verification task.
        """
        logger.info("Creating repository verification task. Inputs expected via kickoff.")
        task_description = f"""
Verify the existence and accessibility of the component repository specified by the input `repository_url`: {{repository_url}}.

1.  **Input:** The repository URL is: {{repository_url}}
2.  **Action:** Use available tools (e.g., a GitHub 'get repository details' tool) using the specific repository URL '{{repository_url}}' provided as input to confirm that the repository exists and is accessible.
3.  **Output:**
    *   If successful, confirm the repository '{{repository_url}}' is valid. You might output basic details like the full name or ID as context for the next step.
    *   If the repository cannot be found or accessed, report the error clearly, mentioning '{{repository_url}}'.
4.  **Tool Usage:** You MUST use the provided tools to interact with the repository source (e.g., GitHub), applying them to the given repository URL: '{{repository_url}}'.
    **Important:** When calling any tool, ensure you do not include a `properties` field in the tool's input arguments.
"""
        return Task(
            description=task_description,
            agent=self.repository_discovery_agent(),
            expected_output="Confirmation that the repository specified in `repository_url` (e.g., {repository_url}) is valid and accessible, potentially including basic identifying information, or an error message if not."
        )

    @task
    def documentation_analysis_task(self) -> Task:
        """
        Creates the task for analyzing documentation changes between specific commits
        in the repository verified by the previous task.

        Returns:
            Task: An instance of the documentation analysis task for specific commits.
        """
        logger.info("Creating documentation analysis task. Depends on repository verification task.")

        task_description = f"""
Analyze documentation changes in `README.md` between two specific commits within a given branch (`ref`) for the specific repository confirmed in the previous step.

You will use the following inputs provided via the kickoff method:
- Repository URL: {{repository_url}}
- Branch/Ref: {{ref}}
- Before Commit: {{before}}
- After Commit: {{after}}

Follow these steps:

1.  **Context:** Acknowledge the repository '{{repository_url}}' has been verified by the previous task.
2.  **Fetch `README.md` at 'before' commit:** Use available Git tools to retrieve the *exact* content of the `README.md` file as it existed at the commit hash '{{before}}' within the repository '{{repository_url}}'. Handle cases where the file might not exist at this commit.
3.  **Fetch `README.md` at 'after' commit:** Use available Git tools to retrieve the *exact* content of the `README.md` file as it existed at the commit hash '{{after}}' within the repository '{{repository_url}}'. Handle cases where the file might not exist at this commit.
4.  **Compare Documentation:**
    *   If `README.md` exists in both commits ('{{before}}' and '{{after}}'), use available tools (e.g., a diff tool or function) to compare the content from the '{{after}}' commit against the content from the '{{before}}' commit for the repository '{{repository_url}}'.
    *   If `README.md` was created in the '{{after}}' commit (didn't exist in '{{before}}'), note this as a creation event for '{{repository_url}}'.
    *   If `README.md` was deleted (existed in '{{before}}', not in '{{after}}'), note this as a deletion event for '{{repository_url}}'.
5.  **Analyze Changes:**
    *   If differences are found (or creation/deletion occurred between '{{before}}' and '{{after}}'):
        *   Carefully examine the differences ('diff').
        *   Identify the sections added, modified, or deleted.
        *   Focus on summarizing the *meaning* of the documentation changes concisely.
6.  **Generate Changelog Entry:**
    *   Based on the analysis, create a single, concise, human-readable changelog entry describing the documentation update for repository '{{repository_url}}' on ref '{{ref}}'.
    *   Mention the `ref` ('{{ref}}') if helpful.
    *   Example: "[{{ref}}] Updated installation instructions in README.md."
    *   Example: "[{{ref}}] Added initial README.md."
    *   Example: "[{{ref}}] Removed outdated section from README.md."
7.  **Output:**
    *   Provide the generated changelog entry as the final answer.
    *   If no changes were detected between commit '{{before}}' and commit '{{after}}' for `README.md` in repository '{{repository_url}}' on ref '{{ref}}', state clearly: "No changes found in README.md between commit {{before}} and {{after}} on ref {{ref}} for repository {{repository_url}}."
8.  **Tool Usage:** You MUST use the provided tools for fetching file contents at specific commits ('{{before}}', '{{after}}') and potentially comparing files within the context of the repository '{{repository_url}}'. Follow tool instructions carefully.
"""

        return Task(
            description=task_description,
            agent=self.documentation_analysis_agent(),
            expected_output="A concise changelog entry summarizing the changes in README.md between the 'before' ({before}) and 'after' ({after}) commits for the given 'ref' ({ref}) and 'repository_url' ({repository_url}), or a confirmation that no changes were found.",
            context=[self.repository_verification_task()]
        )

    @crew
    def component_documentation_crew(self) -> Crew:
        """
        Creates and configures the Component Documentation Crew using a two-step process:
        1. Verify the repository.
        2. Analyze documentation changes within that repository.

        Returns:
            Crew: An instance of the Component Documentation Crew.
        """
        logger.info(f"Initializing Component Documentation Crew with verification and analysis steps.")
        return Crew(
            agents=[
                self.repository_discovery_agent(),
                self.documentation_analysis_agent()
                ],
            tasks=[
                self.repository_verification_task(),
                self.documentation_analysis_task()
                ],
            verbose=True,
            process=Process.sequential,
        )

# Example usage (optional, for testing)
if __name__ == "__main__":
    # Load environment variables (e.g., from .env file)
    # from dotenv import load_dotenv
    # load_dotenv()

    print("## Component Documentation Crew Example (Specific Commit)")
    # Example inputs mimicking a GitHub webhook payload structure
    # These would normally come from the webhook event
    kickoff_inputs = {
        'repository_url': 'your_org/your_component_repo', # Replace with actual repo identifier/URL
        'ref': 'refs/heads/feature/update-docs',           # Example branch ref
        'before': 'a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0', # Example 'before' commit hash
        'after': 'f0e9d8c7b6a5f4e3d2c1b0a9f8e7d6c5b4a3b2a1'  # Example 'after' commit hash
    }

    try:
        # Pass static inputs if any during crew class initialization (here, none needed)
        doc_crew = ComponentDocumentationCrew()
        # Pass the specific commit/ref info during kickoff
        result = doc_crew.component_documentation_crew().kickoff(inputs=kickoff_inputs)
        print("\n\n########################")
        print("## Crew Final Result:")
        print("########################")
        print(result)
    except ValueError as e:
        print(f"Error initializing or running crew: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        logger.exception("Unexpected error during crew execution:") 