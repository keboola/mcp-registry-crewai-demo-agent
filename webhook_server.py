import os
import hmac
import hashlib
import json
import requests
from flask import Flask, request, jsonify

# --- Configuration ---
# Load secrets from environment variables for security
# You'll need to set these in your environment before running the app:
# export GITHUB_SECRET='your_github_webhook_secret'
# export KICKOFF_TOKEN='your_crewai_api_token'
# export KICKOFF_URL='https:/mcp-registry-crew-demo-feat-documentation-a.agentic.canary-orion.keboola.dev/kickoff' # Optional override
GITHUB_SECRET = os.environ.get("GITHUB_SECRET")
KICKOFF_TOKEN = os.environ.get("KICKOFF_TOKEN")
# Default Kickoff URL, can be overridden by environment variable
KICKOFF_URL = os.environ.get(
    "KICKOFF_URL",
    "https://mcp-registry-crew-demo-feat-documentation-a.agentic.canary-orion.keboola.dev/kickoff"
)
KICKOFF_CREW_NAME = "ComponentDocumentationCrew" # Or fetch from webhook/config if needed

# --- Flask App Initialization ---
app = Flask(__name__)

# --- Helper Functions ---

def verify_signature(payload_body, signature_header):
    """Verify that the payload was sent from GitHub by validating the signature."""
    if not signature_header:
        app.logger.warning("Signature header missing!")
        return False
    if not GITHUB_SECRET:
        app.logger.error("GITHUB_SECRET not configured. Cannot verify signature.")
        return False # Should ideally raise an error or halt

    hash_object = hmac.new(
        GITHUB_SECRET.encode('utf-8'),
        msg=payload_body,
        digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()

    if not hmac.compare_digest(expected_signature, signature_header):
        app.logger.warning(f"Signature mismatch. Expected: {expected_signature}, Got: {signature_header}")
        return False

    return True

def trigger_crew_kickoff(repo_url: str, ref: str, before: str, after: str):
    """Sends a POST request to the CrewAI kickoff endpoint with specific inputs."""
    if not KICKOFF_TOKEN:
        app.logger.error("KICKOFF_TOKEN is not set. Cannot trigger crew kickoff.")
        return False, "Kickoff token not configured on server."

    headers = {
        'accept': 'application/json',
        'Authorization': f'Bearer {KICKOFF_TOKEN}',
        'Content-Type': 'application/json'
    }
    # Include the specific details extracted from the webhook in the inputs
    payload = {
        "crew": KICKOFF_CREW_NAME,
        "inputs": {
            "repository_url": repo_url,
            "ref": ref,
            "before": before,
            "after": after,
            "verbose": True # Keep other necessary inputs
        },
        "wait": False # Set to true if you need the webhook to wait for completion
    }

    try:
        app.logger.info(f"Sending kickoff request to {KICKOFF_URL} for crew {KICKOFF_CREW_NAME} with inputs: {{ref: {ref}, before: {before[:7]}..., after: {after[:7]}..., repo: {repo_url}}}")
        response = requests.post(KICKOFF_URL, headers=headers, json=payload, timeout=30) # Added timeout
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        app.logger.info(f"Kickoff request successful. Status: {response.status_code}, Response: {response.text[:200]}...") # Log snippet of response
        return True, response.json()
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error triggering crew kickoff: {e}")
        error_details = f"Failed to trigger crew: {e}"
        if hasattr(e, 'response') and e.response is not None:
             error_details += f" | Status: {e.response.status_code} | Body: {e.response.text[:200]}..."
        return False, error_details
    except Exception as e:
        # Catch unexpected errors
        app.logger.exception(f"Unexpected error during crew kickoff: {e}")
        return False, f"An unexpected error occurred: {e}"


# --- Webhook Endpoint ---

@app.route('/', methods=['GET'])
def health_check():
    """Provides a simple health check endpoint."""
    app.logger.info("Received request on / (health check)")
    return jsonify({"status": "ok", "message": "Webhook server is running"}), 200

@app.route('/webhook', methods=['POST'])
def handle_github_webhook():
    """Handles incoming POST requests from GitHub webhooks."""
    app.logger.info("Received request on /webhook")

    # --- Security Verification ---
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_signature(request.data, signature):
        app.logger.warning("Webhook signature verification failed.")
        return jsonify({"status": "error", "message": "Invalid signature"}), 403

    # --- Event Type Check ---
    event_type = request.headers.get('X-GitHub-Event')
    app.logger.info(f"Received GitHub event: {event_type}")

    # --- Payload Parsing ---
    try:
        payload = request.json
        if not payload:
            app.logger.warning("Request payload is empty or not valid JSON.")
            return jsonify({"status": "error", "message": "Invalid JSON payload"}), 400
        # You can inspect the payload here to decide if you want to trigger the crew
        # For example, check the branch for push events, or action for pull_request events
        app.logger.debug(f"Webhook payload: {json.dumps(payload, indent=2)}") # Be careful logging full payloads
    except Exception as e:
         app.logger.error(f"Error parsing JSON payload: {e}")
         return jsonify({"status": "error", "message": "Could not parse JSON payload"}), 400


    # --- Trigger Logic (Example: Trigger on 'push' events) ---
    # Modify this logic based on which GitHub events should trigger the crew
    if event_type == 'push':
        # Extract necessary information for the crew
        try:
            ref = payload['ref']
            before_commit = payload['before']
            after_commit = payload['after']
            # Use html_url as it's usually present and user-friendly
            repo_url = payload['repository']['html_url']
            # Add check for non-zero commits
            if before_commit == '0000000000000000000000000000000000000000' or after_commit == '0000000000000000000000000000000000000000':
                app.logger.info(f"Ignoring push event for new/deleted branch ({ref}) with zero commit hash.")
                return jsonify({"status": "ignored", "message": "Ignoring push event for new/deleted branch."}), 200

            app.logger.info(f"Detected 'push' event on ref '{ref}'. Triggering crew kickoff for commits {before_commit[:7]}..{after_commit[:7]} in repo {repo_url}")

            success, result = trigger_crew_kickoff(
                repo_url=repo_url,
                ref=ref,
                before=before_commit,
                after=after_commit
            )

            if success:
                return jsonify({"status": "success", "message": "Crew kickoff triggered", "kickoff_response": result}), 200
            else:
                return jsonify({"status": "error", "message": "Failed to trigger crew kickoff", "details": result}), 500
        except KeyError as e:
            app.logger.error(f"Missing expected key in 'push' event payload: {e}")
            return jsonify({"status": "error", "message": f"Invalid 'push' payload structure, missing key: {e}"}), 400
        except Exception as e:
            # Catch unexpected errors during extraction or triggering
            app.logger.exception(f"Unexpected error processing 'push' event: {e}")
            return jsonify({"status": "error", "message": f"An unexpected error occurred: {e}"}), 500
    elif event_type == 'ping':
         # GitHub sends a 'ping' event when you first set up the webhook
         app.logger.info("Received 'ping' event. Webhook configured successfully.")
         return jsonify({"status": "success", "message": "Webhook received ping event successfully."}), 200
    else:
        # You might want to handle other event types or ignore them
        app.logger.info(f"Ignoring event type: {event_type}")
        return jsonify({"status": "ignored", "message": f"Event type '{event_type}' not configured for trigger."}), 200


# --- Main Execution ---
if __name__ == '__main__':
    # Use 0.0.0.0 to make it accessible on your network
    # Change port if 5000 is already in use
    # Set debug=False for production environments
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8888)) # Use a different port than default 5000 if needed
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(host=host, port=port, debug=debug_mode) 