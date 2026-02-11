import os
import json
import urllib.request
import urllib.error

def list_gemini_models():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY not found in environment.")
        return

    # Try both v1 and v1beta
    for version in ["v1", "v1beta"]:
        print(f"\n--- Testing API Version: {version} ---")
        url = f"https://generativelanguage.googleapis.com/{version}/models?key={api_key}"
        try:
            with urllib.request.urlopen(url, timeout=10.0) as response:
                data = json.loads(response.read().decode('utf-8'))
                models = data.get('models', [])
                print(f"Found {len(models)} models.")
                for m in models:
                    name = m.get('name', '').replace('models/', '')
                    supported_methods = m.get('supportedGenerationMethods', [])
                    if 'generateContent' in supported_methods:
                        print(f"  - {name} (Supports generateContent)")
                    else:
                        print(f"  - {name}")
        except urllib.error.HTTPError as e:
            print(f"HTTP Error {e.code}: {e.reason}")
            try:
                print(f"Response: {e.read().decode('utf-8')}")
            except: pass
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    list_gemini_models()
