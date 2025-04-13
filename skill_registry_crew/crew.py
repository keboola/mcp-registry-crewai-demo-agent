import os

from crewai import Agent, Crew, Process, Task
from dotenv import load_dotenv
from mcp import StdioServerParameters
from mcpadapt.core import MCPAdapt
from mcpadapt.crewai_adapter import CrewAIAdapter

load_dotenv()

class SkillRegistryCrew:
    """SkillRegistryCrew - A crew for working with the Keboola Skill Registry API"""

    def __init__(self):
        skill_registry_token = os.getenv("SKILL_REGISTRY_TOKEN")
        if not skill_registry_token:
            raise ValueError("SKILL_REGISTRY_TOKEN not found in environment variables")

        print("Starting MCP connection with correct executable...")

        mcp_adapt = MCPAdapt(
            StdioServerParameters(
                command="uvx",
                args=[
                    "--from",
                    "keboola-skill-registry-mcp",
                    "keboola-sr-mcp",
                    "--transport", "stdio",
                    "--log-level", "DEBUG",
                    "--api-url", "https://ksr.canary-orion.keboola.dev/api"
                ],
                env={
                    "UV_PYTHON": "3.12",
                    "SKILL_REGISTRY_TOKEN": skill_registry_token,
                    **os.environ
                }
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

        self._mcp_adapt = mcp_adapt

    def __del__(self):
        "Ensure MCP Adapter is properly closed on object destruction"
        if hasattr(self, "_mcp_adapt"):
            try:
                self._mcp_adapt.__exit__(None, None, None)
            except RuntimeError:
                # Ignore 'Cannot close a running event loop' errors
                pass

    def create_hubspot_contact(self, first_name, last_name, email, company=None):
        """Create a HubSpot contact directly using the MCP tool."""
        # Find the hubspot_create_contact tool
        create_contact_tool = None
        for tool in self.mcp_tools:
            if tool.name == "hubspot_create_contact":
                create_contact_tool = tool
                break

        if not create_contact_tool:
            raise ValueError("HubSpot create contact tool not found in MCP tools")

        # Prepare the parameters
        params = {
            "firstname": first_name,
            "lastname": last_name,
            "email": email
        }

        if company:
            params["company"] = company

        print(f"Executing HubSpot contact creation with parameters: {params}")

        # Execute the tool using run() method instead of invoke()
        try:
            result = create_contact_tool.run(**params)
            print("Contact creation successful!")
            return result
        except Exception as e:
            print(f"Error creating contact: {e}")
            raise

    def create_hubspot_opportunity(self, dealname, dealstage, amount=None, company_id=None):
        """Create a HubSpot opportunity (deal) directly using the MCP tool."""
        # Find the hubspot_create_opportunity tool
        create_opportunity_tool = None
        for tool in self.mcp_tools:
            if tool.name == "hubspot_create_opportunity":
                create_opportunity_tool = tool
                break

        if not create_opportunity_tool:
            raise ValueError("HubSpot create opportunity tool not found in MCP tools")

        # Prepare the parameters
        params = {
            "dealname": dealname,
            "dealstage": dealstage
        }

        if amount:
            params["amount"] = amount

        if company_id:
            params["company_id"] = company_id

        print(f"Executing HubSpot opportunity creation with parameters: {params}")

        try:
            result = create_opportunity_tool.run(**params)
            return result
        except Exception as e:
            print(f"Error creating opportunity: {e}")
            raise

    def run(self, operation, **kwargs):
        """Run operations based on the specified operation type."""
        try:
            if operation == "hubspot-contact":
                return self.create_hubspot_contact(
                    first_name=kwargs.get("first_name"),
                    last_name=kwargs.get("last_name"),
                    email=kwargs.get("email"),
                    company=kwargs.get("company")
                )
            elif operation == "hubspot-opportunity":
                return self.create_hubspot_opportunity(
                    dealname=kwargs.get("dealname"),
                    dealstage=kwargs.get("dealstage"),
                    amount=kwargs.get("amount"),
                    company_id=kwargs.get("company_id")
                )
            elif operation == "hubspot-all":
                # Execute both operations
                contact_result = self.create_hubspot_contact(
                    first_name=kwargs.get("first_name"),
                    last_name=kwargs.get("last_name"),
                    email=kwargs.get("email"),
                    company=kwargs.get("company")
                )

                opportunity_result = self.create_hubspot_opportunity(
                    dealname=f"{kwargs.get('company')} Deal",
                    dealstage=kwargs.get("dealstage", "appointmentscheduled"),
                    amount=kwargs.get("amount"),
                    company_id=kwargs.get("company_id")
                )

                return {
                    "contact": contact_result,
                    "opportunity": opportunity_result
                }
            else:
                raise ValueError(f"Unknown operation: {operation}")
        except Exception as e:
            print(f"Error executing operation {operation}: {e}")
            raise