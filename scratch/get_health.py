import urllib.request
import json

try:
    with urllib.request.urlopen("http://127.0.0.1:8000/api/v1/health") as response:
        html = response.read().decode('utf-8')
        print("API V1 Health Response:", html)
except Exception as e:
    print("Error calling server api v1 health check:", e)
