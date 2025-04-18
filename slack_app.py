#!/usr/bin/env python
import os
import logging
import threading
import traceback
import requests
from flask import Flask, request, jsonify, Response

# --- Configuration ---
# Set up basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Crew Kickoff Configuration
KICKOFF_URL = os.environ.get(
    "KICKOFF_URL",
)
KICKOFF_CREW_NAME = "SalesCrew"  # As requested
KICKOFF_TOKEN = os.environ.get("KICKOFF_TOKEN")  # Get token from environment

allowed_channels = ["C08NA2E9T0W"]
# --- Flask App Initialization ---
app = Flask(__name__)


# --- Crew Kickoff Function (for background thread) ---
def run_crew_async(slack_message_text: str):
    """Sends a POST request to the CrewAI kickoff endpoint in a background thread."""
    if not KICKOFF_TOKEN:
        logging.error(
            "KICKOFF_TOKEN environment variable not set. Cannot trigger crew kickoff."
        )
        return
    if not KICKOFF_URL:
        logging.error("KICKOFF_URL is not configured. Cannot trigger crew kickoff.")
        return

    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {KICKOFF_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "crew": KICKOFF_CREW_NAME,
        "inputs": {
            "initial_message": slack_message_text,  # Pass the message text
            "verbose": True,
        },
        "wait": False,  # Crucial for background processing
    }

    try:
        logging.info(
            f"Sending kickoff request to {KICKOFF_URL} for crew '{KICKOFF_CREW_NAME}' with Slack message input."
        )
        response = requests.post(KICKOFF_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        logging.info(
            f"Kickoff request successful for crew '{KICKOFF_CREW_NAME}'. Status: {response.status_code}"
        )
        # Optional: Log parts of the response if needed, e.g., run ID
        # logging.debug(f"Kickoff response: {response.json()}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error triggering crew kickoff for '{KICKOFF_CREW_NAME}': {e}")
        error_details = f"Failed to trigger crew: {e}"
        if hasattr(e, "response") and e.response is not None:
            error_details += f" | Status: {e.response.status_code} | Body: {e.response.text[:200]}..."
        logging.error(error_details)
    except Exception as e:
        # Catch unexpected errors during kickoff
        logging.exception(
            f"Unexpected error during crew kickoff for '{KICKOFF_CREW_NAME}': {e}"
        )


# --- Slack Event Endpoint ---
@app.route("/slack/events", methods=["POST"])
def slack_events():
    """
    Handles incoming requests from Slack's Event Subscriptions.
    """
    # 1. Handle URL Verification Challenge
    if request.is_json and request.json.get("type") == "url_verification":
        challenge = request.json.get("challenge")
        if challenge:
            logging.info("Received Slack URL verification challenge.")
            return jsonify({"challenge": challenge})
        else:
            logging.error("URL verification challenge missing.")
            return "Challenge missing", 400

    # 2. Basic Request Validation (Add Signature Verification in Production!)
    if not request.is_json:
        logging.warning("Received non-JSON request")
        return "Request must be JSON", 400

    payload = request.json
    event_type = payload.get("type")

    # 3. Handle Event Callbacks
    if event_type == "event_callback":
        event = payload.get("event", {})
        message_type = event.get("type")
        text = event.get("text")
        user = event.get("user")  # Get user ID to potentially ignore bot messages
        bot_id = event.get("bot_id")  # Check if the message is from a bot

        if payload.get("channel") in allowed_channels:
            # Process only user messages (ignore bot messages)
            if message_type == "message" and text and not bot_id:
                logging.info(f"Received message from user {user}: '{text[:50]}...'")

                # --- CRITICAL: Respond immediately and run crew in background ---
                # Start the crew kickoff in a separate thread
                thread = threading.Thread(target=run_crew_async, args=(text,))
                thread.start()

                # Acknowledge Slack immediately within 3 seconds
                logging.info("Acknowledged Slack event, processing in background.")
                return Response(status=200)
            else:
                # Acknowledge other message subtypes or events without processing
                logging.debug(f"Ignoring event type: {message_type} or bot message.")
                return Response(status=200)

    # 4. Handle other payload types if necessary
    logging.warning(f"Received unhandled payload type: {event_type}")
    return "Unhandled event type", 400  # Or 200 if you want to ignore silently


# --- Run Flask App ---
if __name__ == "__main__":
    # Note: Use a production WSGI server like Gunicorn or uWSGI for deployment
    logging.info("Starting Flask server for Slack events...")
    app.run(
        host="0.0.0.0", port=int(os.environ.get("PORT", 8888)), debug=False
    )  # Use port 3000 if PORT env var not set
