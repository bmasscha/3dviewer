import json
import urllib.request
import urllib.error
import os
import re
import logging
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt, context=None, options=None):
        """Generates a response from the LLM."""
        pass

    @abstractmethod
    def get_name(self):
        """Returns the name of the provider."""
        pass

    @abstractmethod
    def get_available_models(self):
        """Returns a list of available models."""
        pass

class OllamaProvider(LLMProvider):
    def __init__(self, model_name="gemma3:1b"):
        self.model_name = model_name
        self.url = "http://127.0.0.1:11434/api/generate"
        self.logger = logging.getLogger(__name__)

    def get_name(self):
        return "Ollama"

    def generate(self, prompt, context=None, options=None):
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "context": context,
            "options": options or {
                "temperature": 0.0,
                "num_predict": 128,
            }
        }
        
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(self.url, data=data, headers={'Content-Type': 'application/json'})
            
            # Disable proxies for local stability
            proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy_handler)
            
            with opener.open(req, timeout=15.0) as response:
                result = json.loads(response.read().decode('utf-8'))
                return {
                    "response": result.get('response', '').strip(),
                    "context": result.get('context'),
                    "error": None
                }
        except Exception as e:
            return {"error": f"Ollama Connection Error: {str(e)}"}

    def get_available_models(self):
        url = "http://127.0.0.1:11434/api/tags"
        try:
            proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy_handler)
            with opener.open(url, timeout=2.0) as response:
                data = json.loads(response.read().decode('utf-8'))
                return [m['name'] for m in data.get('models', [])]
        except Exception:
            return []

class GeminiProvider(LLMProvider):
    def __init__(self, model_name="gemini-2.0-flash"):
        self.model_name = model_name
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        self.history = [] # List of {"role": "user"|"model", "parts": [{"text": "..."}]}
        self.system_prompt = None
        self.logger = logging.getLogger(__name__)

    def get_name(self):
        return "Gemini"

    def generate(self, prompt, context=None, options=None):
        if not self.api_key:
            return {"error": "GOOGLE_API_KEY not found in environment. Please set it to use Gemini."}

        # Some models prefer v1, some v1beta. We'll stick to a configurable version or try v1 first.
        api_version = os.environ.get("GEMINI_API_VERSION", "v1beta") # Users can override, default to v1beta for better compatibility
        url = f"https://generativelanguage.googleapis.com/{api_version}/models/{self.model_name}:generateContent?key={self.api_key}"
        
        contents = []
        # Add history
        for item in self.history:
            contents.append(item)
        
        # Add current prompt
        contents.append({"role": "user", "parts": [{"text": prompt}]})
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": options.get("temperature", 0.0) if options else 0.0,
                "maxOutputTokens": options.get("num_predict", 128) if options else 128,
            }
        }
        
        if self.system_prompt:
            payload["system_instruction"] = {"parts": [{"text": self.system_prompt}]}

        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
            
            with urllib.request.urlopen(req, timeout=15.0) as response:
                result = json.loads(response.read().decode('utf-8'))
                
                # Extract text from Gemini response
                try:
                    candidates = result.get('candidates', [])
                    if candidates:
                        text = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '').strip()
                        
                        # Update history (max 10 turns)
                        self.history.append({"role": "user", "parts": [{"text": prompt}]})
                        self.history.append({"role": "model", "parts": [{"text": text}]})
                        if len(self.history) > 20: # 10 turns
                            self.history = self.history[-20:]
                            
                        return {
                            "response": text,
                            "context": None, # Gemini doesn't use the same context token system
                            "error": None
                        }
                    else:
                        return {"error": "Gemini returned no candidates."}
                except (IndexError, KeyError) as e:
                    return {"error": f"Error parsing Gemini response: {str(e)}"}
                    
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode('utf-8')
                err_json = json.loads(err_body)
                msg = err_json.get('error', {}).get('message', str(e))
                return {"error": f"Gemini API Error ({e.code}): {msg}"}
            except:
                return {"error": f"Gemini API Error: {str(e)}"}
        except Exception as e:
            return {"error": f"Gemini Connection Error: {str(e)}"}

    def get_available_models(self):
        if not self.api_key:
            return ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
        try:
            with urllib.request.urlopen(url, timeout=5.0) as response:
                data = json.loads(response.read().decode('utf-8'))
                models = data.get('models', [])
                names = [m.get('name', '').replace('models/', '') for m in models]
                # Filter for models that support generateContent
                names = [m.get('name', '').replace('models/', '') for m in models 
                         if 'generateContent' in m.get('supportedGenerationMethods', [])]
                return sorted(list(set(names))) if names else ["gemini-1.5-flash", "gemini-1.5-pro"]
        except Exception:
            return ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"]
