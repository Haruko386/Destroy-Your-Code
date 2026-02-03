# core/backup.py
import shutil
import os

def backup_project(project_path):
    backup_path = project_path + ".backup"
    if os.path.exists(backup_path):
        print("Backup already exists.")
        return
    shutil.copytree(project_path, backup_path)
    print("Backup created:", backup_path)