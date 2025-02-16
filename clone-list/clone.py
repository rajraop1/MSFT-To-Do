import requests
import json
import argparse
import copy

def get_access_token():
    try:
        with open("token.txt", "r", encoding="utf-8") as file:
            return file.read().strip()
    except FileNotFoundError:
        print("Error: Token file 'token.txt' not found. Please create the file and add your OAuth2 token.")
        exit(1)

def fetch_todo_lists(access_token):
    url = "https://graph.microsoft.com/v1.0/me/todo/lists"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        lists = response.json()
        for todo_list in lists.get("value", []):
            list_id = todo_list["id"]
            todo_list["tasks"] = fetch_tasks(access_token, list_id)
        return lists
    else:
        print(f"Error fetching lists: {response.status_code}, {response.text}")
        return None

def fetch_tasks(access_token, list_id):
    url = f"https://graph.microsoft.com/v1.0/me/todo/lists/{list_id}/tasks"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("value", [])
    else:
        print(f"Error fetching tasks for list {list_id}: {response.status_code}, {response.text}")
        return []

def clone_todo_list(access_token, filename, source_list_name, new_list_name):
    with open(filename, "r", encoding="utf-8") as f:
        todo_data = json.load(f)
    
    cloned_list = None
    for todo_list in todo_data.get("value", []):
        if todo_list["displayName"] == source_list_name:
            cloned_list = copy.deepcopy(todo_list)
            break
    
    if not cloned_list:
        print(f"Error: Source list '{source_list_name}' not found.")
        return
    
    # Create new list in Microsoft To-Do
    url = "https://graph.microsoft.com/v1.0/me/todo/lists"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {"displayName": new_list_name}
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 201:
        new_list_id = response.json()["id"]
        print(f"Cloned list created: {new_list_name}")
        
        # Copy tasks to new list
        for task in cloned_list.get("tasks", []):
            import_task(access_token, new_list_id, task)
    else:
        print(f"Error creating list {new_list_name}: {response.status_code}, {response.text}")

def import_task(access_token, list_id, task):
    url = f"https://graph.microsoft.com/v1.0/me/todo/lists/{list_id}/tasks"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {
        "title": task["title"],
        "status": task.get("status", "notStarted"),
        "dueDateTime": task.get("dueDateTime"),
        "body": {"content": task.get("body", {}).get("content", ""), "contentType": "text"}
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 201:
        print(f"Imported task: {task['title']}")
    else:
        print(f"Error importing task {task['title']}: {response.status_code}, {response.text}")

def main():
    parser = argparse.ArgumentParser(description="Clone a Microsoft To-Do list and push it to Microsoft To-Do.")
    parser.add_argument("filename", help="Filename containing exported To-Do lists")
    parser.add_argument("source_list_name", help="The name of the list to clone")
    parser.add_argument("new_list_name", help="The name for the new cloned list")
    args = parser.parse_args()
    
    token = get_access_token()
    clone_todo_list(token, args.filename, args.source_list_name, args.new_list_name)

if __name__ == "__main__":
    main()

