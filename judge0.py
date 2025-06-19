import json
import time
import requests

# Judge0 API configuration
JUDGE0_ENDPOINT = "https://judge0-ce.p.rapidapi.com/submissions"
HEADERS = {
    "Content-Type": "application/json",
    "X-RapidAPI-Key": "68ebceab75msha4531b3497020cdp1d32adjsn7ed41e077261",  # Replace with your API key
    "X-RapidAPI-Host": "judge0-ce.p.rapidapi.com"
}

LANGUAGE_IDS = {
    "python": 71,
    "java": 62,
    "javascript": 63,
    "cpp": 54,
}

def submit_code(source_code, language_id, stdin="", expected_output=""):
    """
    Submit code to the Judge0 API with properly formatted stdin and expected output.
    """
    if not isinstance(stdin, str):
        try:
            stdin = json.dumps(stdin)
        except Exception as e:
            print(f"Error converting stdin: {e}")
            stdin = str(stdin)
    
    expected_output = str(expected_output)

    payload = {
        "source_code": source_code,
        "language_id": language_id,
        "stdin": stdin,
        "expected_output": expected_output,
    }
    # Switch to synchronous mode to ensure the input is sent and processed immediately
    params = {"base64_encoded": "false", "wait": "true"}

    try:
        print("Submitting code to Judge0...")
        response = requests.post(JUDGE0_ENDPOINT, json=payload, headers=HEADERS, params=params)
        response.raise_for_status()
        response_data = response.json()
        token = response_data.get("token")
        if not token:
            raise Exception(f"Submission failed: {response_data}")
        return token
    except requests.exceptions.RequestException as e:
        print(f"Error submitting code to Judge0: {e}")
        raise Exception(f"Failed to submit code: {e}")

def get_result(token):
    """
    Poll the Judge0 API using the token until the result is ready.
    """
    params = {"base64_encoded": "false"}
    max_retries = 10
    retry_count = 0

    while retry_count < max_retries:
        try:
            print(f"Fetching result for token: {token}")
            result_response = requests.get(f"{JUDGE0_ENDPOINT}/{token}", headers=HEADERS, params=params)
            result_response.raise_for_status()
            result = result_response.json()
            print(f"Result from Judge0: {json.dumps(result, indent=2)}")

            status_id = result["status"]["id"]
            if status_id in [1, 2]:
                time.sleep(2)
                retry_count += 1
            else:
                return result
        except requests.exceptions.RequestException as e:
            print(f"Error fetching result from Judge0: {e}")
            retry_count += 1
            time.sleep(2)

    raise Exception(f"Failed to fetch result after {max_retries} retries")
