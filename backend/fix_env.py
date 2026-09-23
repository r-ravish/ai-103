import json
import subprocess

with open("/Users/ravishraheja/.gemini/antigravity-ide/brain/fbc248c3-9688-487e-9de9-3516b4db283b/.system_generated/tasks/task-445.log", "r") as f:
    lines = f.readlines()

# The JSON starts after "Output:\n"
json_str = ""
capture = False
for line in lines:
    if line.strip() == "Output:":
        capture = True
        continue
    if capture and line.startswith("Log:"):
        break
    if capture:
        json_str += line

data = json.loads(json_str)
env_vars = data["properties"]["template"]["containers"][0]["env"]

new_vars = {
    "AZURE_CLIENT_ID": "49c28cb9-57af-4111-b17f-19345d82ffdb",
    "AZURE_TENANT_ID": "69cb8230-07dd-45ab-9ae8-0e620cf722d5",
    "AZURE_CLIENT_SECRET": "secretref:azure-client-secret"
}

env_cmd_args = []
for item in env_vars:
    name = item["name"]
    if name in new_vars:
        continue
    
    if "secretRef" in item:
        env_cmd_args.append(f"{name}=secretref:{item['secretRef']}")
    else:
        val = item.get("value", "")
        # escape spaces and special chars if needed, though subprocess handles lists safely
        env_cmd_args.append(f"{name}={val}")

for k, v in new_vars.items():
    env_cmd_args.append(f"{k}={v}")

cmd = [
    "az", "containerapp", "update",
    "-n", "ai103-backend",
    "-g", "ai103-production",
    "--set-env-vars"
] + env_cmd_args

print("Running command to restore env vars...")
subprocess.run(cmd, check=True)
print("Restored successfully.")
