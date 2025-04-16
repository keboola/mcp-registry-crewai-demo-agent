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
class EmailResearchCrew:
    """Email research crew for finding contacts and sending emails"""

    def __init__(self, inputs=None):
        """Initialize the crew with inputs and MCP connection"""

        skill_registry_token = os.getenv("SKILL_REGISTRY_TOKEN")
        if not skill_registry_token:
            raise ValueError("SKILL_REGISTRY_TOKEN not found in environment variables")

        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError(
                "OPENAI_API_KEY is not set. Create a .env file at the root of the project with OPENAI_API_KEY=<your-api-key>"
            )

        print("Starting MCP connection for EmailResearchCrew...")

        self._mcp_adapt_email = MCPAdapt( 
            StdioServerParameters(
                command="uvx",
                args=[
                    "--from",
                    "keboola-skill-registry-mcp",
                    "keboola-sr-mcp",
                    "--transport",
                    "stdio",
                    "--log-level",
                    "DEBUG",
                    "--api-url",
                    "https://ksr.canary-orion.keboola.dev/api",
                ],
                env={
                    "UV_PYTHON": "3.12",
                    "SKILL_REGISTRY_TOKEN": skill_registry_token,
                    **os.environ,
                },
            ),
            CrewAIAdapter(),
        )

        print("Attempting to connect to MCP server for EmailResearchCrew...")
        self.mcp_tools = self._mcp_adapt_email.__enter__()
        print("Successfully connected to MCP server for EmailResearchCrew!")

        # Print available tools for debugging
        print("Available tools for EmailResearchCrew:")
        for tool in self.mcp_tools:
            print(f"- {tool.name}: {tool.description}")

        self.inputs = inputs or {}
        logger.info(f"EmailResearchCrew initialized with inputs: {self.inputs}")

    def __del__(self):
        "Ensure MCP Adapter is properly closed on object destruction"
        if hasattr(self, "_mcp_adapt_email"):
            try:
                self._mcp_adapt_email.__exit__(None, None, None)
            except RuntimeError:
                # Ignore 'Cannot close a running event loop' errors
                pass

    @agent
    def research_email_agent(self) -> Agent:
        return Agent(
            role="Research Email Sender",
            goal="Find contact emails and send emails",
            backstory="You are an expert in finding contact information within HubSpot and sending emails. The schema contains limit as integer not string",
            verbose=True,
            tools=self.mcp_tools,
        )

    @task
    def research_email_task(self) -> Task:
        """Creates a research task for finding and sending an email"""
        # Get inputs specific to this task
        researcher_name = self.inputs.get("researcher_name")
        researcher_email = self.inputs.get("researcher_email")
        message = self.inputs.get("message")

        # Validate required inputs for this task
        if not researcher_name:
            raise ValueError("researcher_name is required for research_email_task")
        if not researcher_email:
            raise ValueError("researcher_email (fallback) is required for research_email_task")
        if not message:
            raise ValueError("message is required for research_email_task")

        print(f"EmailResearchCrew Inputs: Name='{researcher_name}', Fallback='{researcher_email}', Msg='{message[:20]}...'")

        # Use triple quotes for the multi-line description string for clarity and robustness
        description_string = f"""Send an email about hangover treatments research following these steps:
1. Search for contact '{researcher_name}' in HubSpot using the search tool (e.g., 'radekdemo').
   **IMPORTANT TOOL USAGE:** When calling the search tool, provide the arguments as a single JSON **string** representing the parameters directly.
   For example: '"limit": 10, "properties": "email"'. Do **not** nest these parameters inside another key like 'properties'.
2. If found, extract and use their email address directly
3. If not found in the first page of results, check if pagination exists and continue searching through ALL available pages
4. If still not found after checking ALL pagination pages, you MUST use the fallback email '{researcher_email}' provided in the input
5. If both the HubSpot search and fallback email fail, only then pause and ask the user to provide an email address
6. Once you have a valid email address, send an email with subject 'Inquiry about Hangover Treatments Research' and body: '{message}'
7. In your final answer, clearly state which email address was used and why (found in HubSpot or used fallback)
"""

        return Task(
            description=description_string,
            agent=self.research_email_agent(),
            expected_output="An email sent with confirmation of which email address was used and why"
        )

    @crew
    def research_email_crew(self) -> Crew:
        """Creates the email research and sending crew"""
        logger.info(f"Initialising email research crew with inputs: {self.inputs}")

        return Crew(
            agents=[self.research_email_agent()],
            tasks=[self.research_email_task()],
            verbose=True,
            process=Process.sequential,
        )


def get_status() -> Dict[str, Any]:
    """
    Get the current status of the service.
    """
    return {"status": "running", "timestamp": datetime.now().isoformat()}
