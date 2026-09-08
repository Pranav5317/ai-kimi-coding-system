import requests
import json

r = requests.post("http://localhost:11434/api/generate", json={
    "model": "llama3.1:latest",
    "prompt": "<|start_header_id|>system<|end_header_id|>\n\nGiven the following functions, please respond with a JSON for a function call with its proper arguments that best answers the given prompt.\n\nRespond in the format {\"name\": function name, \"parameters\": dictionary of argument name and its value}. Do not use variables.\n\n{\"type\": \"function\", \"function\": {\"name\": \"create_directory\", \"description\": \"Create directory\", \"parameters\": {\"type\": \"object\", \"properties\": {\"path\": {\"type\": \"string\"}}, \"required\": [\"path\"]}}}\n{\"type\": \"function\", \"function\": {\"name\": \"create_file\", \"description\": \"Create a file with content in the workspace.\", \"parameters\": {\"type\": \"object\", \"properties\": {\"path\": {\"type\": \"string\"}, \"content\": {\"type\": \"string\"}}, \"required\": [\"path\", \"content\"]}}}\n<|eot_id|><|start_header_id|>user<|end_header_id|>\n\nCreate a directory named \"backend\" and inside it create a file named \"server.py\" containing a basic hello world script.<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n",
    "stream": False,
    "raw": True,
    "options": {"temperature": 0.0}
})

print("RAW OUTPUT WITH 2 TOOLS:", r.json().get("response"))

