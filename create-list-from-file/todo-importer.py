import requests
import openpyxl
import os
import argparse
import logging
import sys

# Setup logging
logging.basicConfig(filename='logfile.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')

GRAPH_ROOT = 'https://graph.microsoft.com/v1.0/me/todo/lists'

# Read token from file
def read_token(token_file='token'):
    try:
        with open(token_file, 'r') as f:
            token = f.read().strip()
        logging.debug("Token read successfully.")
        return token
    except Exception as e:
        logging.error(f"Failed to read token: {e}")
        sys.exit(1)

# Get existing To Do lists
def get_todo_lists(headers):
    url = GRAPH_ROOT
    try:
        logging.debug(f"GET {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        lists = response.json().get('value', [])
        logging.debug(f"Fetched {len(lists)} existing lists from {url}. Status: {response.status_code}")
        return lists
    except Exception as e:
        logging.error(f"Failed to fetch To Do lists from {url}: {e}")
        return []

# Create a new list
def create_list(list_name, headers):
    url = GRAPH_ROOT
    try:
        payload = {"displayName": list_name}
        logging.debug(f"POST {url} with payload {payload}")
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        logging.debug(f"Created list '{list_name}' at {url}. Status: {response.status_code}")
        return response.json()
    except Exception as e:
        logging.error(f"Failed to create list '{list_name}' at {url}: {e}")
        return None

# Get tasks for a given list
def get_tasks(list_id, headers):
    url = f"{GRAPH_ROOT}/{list_id}/tasks"
    try:
        logging.debug(f"GET {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        tasks = response.json().get('value', [])
        logging.debug(f"Fetched {len(tasks)} tasks for list ID {list_id} from {url}. Status: {response.status_code}")
        return tasks
    except Exception as e:
        logging.error(f"Failed to fetch tasks for list {list_id} from {url}: {e}")
        return []

# Create a new task
def create_task(list_id, task_name, headers):
    url = f"{GRAPH_ROOT}/{list_id}/tasks"
    try:
        payload = {"title": task_name}
        logging.debug(f"POST {url} with payload {payload}")
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        logging.debug(f"Created task '{task_name}' at {url}. Status: {response.status_code}")
        return response.json()
    except Exception as e:
        logging.error(f"Failed to create task '{task_name}' at {url}: {e}")
        return None

# Get steps for a given task
def get_steps(list_id, task_id, headers):
    url = f"{GRAPH_ROOT}/{list_id}/tasks/{task_id}/checklistItems"
    try:
        logging.debug(f"GET {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        steps = response.json().get('value', [])
        logging.debug(f"Fetched {len(steps)} steps for task ID {task_id} from {url}. Status: {response.status_code}")
        return steps
    except Exception as e:
        logging.error(f"Failed to fetch steps for task {task_id} from {url}: {e}")
        return []

# Create a new step
def create_step(list_id, task_id, step_name, headers):
    url = f"{GRAPH_ROOT}/{list_id}/tasks/{task_id}/checklistItems"
    try:
        payload = {"displayName": step_name}
        logging.debug(f"POST {url} with payload {payload}")
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        logging.debug(f"Created step '{step_name}' at {url}. Status: {response.status_code}")
        return response.json()
    except Exception as e:
        logging.error(f"Failed to create step '{step_name}' at {url}: {e}")
        return None

# Main processing function
def process_xlsx(file_path, token):
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    # Extract list name from file
    list_name = os.path.splitext(os.path.basename(file_path))[0]
    logging.debug(f"Processing list: {list_name}")

    lists = get_todo_lists(headers)
    list_obj = next((lst for lst in lists if lst['displayName'] == list_name), None)

    if not list_obj:
        list_obj = create_list(list_name, headers)
        if not list_obj:
            logging.error("Exiting due to list creation failure.")
            return
    list_id = list_obj['id']

    tasks = get_tasks(list_id, headers)
    task_titles = {task['title']: task for task in tasks}

    wb = openpyxl.load_workbook(file_path)
    ws = wb.active

    tasks_created = 0
    steps_created = 0

    for row in ws.iter_rows(min_row=2, values_only=True):
        task_name, step_name = row

        if not task_name:
            continue

        # Create task if not exists
        if task_name not in task_titles:
            task_obj = create_task(list_id, task_name, headers)
            if not task_obj:
                continue
            task_titles[task_name] = task_obj
            tasks_created += 1
        task_id = task_titles[task_name]['id']

        # Fetch steps
        steps = get_steps(list_id, task_id, headers)
        step_names = [step['displayName'] for step in steps]

        # Create step if not exists
        if step_name and step_name not in step_names:
            if create_step(list_id, task_id, step_name, headers):
                steps_created += 1

    # Summary
    logging.info(f"Summary: Lists: 1, Tasks Created: {tasks_created}, Steps Created: {steps_created}")
    print(f"✅ Done. Lists: 1, Tasks Created: {tasks_created}, Steps Created: {steps_created}")

# Argument parsing
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Import tasks and steps into Microsoft To Do.')
    parser.add_argument('-list_file', required=True, help='Excel file with tasks and steps.')
    args = parser.parse_args()

    token = read_token()
    process_xlsx(args.list_file, token)

