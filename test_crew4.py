#!/usr/bin/env python
import os
import random
import logging
import yaml # Need to import yaml
import requests # Added requests
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import BaseTool # Added BaseTool
# from langchain_openai import ChatOpenAI # Or your preferred LLM

# Ensure API key is set (replace with your actual key management)
# if not os.environ.get("OPENAI_API_KEY"):
#     raise ValueError("OPENAI_API_KEY is not set.")

# --- Default Configurations ---
DEFAULT_AGENTS_CONFIG = {
    'sales_agent': {
        'role': 'Sales Analyst',
        'goal': 'Analyze messages and provide sales-focused responses',
        'backstory': 'An expert in understanding customer needs from brief messages.'
    }
}

DEFAULT_TASKS_CONFIG = {
    'sales_task': {
        'description': 'Analyze the provided message and generate a response.', # Base description, will be overridden
        'expected_output': 'A sales-oriented response string.'
    }
}

# --- Function to Load Config Files ---
def load_config(config_path, default_config):
    """Loads YAML config file or returns default."""
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logging.warning(f"Failed to load or parse {config_path}: {e}. Using default config.")
            return default_config
    else:
        # Use the warning from CrewAI's perspective if file not found
        # logging.warning(f"Config file not found at {config_path}. Using default config.")
        return default_config

# --- Crew Definition ---

@CrewBase
class SalesCrew:
    """
    A crew designed to process incoming messages (e.g., from Slack)
    and generate appropriate sales-related responses.
    """
    # Determine config paths relative to this script file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    agents_config_path = os.path.join(script_dir, 'config', 'agents.yaml')
    tasks_config_path = os.path.join(script_dir, 'config', 'tasks.yaml')

    # Load configs or use defaults
    agents_config = load_config(agents_config_path, DEFAULT_AGENTS_CONFIG)
    tasks_config = load_config(tasks_config_path, DEFAULT_TASKS_CONFIG)


    def __init__(self, inputs=None):
        """
        Initializes the SalesCrew.
        Args:
            inputs (dict): Inputs passed during crew kickoff, expected
                           to contain {'message': 'slack_message_content'}.
        """
        slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        if not slack_webhook_url:
            raise EnvironmentError("SLACK_WEBHOOK_URL not found in the environment variables")

        self.slack_webhook_url = slack_webhook_url
        self.inputs = inputs or {}
        # You might initialize LLMs or tools here if needed globally
        # self.llm = ChatOpenAI(model="gpt-4-turbo") # Example

    @agent
    def sales_responder_agent(self) -> Agent:
        """
        Agent responsible for analyzing incoming messages, crafting
        sales-oriented replies, and posting them to Slack.
        """
        # Instantiate the Slack tool
        slack_tool = SlackPostTool(webhook_url=self.slack_webhook_url)

        # Ensure 'sales_agent' key exists before accessing
        agent_conf = self.agents_config.get('sales_agent', DEFAULT_AGENTS_CONFIG['sales_agent'])
        return Agent(
            config=agent_conf,
            # llm=self.llm, # Uncomment if using a specific LLM instance
            verbose=True,
            allow_delegation=False, # Keep it simple for this example
            tools=[slack_tool] # Add the slack tool here
        )

    @task
    def analyze_and_respond_task(self) -> Task:
        """
        Task for analyzing the input message, generating one of three
        pre-defined response types, and posting the result to Slack.
        """
        # Define the possible response templates
        response_templates = {
            "revenue_update": "Based on '{initial_message}', our analysis suggests your business is currently tracking towards a 15% increase in annual revenue. We can explore strategies to accelerate this further.",
            "sales_pitch": "Thanks for reaching out about '{initial_message}'. Our solution can directly address this by [mention relevant feature/benefit]. Would you be open to a quick chat next week?",
            "deep_research": "Understood. Regarding '{initial_message}', I will initiate a deep dive analysis into [mention specific area, e.g., market trends, competitor actions] relevant to this. I'll prepare a brief summarizing key findings and strategic recommendations."
        }

        # Simple logic to pick a response type (replace with LLM decision if needed)
        chosen_response_type = random.choice(list(response_templates.keys()))

        # Get the input message safely
        # Note: We are using the key 'message' which slack_app.py should be sending
        input_message = self.inputs.get('message', 'No message provided.')

        # Construct the task description dynamically
        task_description = f"""
Analyze the incoming message: "{input_message}"

1.  **Generate Response:** Based on your analysis, generate a response using the following format and guidance:
    - Response Format Chosen: {chosen_response_type}
    - Guidance:
        - If 'revenue_update': Provide a generic positive revenue outlook, mentioning the original message for context.
        - If 'sales_pitch': Craft a concise sales pitch relevant to the message, suggesting a follow-up.
        - If 'deep_research': Acknowledge the message and state that a detailed research task will be performed, mentioning the message topic.
    - Use the template for '{chosen_response_type}':
        "{response_templates[chosen_response_type]}"
    - Ensure you replace '{{initial_message}}' with the actual message content: "{input_message}".
    - If the message is complex, focus on the core request or topic for the placeholder.

2.  **Post to Slack:** Once you have generated the final response string (and *only* the response string), use the 'post_to_slack_tool' to send this exact string as a message to Slack.

Your final output for the entire task should be a confirmation message indicating the response was posted to Slack (e.g., "Response posted to Slack.").
"""
        # Ensure 'sales_task' key exists before accessing
        task_conf = self.tasks_config.get('sales_task', DEFAULT_TASKS_CONFIG['sales_task'])
        return Task(
            config=task_conf,
            description=task_description, # Pass the dynamic description
            agent=self.sales_responder_agent(),
            # Update expected output to reflect the action taken
            expected_output="A confirmation message stating that the generated sales response has been successfully posted to Slack using the provided tool."
        )

    @crew
    def sales_analysis_crew(self) -> Crew:
        """
        Assembles the Sales Crew.
        """
        return Crew(
            agents=[self.sales_responder_agent()],
            tasks=[self.analyze_and_respond_task()],
            process=Process.sequential,
            verbose=True
        )

class SlackPostTool(BaseTool):
    name: str = "post_to_slack_tool"
    description: str = """
    Post a message to a Slack channel using a webhook URL.

    Args:
        message (str): The message to post to Slack

    Returns:
        str: Confirmation message
    """
    webhook_url: str

    def _run(self, message: str) -> str:
        try:
            # Use the internal post_to_slack function
            return post_to_slack(message, self.webhook_url)
        except Exception as e:
            # Provide more specific error feedback
            logging.error(f"SlackPostTool error: {e}")
            return f"Error posting to Slack: {str(e)}"

def post_to_slack(message: str, webhook_url: str) -> str:
    """
    Post a message to Slack using a webhook URL.

    Args:
        message: The text to post to Slack
        webhook_url: The Slack webhook URL

    Returns:
        A confirmation message
    """
    if not webhook_url:
        raise ValueError("Missing Slack webhook URL.")

    payload = {"text": message}
    response = requests.post(webhook_url, json=payload)
    response.raise_for_status()
    return "Report successfully posted to Slack."

# --- Example Usage (Simulating receiving a POST request) ---

if __name__ == "__main__":
    print("## Sales Crew Example Simulation")
    logging.basicConfig(level=logging.INFO) # Add basic logging for local run

    # Simulate the input received from the web server after a Slack message
    simulated_inputs = {
        # --- Try changing this message! ---
        "message": "Can you tell me more about your integration capabilities with Salesforce? \"Special\" chars included."
        # ---
    }

    print(f"\nSimulating kickoff with inputs: {simulated_inputs}")

    try:
        # Instantiate the crew with the simulated inputs
        sales_crew_instance = SalesCrew(inputs=simulated_inputs)

        # Kick off the crew process
        # Pass inputs again if kickoff requires them (depends on CrewAI version/setup)
        result = sales_crew_instance.sales_analysis_crew().kickoff(inputs=simulated_inputs)

        print("\n\n########################")
        print("## Crew Final Result:")
        print("########################")
        print(result)

    except ValueError as e:
        print(f"\nError initializing or running crew: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        # import traceback
        # traceback.print_exc() # Uncomment for detailed debugging

    print("\nNote: This script simulates the CrewAI part.")
    print("A separate web server (e.g., using Flask or FastAPI) is needed to:")
    print("1. Receive POST requests from Slack (via Event Subscriptions).")
    print("2. Parse the message.")
    print("3. Instantiate and kickoff this SalesCrew.")
    print("4. Potentially send the result back to Slack.") 