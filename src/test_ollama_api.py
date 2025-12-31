import urllib.request
import json

# Test the exact setup
url = "http://127.0.0.1:11434/api/generate"
payload = {
    "model": "gemma3:1b",
    "prompt": "Say hello",
    "stream": False
}

try:
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    
    proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_handler)
    
    with opener.open(req, timeout=10.0) as response:
        result = json.loads(response.read().decode('utf-8'))
        print("SUCCESS!")
        print(json.dumps(result, indent=2))
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.reason}")
    print(f"Response body: {e.read().decode()}")
except Exception as e:
    print(f"Error: {e}")
