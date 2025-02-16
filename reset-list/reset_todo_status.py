import requests
import json
import argparse

def get_access_token():
    try:
        with open("token.txt", "r", encoding="utf-8") as file:
            return file.read().strip()
    except FileNotFoundError:
        print("Error: Token file 'token.txt' not found. Please create the file and add your OAuth2 token.")
        exit(1)

def fetch_tasks(access_token, list_id):
    url = f"https://graph.microsoft.com/v1.0/me/todo/lists/{list_id}/tasks"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("value", [])
    else:
        print(f"Error fetching tasks for list {list_id}: {response.status_code}, {response.text}")
        return []

def update_task_status(access_token, task_id, list_id):
    url = f"https://graph.microsoft.com/v1.0/me/todo/lists/{list_id}/tasks/{task_id}"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {"status": "notStarted"}
    response = requests.patch(url, headers=headers, json=payload)
    if response.status_code == 200:
        print(f"Updated task {task_id} to 'notStarted'")
    else:
        print(f"Error updating task {task_id}: {response.status_code}, {response.text}")

def reset_list_tasks(access_token, list_name):
    url = "https://graph.microsoft.com/v1.0/me/todo/lists"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Error fetching lists: {response.status_code}, {response.text}")
        return
    
    lists = response.json().get("value", [])
    list_id = None
    for todo_list in lists:
        if todo_list["displayName"] == list_name:
            list_id = todo_list["id"]
            break
    
    if not list_id:
        print(f"Error: List '{list_name}' not found.")
        return
    
    tasks = fetch_tasks(access_token, list_id)
    for task in tasks:
        update_task_status(access_token, task["id"], list_id)

def main():
    parser = argparse.ArgumentParser(description="Reset all tasks in a Microsoft To-Do list to 'Not Completed'")
    parser.add_argument("list_name", help="The name of the list to reset")
    args = parser.parse_args()
    
    token = get_access_token()
    reset_list_tasks(token, args.list_name)

if __name__ == "__main__":
    main()

