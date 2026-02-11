import re
import json
import logging
import os
import llm_provider

class CommandInterpreter:
    def __init__(self, provider_type="ollama"):
        self.logger = logging.getLogger(__name__)
        self.last_action = None
        self.history = [] # For UI display
        self.context = None # Provider native context
        self.provider = None
        self.set_provider(provider_type)
        self.commands_prompt = self._load_commands_file()
        if self.provider:
            self.provider.system_prompt = self.commands_prompt

    def set_provider(self, provider_type, model_name=None):
        """Switches the active LLM provider."""
        if provider_type.lower() == "ollama":
            self.provider = llm_provider.OllamaProvider(model_name or "gemma3:1b")
        elif provider_type.lower() == "gemini":
            self.provider = llm_provider.GeminiProvider(model_name or "gemini-2.0-flash")
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")
        self.context = None # Reset context on provider switch
        if hasattr(self, 'commands_prompt'):
            self.provider.system_prompt = self.commands_prompt

    def interpret(self, text, state=None):
        """
        Interprets a text command and returns (action_dict, response_message).
        """
        self.current_state = state # Store for llm parsing
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
        
        # User manual model override: "set model gemini-1.5-flash"
        model_match = re.search(r"set model ([\w\-.:]+)", text)
        if model_match:
            new_model = model_match.group(1)
            self.provider.model_name = new_model
            return None, f"Model switched to {new_model} on {self.provider.get_name()}."

        # User manual provider override: "set provider gemini"
        provider_match = re.search(r"set provider (gemini|ollama)", text)
        if provider_match:
            new_provider = provider_match.group(1)
            try:
                self.set_provider(new_provider)
                return None, f"Provider switched to <b>{self.provider.get_name()}</b>."
            except Exception as e:
                return None, f"Error switching provider: {str(e)}"

        if any(w in text for w in ['help', 'what can you do', 'actions', 'commands', 'instructions']):
            return self._run_help()

        if 'list' in text or 'show' in text or 'what' in text:
            if any(w in text for w in ['color', 'scheme', 'palette', 'colormap', 'tf']):
                return self._run_list_colors()
            if any(w in text for w in ['mode', 'render']):
                return self._run_list_modes()
            if any(w in text for w in ['command', 'action', 'help']):
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
                # Smart "more" for absolute setters
                absolute_actions = ['adjust_quality', 'set_threshold', 'set_density', 'set_opacity']
                if action['action'] in absolute_actions:
                    if 'params' in action and 'value' in action['params']:
                        # If more quality, increase it. If more threshold, increase it.
                        # Scale based on modifier
                        scale = 1.2 * modifier if modifier != 1.0 else 1.2
                        action['params']['value'] *= scale
                        return action, f"Increasing {action['action']} to {action['params']['value']:.2f}."
                
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
        action = self._try_regex_parsing(text, raw_text)
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

    def _load_commands_file(self):
        """Load commands documentation from commands.md file."""
        try:
            commands_path = os.path.join(os.path.dirname(__file__), 'commands.md')
            with open(commands_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.logger.warning(f"Could not load commands.md: {e}")
            return self._get_fallback_prompt()

    def _get_fallback_prompt(self):
        """Fallback prompt if commands.md cannot be loaded."""
        return (
            "You are a helpful AI assistant with viewer control abilities.\n"
            "You can: answer questions, do math, chat, AND control the 3D viewer.\n\n"
            "Return JSON: {\"action_dict\": {...} or null, \"response\": \"message\"}\n"
            "Actions: zoom, rotate, reset, set_mode, set_tf, set_slice, crop, load\n"
        )

    def _run_help(self):
        help_text = (
            "<b>Available Commands:</b><br/>"
            "• <b>View:</b> zoom [in/out], rotate [x/y], reset/home, dual view<br/>"
            "• <b>Modes:</b> set mode [mip/standard/cinematic/mida/shaded/edge]<br/>"
            "• <b>Colors:</b> use [colormap] - e.g. 'use bone colors' or 'list color schemes'<br/>"
            "• <b>Slices:</b> move [X/Y/Z] slice to [percent], crop [X/Y/Z] [min] [max]<br/>"
            "• <b>Properties:</b> set threshold [0-1], set density/quality/opacity<br/>"
            "• <b>Advanced:</b> set lighting [fixed/headlamp], specular [0-2], shininess [1-128]<br/>"
            "• <b>System:</b> status, set provider [gemini/ollama], set model [name]<br/>"
            "<i>Try natural language: 'make the bone more visible' or 'sharpen the edges'.</i>"
        )
        return None, help_text

    def _run_list_colors(self):
        # Fetch from state if available, otherwise fallback to hardcoded list matching AppCore
        colormaps = [
            "grayscale", "viridis", "plasma", "medical", "legacy_rainbow", 
            "ct_bone", "ct_soft_tissue", "ct_muscle", "ct_lung", 
            "legacy_cool_warm", "ct_sandstone", "ct_body",
            "cet_fire", "cet_rainbow", "cet_coolwarm", "cet_bkr", "cet_bky", 
            "cet_glasbey", "cet_glasbey_dark", "cet_bgyw", "cet_bmy", "cet_kgy", 
            "cet_gray", "cet_cwr", "cet_linear_kry_5_95_c72", "cet_blues", "cet_isolum"
        ]
        
        # Group them for better readability
        standard = ["grayscale", "viridis", "plasma", "medical"]
        medical = ["ct_bone", "ct_soft_tissue", "ct_muscle", "ct_lung", "ct_sandstone", "ct_body"]
        perceptual = [c for c in colormaps if c.startswith("cet_")]
        others = [c for c in colormaps if c not in standard + medical + perceptual]

        result = "<b>Standard Colormaps:</b> " + ", ".join(standard) + "<br/>"
        result += "<b>Medical/CT:</b> " + ", ".join(medical) + "<br/>"
        result += "<b>Perceptually Uniform:</b> " + ", ".join(perceptual) + "<br/>"
        result += "<b>Legacy/Others:</b> " + ", ".join(others)
        
        return None, f"Available color schemes:<br/>{result}"

    def _run_list_modes(self):
        modes = ["MIP", "Standard (Volume)", "Cinematic", "MIDA", "Shaded", "Edge Enhanced"]
        result = "• " + "\n• ".join(modes)
        return None, f"Available rendering modes:<br/>{result}"

    def _get_modifier(self, text):
        scale = 1.0
        if any(w in text for w in ['bit', 'little', 'tiny', 'small', 'slightly']):
            scale = 0.3
        elif any(w in text for w in ['lot', 'big', 'fast', 'much', 'very']):
            scale = 3.0
        return scale

    def _run_diagnostics(self):
        # Provider diagnostics
        if isinstance(self.provider, llm_provider.OllamaProvider):
            models = self.provider.get_available_models()
            model_str = ", ".join(models) if models else "None"
            status = "RUNNING" if models else "NOT RESPONDING"
            return None, f"Ollama is {status}. Active Model: <b>{self.provider.model_name}</b>. Available: {model_str}."
        elif isinstance(self.provider, llm_provider.GeminiProvider):
            api_key_status = "PRESENT" if self.provider.api_key else "MISSING"
            models = self.provider.get_available_models()
            model_str = ", ".join(models[:10]) # Show first 10
            if len(models) > 10: model_str += "..."
            return None, f"Gemini Active. Model: <b>{self.provider.model_name}</b>. API Key: {api_key_status}. Available: {model_str}"
        
        return None, "Unknown provider diagnostics."

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
        # Construct the prompt based on provider capabilities
        state_str = ""
        if hasattr(self, 'current_state') and self.current_state:
            state_str = f"\nCurrent Viewer State: {json.dumps(self.current_state)}"

        if isinstance(self.provider, llm_provider.GeminiProvider):
            # Gemini uses system_instruction for the instructions
            prompt = f"{state_str}\nUser: {text}\nJSON:"
        else:
            # Fallback for Ollama/others that might need instructions in the main prompt
            system_prompt = self.commands_prompt
            prompt = f"{system_prompt}\n{state_str}\nUser: {text}\nJSON:"

        options = {
            "temperature": 0.0,
            "num_predict": 128,
            "stop": ["User:", "\n\n"]
        }
        
        result = self.provider.generate(prompt, context=self.context, options=options)
        
        if result.get('error'):
            return result

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
                res_data['action_dict'] = None # Better to do nothing than crash
        elif action and not isinstance(action, dict):
            return {"error": f"<b>AI DATA ERROR:</b> Invalid structure ({type(action).__name__})"}

        # Success - log and update state
        self.history.append({"role": "user", "content": text})
        self.history.append({"role": "assistant", "content": res_data.get('response', '')})
        return res_data

    def _try_regex_parsing(self, text, raw_text):
        # 1. Load Folder (Highest Priority to avoid path shadowing)
        # Match everything after 'load' (and optional 'overlay') as the path
        if 'load' in text:
            path_match = re.search(r'load\s+(?:overlay\s+)?(.+)', raw_text, re.IGNORECASE)
            if path_match:
                path = path_match.group(1).strip()
                # Remove surrounding quotes if present
                if (path.startswith('"') and path.endswith('"')) or (path.startswith("'") and path.endswith("'")):
                    path = path[1:-1]
                return {'action': 'load', 'params': {'path': path}}

        # Extract number if present
        nums = re.findall(r"[-+]?\d*\.\d+|\d+", text)
        val_from_text = float(nums[0]) if nums else None

        # Zoom commands (including natural language)
        zoom_in_phrases = [r'\bzoom\b', r'\bcloser\b', r'\bnearer\b', r'\bapproach\b']
        zoom_out_phrases = [r'\bback\b', r'\baway\b', r'\bfurther\b', r'\bretreat\b']
        
        if any(re.search(p, text) for p in zoom_in_phrases) or any(re.search(p, text) for p in zoom_out_phrases):
            value = val_from_text if val_from_text is not None else 1.0
            if any(re.search(p, text) for p in zoom_out_phrases) and not any(re.search(p, text) for p in zoom_in_phrases):
                value = -abs(value)
            elif r'\bout\b' in text: # Simple check
                value = -abs(value)
            return {'action': 'zoom', 'params': {'value': value}}
        
        # Rotate commands
        if any(re.search(r'\b' + w + r'\b', text) for w in ['rotate', 'turn', 'spin', 'orbit']):
            axis = 'y'
            if any(re.search(r'\b' + w + r'\b', text) for w in ['up', 'down', 'vertically', 'slope']):
                axis = 'x'
            
            value = val_from_text if val_from_text is not None else 10.0
            if any(re.search(r'\b' + w + r'\b', text) for w in ['left', 'up']):
                value = -abs(value)
            
            return {'action': 'rotate', 'params': {'axis': axis, 'value': value}}
                
        # Reset / Home commands
        if any(re.search(r'\b' + w + r'\b', text) for w in ['reset', 'home', 'default', 'lost', 'center', 'start']):
            return {'action': 'reset', 'params': {}}
        
        # Rendering mode commands
        if any(re.search(r'\b' + w + r'\b', text) for w in ['mip', 'maximum intensity']):
            return {'action': 'set_mode', 'params': {'mode': 'mip'}}
        if re.search(r'\bcinematic\b', text):
            return {'action': 'set_mode', 'params': {'mode': 'cinematic'}}
        if re.search(r'\bmida\b', text):
            return {'action': 'set_mode', 'params': {'mode': 'mida'}}
        
        # Transfer function commands
        # Check specific cet prefixes first or common ones
        tf_options = ['viridis', 'plasma', 'medical', 'legacy_rainbow', 'legacy_cool_warm', 'grayscale', 
                      'cet_fire', 'cet_rainbow', 'cet_coolwarm', 'cet_bkr', 'cet_bky', 'cet_glasbey', 'cet_glasbey_dark',
                      'cet_bgyw', 'cet_bmy', 'cet_kgy', 'cet_gray', 'cet_cwr', 'cet_linear_kry_5_95_c72', 'cet_blues', 'cet_isolum']
        for tf_name in tf_options:
            if re.search(r'\b' + tf_name + r'\b', text):
                return {'action': 'set_tf', 'params': {'tf': tf_name}}
        
        # Fallback for just 'rainbow' or 'cool warm' to map to legacy if cet not specified
        if re.search(r'\brainbow\b', text) and 'cet_' not in text:
            return {'action': 'set_tf', 'params': {'tf': 'legacy_rainbow'}}
        if re.search(r'\bcool\s*warm\b', text) and 'cet_' not in text:
            return {'action': 'set_tf', 'params': {'tf': 'legacy_cool_warm'}}
        
        # Slice positioning
        if re.search(r'\bslice\b', text):
            axis = None
            if re.search(r'\bx\b', text): axis = 'x'
            elif re.search(r'\by\b', text): axis = 'y'
            elif re.search(r'\bz\b', text): axis = 'z'
            
            if axis:
                if any(re.search(r'\b' + w + r'\b', text) for w in ['middle', 'center']):
                    return {'action': 'set_slice', 'params': {'axis': axis, 'percent': 50.0}}
                elif any(re.search(r'\b' + w + r'\b', text) for w in ['start', 'beginning']):
                    return {'action': 'set_slice', 'params': {'axis': axis, 'percent': 0.0}}
                elif re.search(r'\bend\b', text):
                    return {'action': 'set_slice', 'params': {'axis': axis, 'percent': 100.0}}
                elif val_from_text is not None:
                    if '%' in text or val_from_text <= 100:
                        return {'action': 'set_slice', 'params': {'axis': axis, 'percent': val_from_text}}
                    else:
                        return {'action': 'set_slice', 'params': {'axis': axis, 'value': int(val_from_text)}}
        
        # Lighting mode
        if re.search(r'\bheadlamp\b', text):
            return {'action': 'set_lighting', 'params': {'mode': 'headlamp'}}
        if re.search(r'\bfixed\b', text) and re.search(r'\blight\b', text):
            return {'action': 'set_lighting', 'params': {'mode': 'fixed'}}

        # Crop / Clip
        if any(re.search(r'\b' + w + r'\b', text) for w in ['crop', 'clip']):
            axis = None
            if re.search(r'\bx\b', text): axis = 'x'
            elif re.search(r'\by\b', text): axis = 'y'
            elif re.search(r'\bz\b', text): axis = 'z'
            
            if axis and len(nums) >= 2:
                v1, v2 = float(nums[0]), float(nums[1])
                if v1 > 1.0: v1 /= 100.0
                if v2 > 1.0: v2 /= 100.0
                return {'action': 'crop', 'params': {'axis': axis, 'min': min(v1, v2), 'max': max(v1, v2)}}
            elif any(re.search(r'\b' + w + r'\b', text) for w in ['half', 'middle', 'center']):
                 if axis:
                     return {'action': 'crop', 'params': {'axis': axis, 'min': 0.25, 'max': 0.75}}

        # Threshold commands
        if re.search(r'\bthreshold\b', text):
            return {'action': 'set_threshold', 'params': {'value': val_from_text if val_from_text is not None else 0.05}}
            
        # Quality / Sampling commands
        if any(re.search(r'\b' + w + r'\b', text) for w in ['quality', 'sampling', 'resolution']):
            # If "increase" or "better", and no number, suggest 1.5x
            if any(w in text for w in ['increase', 'better', 'higher', 'more']) and val_from_text is None:
                return {'action': 'adjust_quality', 'params': {'value': 1.5}}
            # If "decrease" or "lower", and no number, suggest 0.5x
            if any(w in text for w in ['decrease', 'lower', 'faster', 'less']) and val_from_text is None:
                return {'action': 'adjust_quality', 'params': {'value': 0.5}}
            return {'action': 'adjust_quality', 'params': {'value': val_from_text if val_from_text is not None else 1.0}}

        # Density / Opacity commands
        if any(re.search(r'\b' + w + r'\b', text) for w in ['density', 'opacity']):
            return {'action': 'set_density', 'params': {'value': val_from_text if val_from_text is not None else 50.0}}

        # Overlay Alignment & Scaling
        if re.search(r'\boffset\b', text):
            return {'action': 'set_offset', 'params': {}}
        if re.search(r'\bscale\b', text):
            return {'action': 'set_scale', 'params': {}}
        if re.search(r'\bfit\b', text):
            return {'action': 'fit_overlay', 'params': {}}
        if re.search(r'\bcenter\b', text):
            return {'action': 'center_overlay', 'params': {}}

        return None
