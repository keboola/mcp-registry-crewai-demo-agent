import os

from dotenv import load_dotenv

from orchestrator import LeadManagementCrew


def main():
    # Load environment variables from .env file
    load_dotenv()

    # Check for required environment variables
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError(
            "OPENAI_API_KEY is not set. Create a .env file with OPENAI_API_KEY=<your-api-key>"
        )

    if not os.environ.get("SKILL_REGISTRY_TOKEN"):
        raise ValueError(
            "SKILL_REGISTRY_TOKEN is not set. Add it to your .env file."
        )

    # Sample sales note - you can replace this with user input or data from another source
    sample_note = """
    Had a great meeting with John Smith (john.smith@example.com) today. 
    He's interested in our enterprise solution for his company. 
    The opportunity is for a full platform implementation worth about $75,000.
    Will follow up next week to discuss details.
    """
    researcher_name = "John Doe"
    researcher_email = "john.doe@example.com"
    message = "Hello, I am interested in your research on hangover treatments. Can you provide more information?"
    # Initialize the crew with the sample note
    crew = LeadManagementCrew(
        inputs={
            "note": sample_note,
            "researcher_name": researcher_name,
            "researcher_email": researcher_email,
            "message": message
        }
    )

    # Run the crew
    print("Starting Lead Management process...")
    result = crew.lead_management_crew().kickoff()
    email = crew.research_email_crew().kickoff()

    return {
        "status": "success",
        "result": str(result),
        "email": email,
    }


if __name__ == "__main__":
    main()
