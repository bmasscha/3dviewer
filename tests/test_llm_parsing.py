import sys
import os
import json

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from command_interpreter import CommandInterpreter

def test_parsing():
    interpreter = CommandInterpreter()
    print(f"Testing with model: {interpreter.model_name}")
    
    test_commands = [
        "zoom in",
        "rotate x 45",
        "set mode mip",
        "set colors to viridis",
        "move x slice to 50%",
        "what can you do?"
    ]
    
    for cmd in test_commands:
        print(f"\nUser: {cmd}")
        action, response = interpreter.interpret(cmd)
        print(f"Action: {json.dumps(action, indent=2)}")
        print(f"Response: {response}")

if __name__ == "__main__":
    test_parsing()
