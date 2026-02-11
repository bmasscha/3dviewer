import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from command_interpreter import CommandInterpreter
import llm_provider

def test_switching():
    print("Testing Provider Switching...")
    ci = CommandInterpreter()
    print(f"  Initialized with: {ci.provider.get_name()}")
    assert ci.provider.get_name() == "Ollama"
    
    ci.interpret("set provider gemini")
    print(f"  Switched to: {ci.provider.get_name()}")
    assert ci.provider.get_name() == "Gemini"
    
    ci.interpret("set provider ollama")
    print(f"  Switched back to: {ci.provider.get_name()}")
    assert ci.provider.get_name() == "Ollama"
    print("  SUCCESS: Switching works.")

def test_diagnostics():
    print("Testing Diagnostics...")
    ci = CommandInterpreter()
    _, msg = ci.interpret("status")
    print(f"  Ollama Status: {msg}")
    
    ci.interpret("set provider gemini")
    _, msg = ci.interpret("status")
    print(f"  Gemini Status: {msg}")
    print("  SUCCESS: Diagnostics work.")

if __name__ == "__main__":
    try:
        test_switching()
        test_diagnostics()
        print("\nAll basic tests passed!")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
