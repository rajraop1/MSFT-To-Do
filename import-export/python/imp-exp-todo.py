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

def export_to_json(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"Data exported to {filename}")

def import_from_json(access_token, filename):
    with open(filename, "r", encoding="utf-8") as f:
        todo_data = json.load(f)
    
    url = "https://graph.microsoft.com/v1.0/me/todo/lists"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    
    for todo_list in todo_data.get("value", []):
        list_name = todo_list["displayName"]
        payload = {"displayName": list_name}
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 201:
            new_list_id = response.json()["id"]
            print(f"Imported list: {list_name}")
            
            for task in todo_list.get("tasks", []):
                import_task(access_token, new_list_id, task)
        else:
            print(f"Error importing {list_name}: {response.status_code}, {response.text}")

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
    parser = argparse.ArgumentParser(description="Export or import Microsoft To-Do lists and tasks.")
    parser.add_argument("action", choices=["export", "import"], help="Action to perform: export or import")
    parser.add_argument("filename", help="Filename to export to or import from")
    args = parser.parse_args()
    
    token = get_access_token()
    
    if args.action == "export":
        todo_data = fetch_todo_lists(token)
        if todo_data:
            export_to_json(todo_data, args.filename)
    elif args.action == "import":
        import_from_json(token, args.filename)

if __name__ == "__main__":
    main()

