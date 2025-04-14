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
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

from pydantic import BaseModel


class NoteExtractionModel(BaseModel):
    name: str
    email: str
    opportunity_name: str
    value: str


@CrewBase
class LeadManagementCrew:
    """Lead management crew for handling sales leads from sales person notes"""

    def __init__(self, inputs=None):
        """Initialize the crew with inputs"""

        skill_registry_token = os.getenv("SKILL_REGISTRY_TOKEN")
        if not skill_registry_token:
            raise ValueError("SKILL_REGISTRY_TOKEN not found in environment variables")

        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError(
                "OPENAI_API_KEY is not set. Create a .env file at the root of the project with OPENAI_API_KEY=<your-api-key>"
            )

        print("Starting MCP connection with correct executable...")

        mcp_adapt = MCPAdapt(
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

        print("Attempting to connect to MCP server...")
        self.mcp_tools = mcp_adapt.__enter__()
        print("Successfully connected to MCP server!")

        # Print available tools for debugging
        print("Available tools:")
        for tool in self.mcp_tools:
            print(f"- {tool.name}: {tool.description}")

        self.inputs = inputs or {}
        logger.info(f"ContentCreationCrew initialized with inputs: {self.inputs}")

    def __del__(self):
        "Ensure MCP Adapter is properly closed on object destruction"
        if hasattr(self, "_mcp_adapt"):
            try:
                self._mcp_adapt.__exit__(None, None, None)
            except RuntimeError:
                # Ignore 'Cannot close a running event loop' errors
                pass

    @agent
    def note_parser_agent(self) -> Agent:
        """Creates a research agent for gathering information"""
        return Agent(
            role="Note Parser",
            goal="Extract contact name, email, opportunity name and value from unstructured sales notes",
            backstory="Expert in analyzing free-text notes and turning them into structured CRM-ready data.",
            verbose=True,
        )

    @agent
    def hubspot_agent(self) -> Agent:
        """Creates an agent for managing Hubspot CRM operations"""
        return Agent(
            role="Hubspot CRM Manager",
            goal="Create contacts in Hubspot if they don't exist and then create opportunities",
            backstory="Expert in CRM operations who ensures leads are properly tracked in Hubspot",
            verbose=True,
            tools=self.mcp_tools,
        )

    @task
    def note_parser_task(self) -> Task:
        """Creates a research task for the given topic"""
        # Get topic from inputs
        note = (
            self.inputs.get("note") if hasattr(self, "inputs") and self.inputs else None
        )

        if not note:
            raise ValueError("Note is required for note_parser_task")

        return Task(
            description=(
                f'Extract structured lead information from the following sales note:\n\n"{note}"\n\n'
                f"Return only the structured data as requested."
            ),
            expected_output="Extracted lead info with name, email, opportunity_name, and value.",
            agent=self.note_parser_agent(),
            output_json=NoteExtractionModel,
        )

    @task
    def hubspot_task(self) -> Task:
        """Creates a task for Hubspot CRM operations"""
        return Task(
            description=(
                "Using the extracted lead information, perform the following steps:\n"
                "1. Check if the contact already exists in Hubspot using their email\n"
                "2. If the contact doesn't exist, create a new contact with their name and email\n"
                "3. Create a new opportunity/deal for the contact with the opportunity name and value\n"
                "4. Return the IDs of the created or existing contact and the new opportunity"
            ),
            expected_output="Hubspot contact ID and opportunity ID",
            agent=self.hubspot_agent(),
            context=[self.note_parser_task()],
        )

    @crew
    def lead_management_crew(self) -> Crew:
        """Creates the lead management crew with note parsing and Hubspot integration"""
        # Log the topic being used
        note = (
            self.inputs.get("note") if hasattr(self, "inputs") and self.inputs else None
        )
        logger.info(f"Initialising crew with note: {note}")

        return Crew(
            agents=[self.note_parser_agent(), self.hubspot_agent()],
            tasks=[self.note_parser_task(), self.hubspot_task()],
            verbose=True,
            process=Process.sequential,
        )


def get_status() -> Dict[str, Any]:
    """
    Get the current status of the service.
    """
    return {"status": "running", "timestamp": datetime.now().isoformat()}
