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
    Had a great meeting with John Smith (john.smith+dev1@example.com) today. 
    He's interested in our enterprise solution for his company. 
    The opportunity is for a full platform implementation worth about $75,000.
    Will follow up next week to discuss details.
    """

    # Initialize the crew with the sample note
    crew = LeadManagementCrew(inputs={"note": sample_note})

    # Run the crew
    print("Starting Lead Management process...")
    result = crew.lead_management_crew().kickoff()

    # Display results
    print("\n=== RESULTS ===")
    print(result)
    print("===============")


if __name__ == "__main__":
    main()
