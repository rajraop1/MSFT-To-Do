import requests
import pandas as pd
from openpyxl import Workbook, load_workbook
import json
import argparse
import sys

def log_request(url, status_code, response_text):
    """Logs API requests with their status codes and responses to a log file."""
    with open("request_log.txt", "a") as log_file:
        log_file.write(f"URL: {url} | Status: {status_code} | Response: {response_text}\n")

def get_todo_data(token_file):
    """Fetches all tasks from Microsoft To Do including checklist items (steps), excluding status, with progress updates."""
    try:
        with open(token_file, 'r') as file:
            token = file.read().strip()
    except FileNotFoundError:
        raise Exception("Token file not found.")
    
    headers = {"Authorization": f"Bearer {token}"}
    lists_url = "https://graph.microsoft.com/v1.0/me/todo/lists"
    response = requests.get(lists_url, headers=headers)
    log_request(lists_url, response.status_code, response.text)
    
    if response.status_code != 200:
        raise Exception(f"Error fetching lists: {response.text}")
    
    lists = response.json().get("value", [])
    data = []
    total_lists = len(lists)
    
    for index, lst in enumerate(lists, start=1):
        list_name = lst.get('displayName', 'Unnamed List')
        list_id = lst.get('id', '')
        data.append((list_name, "", ""))  # List level
        
        tasks_url = f"https://graph.microsoft.com/v1.0/me/todo/lists/{list_id}/tasks"
        task_response = requests.get(tasks_url, headers=headers)
        log_request(tasks_url, task_response.status_code, task_response.text)
        
        if task_response.status_code != 200:
            continue
        
        tasks = task_response.json().get("value", [])
        total_tasks = len(tasks)
        
        for task_index, task in enumerate(tasks, start=1):
            task_name = task.get('title', 'Unnamed Task')
            steps_text = ""
            task_id = task.get('id', '')
            
            if task_id:
                checklist_url = f"https://graph.microsoft.com/v1.0/me/todo/lists/{list_id}/tasks/{task_id}/checklistItems"
                checklist_response = requests.get(checklist_url, headers=headers)
                log_request(checklist_url, checklist_response.status_code, checklist_response.text)
                
                if checklist_response.status_code == 200:
                    checklist_items = checklist_response.json().get("value", [])
                    if checklist_items:
                        steps_text = ", ".join([step.get('displayName', 'Unnamed Step') for step in checklist_items if 'displayName' in step])
                    else:
                        #steps_text = "No steps available"
                        steps_text = ""
                else:
                    steps_text = f"Error fetching steps: {checklist_response.status_code} {checklist_response.text}"
            
            data.append(("", task_name, steps_text))  # Task with checklist items in column 3
            
            # Print progress update dynamically
            sys.stdout.write(f"\rProcessing list {index}/{total_lists}, task {task_index}/{total_tasks} completed  ")
            sys.stdout.flush()
    
    print("\nData retrieval completed.")
    return data

def export_to_excel(data, filename):
    """Exports the structured data to an Excel file."""
    try:
        df = pd.DataFrame(data, columns=["List", "Task", "Steps"])
        with pd.ExcelWriter(filename, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="ToDo", index=False)
    except Exception as e:
        raise Exception(f"Error exporting to Excel: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="Microsoft To Do Import/Export Tool")
    parser.add_argument("action", choices=["import"], help="Action to perform")
    parser.add_argument("--file", required=True, help="Excel filename")
    parser.add_argument("--token", required=True, help="Token filename")
    
    args = parser.parse_args()
    
    try:
        if args.action == "import":
            data = get_todo_data(args.token)
            export_to_excel(data, args.file)
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()

