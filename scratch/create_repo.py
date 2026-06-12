import os
import requests
import sys

def create_github_repo():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        # Check if it's in keeper/.env
        try:
            with open("keeper/.env", "r") as f:
                for line in f:
                    if line.startswith("GITHUB_TOKEN="):
                        token = line.strip().split("=")[1]
                        break
        except Exception:
            pass

    if not token:
        print("ERROR: GITHUB_TOKEN not found.")
        sys.exit(1)

    url = "https://api.github.com/user/repos"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {
        "name": "alm-vault-dapp",
        "private": False
    }

    print("Sending request to GitHub API...")
    response = requests.post(url, headers=headers, json=data)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")

    if response.status_code == 401:
        print("CRITICAL ERROR: 401 Unauthorized. Invalid GITHUB_TOKEN.")
        sys.exit(1)
        
    try:
        resp_json = response.json()
    except Exception:
        print("CRITICAL ERROR: Failed to parse JSON response.")
        sys.exit(1)

    if "id" not in resp_json:
        if "errors" in resp_json or response.status_code != 201:
            print("CRITICAL ERROR: Repo creation failed or already exists but no ID returned.")
            sys.exit(1)

    print("Repository successfully created or validated.")

if __name__ == "__main__":
    create_github_repo()
