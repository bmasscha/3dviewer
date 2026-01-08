"""
Example script demonstrating how to send commands to the 3D Viewer via ZMQ.
This simulates the script_runner sending commands to the 3dviewer client.

Prerequisites:
1. The ZMQ server must be running
2. The 3D Viewer application must be running with ZMQ client enabled
"""
from acquila_zmq import AcquilaClient
import time


def main():
    """Send example commands to the 3D Viewer."""
    
    # Initialize the client (this acts as the script_runner)
    client = AcquilaClient(server_ip="127.0.0.1")
    
    print("=" * 60)
    print("3D Viewer ZMQ Command Test Script")
    print("=" * 60)
    print()
    
    # Example 1: Load data
    print("Test 1: Loading dataset...")
    try:
        result = client.send_command(
            component="3dviewer",
            command="load_data",
            arg1="c:/code/antigravity/3dviewer/example_data",  # Update this path
            wait_for="ACK",
            timeout=30  # 30 seconds timeout for loading
        )
        print(f"  Result: {result}")
    except Exception as e:
        print(f"  Error: {e}")
    
    print()
    time.sleep(2)
    
    # Example 2: Change rendering mode
    print("Test 2: Setting rendering mode to MIP...")
    try:
        result = client.send_command(
            component="3dviewer",
            command="set rendering mode to MIP",
            wait_for="ACK",
            timeout=10
        )
        print(f"  Result: {result}")
    except Exception as e:
        print(f"  Error: {e}")
    
    print()
    time.sleep(1)
    
    # Example 3: Adjust density
    print("Test 3: Setting density to 5...")
    try:
        result = client.send_command(
            component="3dviewer",
            command="set density to 5",
            wait_for="ACK",
            timeout=10
        )
        print(f"  Result: {result}")
    except Exception as e:
        print(f"  Error: {e}")
    
    print()
    time.sleep(1)
    
    # Example 4: Change transfer function
    print("Test 4: Setting transfer function to Hot...")
    try:
        result = client.send_command(
            component="3dviewer",
            command="set transfer function to Hot",
            wait_for="ACK",
            timeout=10
        )
        print(f"  Result: {result}")
    except Exception as e:
        print(f"  Error: {e}")
    
    print()
    time.sleep(1)
    
    # Example 5: Rotate view
    print("Test 5: Rotating view...")
    try:
        result = client.send_command(
            component="3dviewer",
            command="rotate 45",
            wait_for="ACK",
            timeout=10
        )
        print(f"  Result: {result}")
    except Exception as e:
        print(f"  Error: {e}")
    
    print()
    print("=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    print("Starting ZMQ command test...")
    print("Make sure:")
    print("  1. The ZMQ server is running")
    print("  2. The 3D Viewer application is running")
    print()
    input("Press Enter to continue...")
    print()
    
    main()
