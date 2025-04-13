#!/usr/bin/env python
import sys
from skill_registry_crew.crew import SkillRegistryCrew

def run(operation, **kwargs):
    """
    Run the crew with specified operation and parameters.

    Args:
        operation: The operation to perform (e.g. "hubspot-contact", "hubspot-opportunity")
        **kwargs: Additional parameters for the operation
    """
    try:
        crew_instance = SkillRegistryCrew()
        result = crew_instance.run(operation, **kwargs)
        print(result)
        return result
    except Exception as e:
        error_msg = f"An error occurred while running the operation: {e}"
        print(error_msg)
        raise Exception(error_msg)

def create_hubspot_contact(first_name, last_name, email, company=None):
    """
    Create a contact in HubSpot.
    """
    return run(
        operation="hubspot-contact",
        first_name=first_name,
        last_name=last_name,
        email=email,
        company=company,
    )

def create_hubspot_opportunity(dealname, dealstage, amount=None, company_id=None):
    """
    Create an opportunity in HubSpot.
    """
    return run(
        operation="hubspot-opportunity",
        dealname=dealname,
        dealstage=dealstage,
        amount=amount,
        company_id=company_id,
    )

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "hubspot-contact":
            create_hubspot_contact(
                first_name=sys.argv[2] if len(sys.argv) > 2 else "John",
                last_name=sys.argv[3] if len(sys.argv) > 3 else "Doe",
                email=sys.argv[4] if len(sys.argv) > 4 else "john.doe@example.com",
                company=sys.argv[5] if len(sys.argv) > 5 else "Acme Inc."
            )
        elif command == "hubspot-opportunity":
            create_hubspot_opportunity(
                dealname=sys.argv[2] if len(sys.argv) > 2 else "New Deal",
                dealstage=sys.argv[3] if len(sys.argv) > 3 else "appointmentscheduled",
                amount=sys.argv[4] if len(sys.argv) > 4 else "10000",
                company_id=sys.argv[5] if len(sys.argv) > 5 else None
            )
        elif command == "hubspot-all":
            run(
                operation="hubspot-all",
                first_name=sys.argv[2] if len(sys.argv) > 2 else "John",
                last_name=sys.argv[3] if len(sys.argv) > 3 else "Doe",
                email=sys.argv[4] if len(sys.argv) > 4 else "john.doe@example.com",
                company=sys.argv[5] if len(sys.argv) > 5 else "Acme Inc.",
                dealstage=sys.argv[6] if len(sys.argv) > 6 else "appointmentscheduled",
                amount=sys.argv[7] if len(sys.argv) > 7 else "10000"
            )
        else:
            print(f"Unknown command: {command}")
            print("Available commands: hubspot-contact, hubspot-opportunity, hubspot-all")
    else:
        print("Usage: python -m skill_registry_crew.main [command] [args...]")
        print("Available commands: ")
        print("  hubspot-contact [first_name] [last_name] [email] [company]")
        print("  hubspot-opportunity [dealname] [dealstage] [amount] [company_id]")
        print("  hubspot-all [first_name] [last_name] [email] [company] [dealstage] [amount]")