import sys
import os
import json
import yaml
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "pg-gccoe-carlos-monteverde")
LOCATION = os.getenv("GCP_LOCATION", "us")

def main():
    print("🚀 Starting Data Quality Rule Publishing...")
    
    output_dir = "output"
    try:
        files = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".json")]
        if not files:
            print("❌ No validation JSON files found in output/")
            return
        
        latest_file = max(files, key=os.path.getmtime)
        print(f"📖 Processing file: {latest_file}")
        
        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
    except Exception as e:
        print(f"❌ Error reading DQ file: {e}")
        return

    # Convert JSON rules to Dataplex YAML format
    rules = data.get("rules", [])
    if not rules:
        print("⚠️ No rules found in JSON.")
        return

    yaml_structure = {
        "rules": []
    }

    for r in rules:
        yaml_rule = {
            "pbt_rule_id": f"rule_{r.get('column')}_{r.get('dimension')}".lower(),
            "target": r.get("column"),
            "dimension": r.get("dimension"),
            "description": r.get("description"),
        }
        
        if r.get("type") == "REGEX" and "parameters" in r:
             yaml_rule["regex"] = r["parameters"].get("pattern")
        
        yaml_structure["rules"].append(yaml_rule)

    timestamp = int(time.time())
    yaml_filename = f"{output_dir}/dq_rules_{timestamp}.yaml"
    
    with open(yaml_filename, "w") as f:
        yaml.dump(yaml_structure, f, sort_keys=False)
        
    print(f"✅ Generated YAML Rules: {yaml_filename}")
    print("Content:")
    print(yaml.dump(yaml_structure, sort_keys=False))

if __name__ == "__main__":
    main()
