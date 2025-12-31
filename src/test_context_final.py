from command_interpreter import CommandInterpreter
import logging

logging.basicConfig(level=logging.INFO)
ci = CommandInterpreter()

print("--- Test 1: Rotation ---")
ci.interpret("rotate 45")
res, msg = ci.interpret("90")
print(f"Input: '90', Result Action: {res}, Message: {msg}")

print("\n--- Test 2: Zoom ---")
ci.interpret("zoom out")
res, msg = ci.interpret("-5")
print(f"Input: '-5', Result Action: {res}, Message: {msg}")

print("\n--- Test 3: Standalone number without context ---")
ci.last_action = None
res, msg = ci.interpret("100")
print(f"Input: '100', Result Action: {res}, Message: {msg}")
