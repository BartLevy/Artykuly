import os, sys, json

def load_json_file(file_name, default = None):
    try:
        with open(file_name,"r", encoding="utf-8") as f: 
            return json.loads(f.read())
    except:
        return default
    
def save_json_file(file_name, data):
    try:
        with open(file_name,"w", encoding="utf-8") as f: 
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except:        
        return False