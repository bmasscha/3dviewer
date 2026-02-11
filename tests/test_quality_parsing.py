import sys
import os
import json

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from command_interpreter import CommandInterpreter

def test_quality_parsing():
    interpreter = CommandInterpreter()
    print(f"Testing with model: {interpreter.provider.model_name}")
    
    test_commands = [
        "increase quality",
        "set quality to 2.5",
        "lower sampling",
        "better resolution",
        "quality 0.8"
    ]
    
    for cmd in test_commands:
        print(f"\nUser: {cmd}")
        action, response = interpreter.interpret(cmd)
        print(f"Action: {json.dumps(action, indent=2)}")
        print(f"Response: {response}")

if __name__ == "__main__":
    test_quality_parsing()
