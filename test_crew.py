import os

from dotenv import load_dotenv

# Import both crew classes
from orchestrator import  EmailResearchCrew


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

    # --- Inputs for Email Research Crew ---
    researcher_name_for_email = "Radek Tomasek" # Example name for email search
    researcher_email_fallback = "martin.vasko@keboola.com" # Example fallback email
    message_for_email = "Hello, I am interested in your latest publication on AI ethics. Could we connect?" # Example message


    # --- Initialize Email Research Crew ---
    print("Initializing Email Research Crew...")
    email_crew = EmailResearchCrew(
         inputs={
            "researcher_name": researcher_name_for_email,
            "researcher_email": researcher_email_fallback,
            "message": message_for_email,
            # Remove lead management inputs from this crew's initialization
        }
    )


    result = email_crew.research_email_crew().kickoff()
    # Return results from both crews
    return {
        "status": "success",
        "result": result,
    }


if __name__ == "__main__":
    final_output = main()
    print(f"\nFinal Output:\n{final_output}")
