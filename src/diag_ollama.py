import urllib.request
import json

def test_conn(url):
    print(f"Testing {url}...")
    try:
        # Disable proxy specifically for this request
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
        with opener.open(url, timeout=2.0) as response:
            print(f"  SUCCESS: Status {response.getcode()}")
            return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

print("Ollama Connection Diagnostics")
urls = [
    "http://localhost:11434/api/tags",
    "http://127.0.0.1:11434/api/tags",
    "http://[::1]:11434/api/tags"
]

for u in urls:
    test_conn(u)
