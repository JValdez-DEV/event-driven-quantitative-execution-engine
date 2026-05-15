import os
import requests
from dotenv import load_dotenv

# Load the environment variables from your droplet
load_dotenv()

def run_communication_audit():
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    
    if not webhook_url:
        print("[!] ERROR: DISCORD_WEBHOOK_URL not found in .env file.")
        return

    payload = {
        "username": "Trade Hunter Audit",
        "content": "⚠️ **V3.6 Communication Audit: SUCCESSFUL**\nEnvironment Link: Verified\nSource: DigitalOcean Droplet"
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code == 204:
            print("[+] Success: Test notification sent to Discord.")
        else:
            print(f"[!] Failed: Discord returned status code {response.status_code}")
    except Exception as e:
        print(f"[!] Critical Error: {str(e)}")

if __name__ == "__main__":
    run_communication_audit()

