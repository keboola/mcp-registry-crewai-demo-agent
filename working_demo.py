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
        description="Send an email to the researcher David Test that is available in the hubspot as a contact with the following text: 'Hello, I am interested in your research on hangover treatments. Can you provide more information?'",
        agent=agent,
        expected_output="An email sent",
    )

    # Create a crew
    crew = Crew(agents=[agent], tasks=[task], verbose=True)

    # Run the crew
    crew.kickoff(inputs={"email":"Send an email to the researcher david@keboola.com with the following text: 'Hello, I am interested in your research on hangover treatments. Can you provide more information?'"})