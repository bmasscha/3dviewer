import re
import json
import logging

class CommandInterpreter:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.last_action = None
        self.history = [] # For UI display
        self.context = None # Ollama native context tokens
        self.model_name = "llama3.2" # Default model

    def interpret(self, text):
        """
        Interprets a text command and returns (action_dict, response_message).
        """
        raw_text = text.strip()
        text = raw_text.lower()
        
        # 0. Local Logic: Math (e.g., "1+1", "22 / 7")
        if re.match(r"^[\d\+\-\*\/\s\(\)\.]+$", text):
            try:
                # Safe eval for simple math
                result = eval(text, {"__builtins__": None}, {})
                return None, f"Result: <b>{result}</b>"
            except: pass
        
        # 0. Diagnostics and Help
        if any(w in text for w in ['status', 'diagnostics', 'check']):
            return self._run_diagnostics()
        
        # User manual model override: "set model gemma:1b"
        model_match = re.search(r"set model ([\w\.-:]+)", text)
        if model_match:
            new_model = model_match.group(1)
            self.model_name = new_model
            return None, f"Model switched to {new_model}. (Ensure it is downloaded in Ollama)"

        if any(w in text for w in ['help', 'what can you do', 'actions', 'list']):
            return self._run_help()

        # 1. Contextual modifiers and standalone numbers
        modifier = self._get_modifier(text)
        
        # 1. Standalone numbers (e.g., "90" following "rotate")
        nums_only = re.findall(r"^[-+]?\d*\.?\d+$", text)
        if nums_only and not any(w in text for w in ['bit', 'little', 'tiny', 'small', 'slightly', 'lot', 'big', 'fast', 'much', 'very']):
            val = float(nums_only[0])
            if self.last_action:
                action = json.loads(json.dumps(self.last_action))
                if 'params' in action and 'value' in action['params']:
                    action['params']['value'] = val
                    return action, f"Updating {action['action']} to {val}."
        
        # 2. Handle "more" / "less"
        if any(w in text for w in ['more', 'again', 'repeat', 'continue']):
            if self.last_action:
                action = json.loads(json.dumps(self.last_action))
                if modifier != 1.0 and 'params' in action and 'value' in action['params']:
                    action['params']['value'] *= modifier
                return action, f"Repeating {action['action']} (scale: {modifier}x)."
            return None, "Nothing to repeat yet."
        
        if any(w in text for w in ['less', 'smaller', 'opposite', 'reverse']):
            if self.last_action:
                action = json.loads(json.dumps(self.last_action))
                if 'params' in action and 'value' in action['params']:
                    action['params']['value'] *= (-1.0 * modifier)
                return action, f"Doing the opposite (scale: {modifier}x)."
            return None, "No previous action to reverse."

        # 2. Try Simple Heuristics (Regex)
        action = self._try_regex_parsing(text)
        if action:
            # Apply modifier to the new action
            if modifier != 1.0 and 'params' in action and 'value' in action['params']:
                action['params']['value'] *= modifier
            
            self.last_action = action
            self.history.append({"role": "user", "content": raw_text})
            msg = self._get_default_message(action)
            self.history.append({"role": "assistant", "content": msg})
            return action, msg
            
        # 3. Try LLM (Ollama/Local)
        llm_result = self._try_llm_parsing(raw_text)
        if llm_result:
            action = llm_result.get('action_dict')
            msg = llm_result.get('response', "")
            
            if action:
                self.last_action = action
            
            # Return response even if action is None (Conversational mode)
            if msg:
                return action, msg
            
            if action:
                return action, "Executing command."
        
        # 4. Fallback Handling
        error_msg = llm_result.get('error') if llm_result else None
        if error_msg:
            return None, f"<b>AI DISCONNECTED:</b> {error_msg}"
        
        return None, "I'm sorry, I didn't quite catch that. Try 'zoom in' or ask 'help'."

    def _run_help(self):
        help_text = (
            "<b>Camera:</b> zoom, rotate, reset, home<br/>"
            "<b>Rendering:</b> 'set mode mip/volume/cinematic', 'use viridis colors'<br/>"
            "<b>Slices:</b> 'move X slice to middle', 'Y slice to 50'<br/>"
            "<b>AI Model:</b> 'set model gemma3:1b' (switches which AI brain to use)<br/>"
            "<b>System:</b> status, help<br/>"
            "<i>Note: 'set model' = AI brain, 'set mode' = rendering style</i>"
        )
        return None, help_text

    def _get_modifier(self, text):
        scale = 1.0
        if any(w in text for w in ['bit', 'little', 'tiny', 'small', 'slightly']):
            scale = 0.3
        elif any(w in text for w in ['lot', 'big', 'fast', 'much', 'very']):
            scale = 3.0
        return scale

    def _run_diagnostics(self):
        import urllib.request
        # Force 127.0.0.1 and disable proxies for Windows 11 stability
        url = "http://127.0.0.1:11434/api/tags"
        try:
            proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy_handler)
            with opener.open(url, timeout=1.0) as response:
                data = json.loads(response.read().decode('utf-8'))
                models = [m['name'] for m in data.get('models', [])]
                model_str = ", ".join(models) if models else "None"
                
                # If current model not in list, suggest one
                if self.model_name not in [m.split(':')[0] for m in models] and self.model_name not in models and models:
                    self.model_name = models[0] # Auto-pick if current is missing
                
                return None, f"Ollama is RUNNING. Active Model: <b>{self.model_name}</b>. Available: {model_str}. (Use 'set model [name]' to switch)"
        except Exception as e:
            return None, f"<b>AI DISCONNECTED:</b> {str(e)} (Check firewall/port 11434)"

    def _get_default_message(self, action):
        a = action.get('action')
        p = action.get('params', {})
        if a == 'zoom':
            return f"Zooming {'in' if p.get('value', 0) > 0 else 'out'}."
        if a == 'rotate':
            axis_name = "horizontally" if p.get('axis') == 'y' else "vertically"
            val = p.get('value', 10.0)
            return f"Rotating {abs(val):.1f} degrees {axis_name}."
        if a == 'reset':
            return "Resetting camera."
        return "Executing."

    def _try_llm_parsing(self, text):
        import urllib.request
        import urllib.error
        
        # Force 127.0.0.1 and disable proxies for Windows 11 stability
        url = "http://127.0.0.1:11434/api/generate"
        
        # This is the "Manual" for the LLM
        system_prompt = (
            "You are a helpful AI assistant with viewer control abilities.\n"
            "You can: answer questions, do math, chat, AND control the 3D viewer.\n\n"
            "### AVAILABLE ACTIONS:\n"
            "1. 'zoom': Move camera closer/further.\n"
            "   - Params: {'value': float} (+ for in, - for out)\n"
            "2. 'rotate': Orbit camera around data.\n"
            "   - Params: {'axis': 'x'|'y', 'value': float} (degrees, left/right=y, up/down=x)\n"
            "3. 'reset': Return to default view.\n"
            "4. 'set_mode': Change rendering mode.\n"
            "   - Params: {'mode': 'mip'|'volume'|'cinematic'|'mida'}\n"
            "5. 'set_tf': Change transfer function (color map).\n"
            "   - Params: {'tf': 'grayscale'|'viridis'|'plasma'|'medical'|'rainbow'}\n"
            "6. 'set_slice': Position orthogonal slice.\n"
            "   - Params: {'axis': 'x'|'y'|'z', 'value': int} OR {'axis': 'x'|'y'|'z', 'percent': float}\n"
            "7. 'set_lighting': Change lighting mode.\n"
            "   - Params: {'mode': 'fixed'|'headlamp'}\n"
            "8. 'adjust_quality': Modify sampling rate.\n"
            "   - Params: {'value': float} (1.0=normal, 2.0=high, 0.5=fast)\n"
            "9. 'crop': Clip/crop the volume.\n"
            "   - Params: {'axis': 'x'|'y'|'z', 'min': float, 'max': float} (normalized 0.0 to 1.0)\n\n"
            "### RULES:\n"
            "- Return JSON: {\"action_dict\": {...} or null, \"response\": \"message\"}\n"
            "- For viewer control: set action_dict with command\n"
            "- For chat/questions: set action_dict=null, answer helpfully\n"
            "- Be friendly and conversational!\n"
        )
        
        payload = {
            "model": self.model_name,
            "prompt": f"{system_prompt}\nUser: {text}\nJSON:",
            "stream": False,
            "context": self.context
        }
        
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
            
            proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy_handler)
            
            with opener.open(req, timeout=5.0) as response:
                result = json.loads(response.read().decode('utf-8'))
                self.context = result.get('context')
                response_text = result.get('response', '').strip()
                
                # Try to extract JSON from the response
                res_data = None
                # Look for JSON object in the response
                json_match = re.search(r'\{[^{}]*"action_dict"[^{}]*\}', response_text, re.DOTALL)
                if json_match:
                    try:
                        res_data = json.loads(json_match.group(0))
                    except json.JSONDecodeError:
                        pass
                
                # If no valid JSON found, treat as pure chat
                if not res_data or not isinstance(res_data, dict):
                    # Pure conversational response
                    self.history.append({"role": "user", "content": text})
                    self.history.append({"role": "assistant", "content": response_text})
                    return {"action_dict": None, "response": response_text}
                
                # Double-check action_dict
                action = res_data.get('action_dict')
                if isinstance(action, str):
                    # Small models often send "null" or the action name as a string
                    if action.lower() in ['null', 'none', '']:
                        res_data['action_dict'] = None
                    else:
                        # Attempt to fix: if they sent "zoom", they forgot the params
                        res_data['action_dict'] = None # Better to do nothing than crash
                elif action and not isinstance(action, dict):
                    return {"error": f"<b>AI DATA ERROR:</b> Invalid structure ({type(action).__name__})"}

                # Success - log and update state
                self.history.append({"role": "user", "content": text})
                self.history.append({"role": "assistant", "content": res_data.get('response', '')})
                return res_data
        except Exception as e:
            return {"error": f"Connection Error: {str(e)}"}

    def _try_regex_parsing(self, text):
        # Extract number if present
        nums = re.findall(r"[-+]?\d*\.\d+|\d+", text)
        val_from_text = float(nums[0]) if nums else None

        # Zoom commands (including natural language)
        zoom_in_phrases = ['zoom', 'closer', 'nearer', 'approach']
        zoom_out_phrases = ['back', 'away', 'further', 'retreat']
        
        if any(w in text for w in zoom_in_phrases) or any(w in text for w in zoom_out_phrases):
            value = val_from_text if val_from_text is not None else 1.0
            # Check for zoom out indicators
            if any(w in text for w in zoom_out_phrases) and not any(w in text for w in zoom_in_phrases):
                value = -abs(value)
            elif 'out' in text:
                value = -abs(value)
            return {'action': 'zoom', 'params': {'value': value}}
        
        # Rotate commands
        if any(w in text for w in ['rotate', 'turn', 'spin', 'orbit']):
            axis = 'y' # Default
            if 'up' in text or 'down' in text or 'vertically' in text or 'slope' in text:
                axis = 'x'
            
            value = val_from_text if val_from_text is not None else 10.0
            if 'left' in text or 'up' in text: # Conventions
                value = -abs(value)
            
            return {'action': 'rotate', 'params': {'axis': axis, 'value': value}}
                
        # Reset / Home commands
        if any(w in text for w in ['reset', 'home', 'default', 'lost', 'center', 'start']):
            return {'action': 'reset', 'params': {}}
        
        # Rendering mode commands
        if any(w in text for w in ['mip', 'maximum intensity']):
            return {'action': 'set_mode', 'params': {'mode': 'mip'}}
        if 'cinematic' in text:
            return {'action': 'set_mode', 'params': {'mode': 'cinematic'}}
        if 'mida' in text:
            return {'action': 'set_mode', 'params': {'mode': 'mida'}}
        
        # Transfer function commands
        for tf_name in ['viridis', 'plasma', 'medical', 'rainbow', 'grayscale']:
            if tf_name in text:
                return {'action': 'set_tf', 'params': {'tf': tf_name}}
        
        # Slice positioning
        if 'slice' in text:
            axis = None
            if 'x' in text:
                axis = 'x'
            elif 'y' in text:
                axis = 'y'
            elif 'z' in text:
                axis = 'z'
            
            if axis:
                # Check for semantic positions
                if 'middle' in text or 'center' in text:
                    return {'action': 'set_slice', 'params': {'axis': axis, 'percent': 50.0}}
                elif 'start' in text or 'beginning' in text:
                    return {'action': 'set_slice', 'params': {'axis': axis, 'percent': 0.0}}
                elif 'end' in text:
                    return {'action': 'set_slice', 'params': {'axis': axis, 'percent': 100.0}}
                elif val_from_text is not None:
                    # Check if it's a percentage or absolute value
                    if '%' in text or val_from_text <= 100:
                        return {'action': 'set_slice', 'params': {'axis': axis, 'percent': val_from_text}}
                    else:
                        return {'action': 'set_slice', 'params': {'axis': axis, 'value': int(val_from_text)}}
        
        # Lighting mode
        if 'headlamp' in text:
            return {'action': 'set_lighting', 'params': {'mode': 'headlamp'}}
        if 'fixed' in text and 'light' in text:
            return {'action': 'set_lighting', 'params': {'mode': 'fixed'}}

        # Crop / Clip
        if any(w in text for w in ['crop', 'clip']):
            axis = None
            if 'x' in text: axis = 'x'
            elif 'y' in text: axis = 'y'
            elif 'z' in text: axis = 'z'
            
            if axis and len(nums) >= 2:
                v1 = float(nums[0])
                v2 = float(nums[1])
                # Normalize if they look like percentages
                if v1 > 1.0: v1 /= 100.0
                if v2 > 1.0: v2 /= 100.0
                return {'action': 'crop', 'params': {'axis': axis, 'min': min(v1, v2), 'max': max(v1, v2)}}
            elif any(w in text for w in ['half', 'middle', 'center']):
                 if axis:
                     return {'action': 'crop', 'params': {'axis': axis, 'min': 0.25, 'max': 0.75}}
            
        return None
