
import os

from dotenv import load_dotenv

# Import both crew classes
from note_taker import LeadManagementCrew


def main():
    # Load environment variables from .env file
    load_dotenv()


    # --- Inputs for Lead Management Crew ---
    sample_note = """
    Had a great meeting with Jane Doe (jane.doe@crmexample.com) today. 
    She's interested in our basic tier for her startup. 
    The opportunity is for a 1-year subscription worth about $5,000.
    Need to create contact and deal in Hubspot.
    """

    # --- Initialize Lead Management Crew ---
    print("Initializing Lead Management Crew...")
    lead_crew = LeadManagementCrew(
        inputs={
            "note": sample_note,
            # Remove email research inputs from this crew's initialization
        }
    )
    result = lead_crew.lead_management_crew().kickoff()
    return result


if __name__ == "__main__":
    final_output = main()
    print(f"\nFinal Output:\n{final_output}")

