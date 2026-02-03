import os
import argparse
from core.backup import backup_project
from core.obfuscate import obfuscate_code, scan_global_definitions

def get_py_files(project_path):
    py_files = []
    for root, _, files in os.walk(project_path):
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))
    return py_files

def destroy(project_path):
    print(f"🔥 Starting destruction: {project_path}")
    backup_project(project_path) # 不需要则注释掉这行
    
    all_files = get_py_files(project_path)
    global_map = {}

    # 深度全局扫描
    print("Scanning for all definitions (Classes, Methods, Attributes)...")
    for path in all_files:
        try:
            with open(path, "r", encoding="utf-8") as fp:
                code = fp.read()
            # 这里的 scan 现在会递归查找类里的方法了
            defs = scan_global_definitions(code)
            global_map.update(defs)
        except Exception as e:
            print(f"  Skipping scan for {path}: {e}")
    
    print(f"  Collected {len(global_map)} global symbols.")

    #  执行一致性混淆
    print("Obfuscating content...")
    for path in all_files:
        try:
            with open(path, "r", encoding="utf-8") as fp:
                code = fp.read()
            
            # 传入 global_map，确保调用处也能正确改名
            new_code = obfuscate_code(code, global_map)
            
            with open(path, "w", encoding="utf-8") as fp:
                fp.write(new_code)
            
            print(f"  [Changed] {os.path.basename(path)}")
        except Exception as e:
            print(f"  [Error] {os.path.basename(path)}: {e}")

    print("✅ Project destroyed successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--project_path', type=str, required=True)
    args = parser.parse_args()
    
    if os.path.exists(args.project_path):
        destroy(args.project_path)
    else:
        print("Path not found.")