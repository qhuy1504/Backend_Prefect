# prefect_service.py
import os
import requests
from flask import jsonify
from dotenv import load_dotenv
load_dotenv()

PREFECT_API_URL = os.getenv("PREFECT_API_URL")
print("PREFECT_API_URL:", PREFECT_API_URL)


def upsert_concurrency_limit_for_tag(tag, concurrency_value):
    delete_endpoint = f"{PREFECT_API_URL}/concurrency_limits/tag/{tag}"
    create_endpoint = f"{PREFECT_API_URL}/concurrency_limits/"

    try:
        requests.delete(delete_endpoint)
    except requests.exceptions.RequestException as e:
        if e.response and e.response.status_code != 404:
            raise

    payload = {
        "tag": tag,
        "concurrency_limit": concurrency_value
    }
    response = requests.post(create_endpoint, json=payload)
    response.raise_for_status()
    return response.json()


def trigger_prefect_flow(deployment_id, parameters=None, tags=None):
    if not deployment_id:
        raise ValueError("Deployment ID is required")

    url = f"{PREFECT_API_URL}/deployments/{deployment_id}/create_flow_run"
    body = {}
    if parameters:
        body["parameters"] = parameters
    if tags:
        body["tags"] = tags

    response = requests.post(url, json=body)
    response.raise_for_status()
    return response.json()


def get_flow_run_state(flow_run_id):
    endpoint = f"{PREFECT_API_URL}/flow_runs/{flow_run_id}"
    response = requests.get(endpoint)
    response.raise_for_status()
    return response.json()


def get_flow_run_logs(flow_run_id):
    endpoint = f"{PREFECT_API_URL}/flow_runs/{flow_run_id}/logs"
    try:
        response = requests.post(endpoint, json={})
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return []


def upsert_variable(name, value):
    filter_endpoint = f"{PREFECT_API_URL}/variables/filter"
    response = requests.post(filter_endpoint, json={"name": {"any_": [name]}, "limit": 100})
    response.raise_for_status()
    found = response.json()

    match = next((v for v in found if v["name"] == name), None)
    if match:
        patch_url = f"{PREFECT_API_URL}/variables/{match['id']}"
        requests.patch(patch_url, json={"value": value})
        return match['id']

    create_url = f"{PREFECT_API_URL}/variables/"
    create_response = requests.post(create_url, json={"name": name, "value": value})
    create_response.raise_for_status()
    return create_response.json()['id']
