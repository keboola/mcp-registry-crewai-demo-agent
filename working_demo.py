"""An example of using the LangChain adapter to adapt MCP tools to LangChain tools.

This example uses the PubMed API to search for studies.
"""

import os

from crewai import Agent, Crew, Task  # type: ignore
from dotenv import load_dotenv
from mcp import StdioServerParameters

from mcpadapt.core import MCPAdapt
from mcpadapt.crewai_adapter import CrewAIAdapter

load_dotenv()
if not os.environ.get("OPENAI_API_KEY"):
    raise ValueError(
        "OPENAI_API_KEY is not set. Create a .env file at the root of the project with OPENAI_API_KEY=<your-api-key>"
    )

with MCPAdapt(
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
                    **os.environ,
                },
            ),
            CrewAIAdapter(),
        ) as tools:
    # print(tools[0].run(request={"term": "efficient treatment hangover"}))
    # print(tools[0])
    # print(tools[0].description)
    # Create a simple agent with the pubmcp tool
    agent = Agent(
        role="Research Email Sender",
        goal="Send emails",
        backstory="You help sending emails to researchers",
        verbose=True,
        tools=tools,
    )

    # Create a task
    task = Task(
        description="Send an email about hangover treatments research following these steps:\n"
            "1. Search for contact '{researcher_name}' in HubSpot using the search tool\n"
            "2. If found, extract and use their email address directly\n"
            "3. If not found in the first page of results, check if pagination exists and continue searching through ALL available pages\n"
            "4. If still not found after checking ALL pagination pages, you MUST use the fallback email '{researcher_email}' provided in the input\n"
            "5. If both the HubSpot search and fallback email fail, only then pause and ask the user to provide an email address\n"
            "6. Once you have a valid email address, send an email with subject 'Inquiry about Hangover Treatments Research' and body: '{message}'\n"
            "7. In your final answer, clearly state which email address was used and why (found in HubSpot or used fallback)",
        agent=agent,
        expected_output="An email sent with confirmation of which email address was used and why"
    )

    crew = Crew(agents=[agent], tasks=[task], verbose=True)

    crew.kickoff(inputs={
        "researcher_name": "John Doe",
        "researcher_email": "radek.tomasek@keboola.com",
        "message": "Hello, I am interested in your research on hangover treatments. Can you provide more information?"
    })