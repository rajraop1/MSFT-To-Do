import os
import argparse
import hashlib
import requests
import sqlite3
import subprocess
from datetime import datetime
from urllib.parse import quote

LOG_FILE = "onedrive_sync.log"


def log_request(url, status_code=None, count=None, cloud_hash=None, local_hash=None, sql=None):
    with open(LOG_FILE, "a") as log:
        timestamp = datetime.utcnow().isoformat()
        line = f"[{timestamp}] {url} - {status_code}"
        if count is not None:
            line += f" - Items fetched: {count}"
        if cloud_hash:
            line += f" - Cloud hash: {cloud_hash}"
        if local_hash:
            line += f" - Local hash: {local_hash}"
        if sql:
            line += f" - SQL: {sql}"
        log.write(line + "\n")


def read_token():
    try:
        with open(".token", "r") as f:
            token = f.read().strip()
        return token
    except Exception:
        raise RuntimeError("Token file (.token) not found or unreadable.")


def get_drive_items(token, item_id=None):
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    url = "https://graph.microsoft.com/v1.0/me/drive/root"
    if item_id:
        url = f"https://graph.microsoft.com/v1.0/me/drive/items/{item_id}/children"
    else:
        url += "/children"

    items = []
    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        items.extend(data['value'])
        log_request(url, response.status_code, len(data['value']))
        url = data.get('@odata.nextLink')
    return items


def get_cloud_hash(token, item_id):
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    url = f"https://graph.microsoft.com/v1.0/me/drive/items/{item_id}"
    response = requests.get(url, headers=headers)
    cloud_hash = None
    if response.status_code == 401:
        raise Exception("Unauthorized: Check your access token")
    if response.ok:
        item = response.json()
        cloud_hash = item.get('file', {}).get('hashes', {}).get('sha1Hash')
    log_request(url, response.status_code, cloud_hash=cloud_hash)
    response.raise_for_status()
    return cloud_hash


HASH_ALGORITHM = 'sha1Hash'
db_file = 'onedrive_sync.db'
download_dir = './downloaded_files'


def init_db():
    conn = sqlite3.connect(db_file , isolation_level=None)
    c = conn.cursor()
    sql = '''CREATE TABLE IF NOT EXISTS files (
                item TEXT PRIMARY KEY,
                item_type TEXT,
                cloud_hash TEXT,
                local_hash TEXT,
                downloaded_date TEXT,
                parent TEXT,
                item_id TEXT
            )'''
    c.execute(sql)
    log_request("init_db", 200, sql=sql)
    conn.commit()
    return conn


def compute_hash(filepath):
    try:
        result = subprocess.run(['sha1sum', filepath], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.split()[0]
    except Exception:
        pass
    hasher = hashlib.sha1()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def populate_db(conn, items, token, path_prefix='', parent=None):
    c = conn.cursor()
    for item in items:
        name = item['name']
        item_id = item['id']
        item_type = 'folder' if 'folder' in item else 'file'
        rel_path = os.path.join(path_prefix, name)

        c.execute("SELECT 1 FROM files WHERE item = ?", (rel_path,))
        if c.fetchone():
            continue

        cloud_hash = None
        sql = "INSERT OR IGNORE INTO files (item, item_type, cloud_hash, local_hash, downloaded_date, parent, item_id) VALUES (?, ?, ?, ?, ?, ?, ?)"
        c.execute(sql, (rel_path, item_type, cloud_hash, None, None, parent, item_id))
        log_request("populate_db", 200, sql=sql)

        if item_type == 'folder':
            c.execute("SELECT 1 FROM files WHERE parent = ? LIMIT 1", (rel_path,))
            if c.fetchone():
                log_request(f"SKIP folder already fetched: {rel_path}", 200, 0)
                continue
            sub_items = get_drive_items(token, item_id)
            populate_db(conn, sub_items, token, rel_path, parent=rel_path)
    conn.commit()


def refresh_file_list(conn, token):
    print("Refreshing file list from OneDrive...")
    items = get_drive_items(token)
    populate_db(conn, items, token)


def get_missing_cloud_hash(conn, token):
    c = conn.cursor()
    c.execute("SELECT item, item_id FROM files WHERE item_type = 'file' AND (cloud_hash IS NULL OR cloud_hash = '') AND item_id IS NOT NULL")
    rows = c.fetchall()
    for item, item_id in rows:
        try:
            cloud_hash = get_cloud_hash(token, item_id)
            sql = "UPDATE files SET cloud_hash = ? WHERE item = ?"
            c.execute(sql, (cloud_hash, item))
            log_request("get_missing_cloud_hash", 200, cloud_hash=cloud_hash, sql=sql)
        except Exception as e:
            log_request(f"get_missing_cloud_hash_failed_{item_id}", 500, cloud_hash="ERROR")
    conn.commit()


def update_cloud_hash(conn, token):
    c = conn.cursor()
    c.execute("SELECT item, item_id FROM files WHERE item_type = 'file' AND item_id IS NOT NULL")
    rows = c.fetchall()
    for item, item_id in rows:
        try:
            cloud_hash = get_cloud_hash(token, item_id)
            sql = "UPDATE files SET cloud_hash = ? WHERE item = ?"
            c.execute(sql, (cloud_hash, item))
            log_request("update_cloud_hash", 200, cloud_hash=cloud_hash, sql=sql)
        except Exception as e:
            log_request(f"update_cloud_hash_failed_{item_id}", 500, cloud_hash="ERROR")
    conn.commit()


def check_updates(conn, local_dir):
    c = conn.cursor()
    c.execute("SELECT item, cloud_hash, local_hash FROM files WHERE item_type = 'file'")
    mismatches = []
    for item, cloud_hash, local_hash in c.fetchall():
        if cloud_hash and local_hash and cloud_hash != local_hash:
            mismatches.append(item)
    print(f"Found {len(mismatches)} updated files.")
    for item in mismatches:
        print(f"UPDATE NEEDED: {item}")


def download_updates(conn, token, local_dir):
    c = conn.cursor()
    c.execute("SELECT item, item_id FROM files WHERE item_type = 'file' AND ( lower(cloud_hash) != lower(local_hash) or local_hash IS NULL ) ")
    updated = 0
    for item, item_id in c.fetchall():
      try:
        local_path = os.path.join(local_dir, item)
        print("File " + item,flush=True)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        url = f"https://graph.microsoft.com/v1.0/me/drive/items/{item_id}/content"
        response = requests.get(url, headers={'Authorization': f'Bearer {token}'})
        if response.ok:
            with open(local_path, 'wb') as f:
                f.write(response.content)
            downloaded_date = datetime.utcnow().isoformat()
            local_hash = compute_hash(local_path)
            sql = "UPDATE files SET downloaded_date = ?, local_hash = ? WHERE item = ?"
            c.execute(sql, (downloaded_date, local_hash, item))
            log_request(url, response.status_code, cloud_hash="UPDATED", local_hash=local_hash, sql=sql)
            updated += 1
        else:
            log_request(url, response.status_code )
      except Exception as e:
        print(f"Error: {e}")

    conn.commit()
    print(f"Downloaded and updated {updated} files.")


def sync_downloads(conn, token, local_dir):
    c = conn.cursor()
    c.execute("SELECT item, item_id FROM files WHERE item_type = 'file' AND downloaded_date IS NULL")
    downloaded = 0
    for item, item_id in c.fetchall():
        local_path = os.path.join(local_dir, item)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        url = f"https://graph.microsoft.com/v1.0/me/drive/items/{item_id}/content"
        response = requests.get(url, headers={'Authorization': f'Bearer {token}'})
        if response.ok:
            with open(local_path, 'wb') as f:
                f.write(response.content)
            downloaded_date = datetime.utcnow().isoformat()
            local_hash = compute_hash(local_path)
            sql = "UPDATE files SET downloaded_date = ?, local_hash = ? WHERE item = ?"
            c.execute(sql, (downloaded_date, local_hash, item))
            log_request(url, response.status_code, local_hash=local_hash, sql=sql)
            downloaded += 1
        else:
            log_request(url, response.status_code)

    conn.commit()
    print(f"Downloaded {downloaded} new files.")


def update_local_hash(conn, local_dir):
    c = conn.cursor()
    c.execute("SELECT item FROM files WHERE item_type = 'file'")
    updated = 0
    for (item,) in c.fetchall():
        local_path = os.path.join(local_dir, item)
        if os.path.exists(local_path):
            local_hash = compute_hash(local_path)
            sql = "UPDATE files SET local_hash = ? WHERE item = ?"
            c.execute(sql, (local_hash, item))
            log_request("update_local_hash", 200, local_hash=local_hash, sql=sql)
            updated += 1
    conn.commit()
    print(f"Updated local hash for {updated} files.")


def find_diff_summary(conn):
    c = conn.cursor()

    c.execute("""
        SELECT COUNT(*) FROM files
        WHERE item_type = 'file'
        AND cloud_hash IS NOT NULL AND cloud_hash != ''
        AND local_hash IS NOT NULL AND local_hash != ''
        AND lower(cloud_hash) = lower(local_hash)
    """)
    same = c.fetchone()[0]

    c.execute("""
        SELECT COUNT(*) FROM files
        WHERE item_type = 'file'
        AND cloud_hash IS NOT NULL AND cloud_hash != ''
        AND local_hash IS NOT NULL AND local_hash != ''
        AND lower(cloud_hash) != lower(local_hash)
    """)
    different = c.fetchone()[0]

    c.execute("""
        SELECT item FROM files
        WHERE item_type = 'file'
        AND (cloud_hash IS NULL OR cloud_hash = '')
    """)
    missing_cloud = [row[0] for row in c.fetchall()]

    c.execute("""
        SELECT item FROM files
        WHERE item_type = 'file'
        AND (local_hash IS NULL OR local_hash = '')
    """)
    missing_local = [row[0] for row in c.fetchall()]

    c.execute("""
        SELECT COUNT(*) FROM files
        WHERE item_type = 'file'
        AND cloud_hash IS NOT NULL AND cloud_hash != ''
        AND (local_hash IS NULL OR local_hash = '')
    """)
    cloud_only = c.fetchone()[0]

    c.execute("""
        SELECT COUNT(*) FROM files
        WHERE item_type = 'file'
        AND local_hash IS NOT NULL AND local_hash != ''
        AND (cloud_hash IS NULL OR cloud_hash = '')
    """)
    local_only = c.fetchone()[0]

    print("Summary of hash comparison:")
    print(f"  Same cloud/local hash: {same}")
    print(f"  Different cloud/local hash: {different}")
    print(f"  Files missing cloud hash ({len(missing_cloud)}):")
    print(f"  Files missing local hash ({len(missing_local)}):")
    print(f"  Cloud hash only : {cloud_only}")
    print(f"  Local hash only : {local_only}")


    #for item in missing_cloud:
        #print(f"    - {item}")
    #for item in missing_local:
        #print(f"    - {item}")

    log_request("summary", 200, count=same + different,
                sql=f"same={same}, different={different}, missing_cloud={len(missing_cloud)}, missing_local={len(missing_local)}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-check_updates', action='store_true')
    parser.add_argument('-download_updates', action='store_true')
    parser.add_argument('-refresh_list', action='store_true')
    parser.add_argument('-update_local_hash', action='store_true')
    parser.add_argument('-update_cloud_hash', action='store_true')
    parser.add_argument('-get_cloud_hash', action='store_true')
    parser.add_argument('-sync_all', action='store_true')
    parser.add_argument('-status', action='store_true')
    parser.add_argument('-local_dir', type=str, default='./downloaded_files')
    args = parser.parse_args()

    token = read_token()
    conn = init_db()
    download_dir = args.local_dir

    try:
        if args.refresh_list:
            refresh_file_list(conn, token)
        elif args.update_cloud_hash:
            print("Updating cloud hashes...")
            update_cloud_hash(conn, token)
        elif args.get_cloud_hash:
            print("Updating missing cloud hashes...")
            get_missing_cloud_hash(conn, token)
        elif args.check_updates:
            print("Checking for file updates...")
            check_updates(conn, download_dir)
        elif args.download_updates:
            print("Downloading updated files...")
            download_updates(conn, token, download_dir)
        elif args.update_local_hash:
            print("Updating local hashes for present files...")
            update_local_hash(conn, download_dir)
        elif args.status:
            print("Comparing cloud and local hashes...")
            find_diff_summary(conn)
        elif args.sync_all:
            print("Running full sync (refresh list, get cloud hash, update local hash, download updates)...")
            refresh_file_list(conn, token)
            get_missing_cloud_hash(conn, token)
            update_local_hash(conn, download_dir)
            download_updates(conn, token, download_dir)
        else:
            print("Performing initial file download...")
            sync_downloads(conn, token, download_dir)
    except Exception as e:
        print(f"Error: {e}")

    conn.close()
    log_request("done","")

