"""
Test script for ZMQ Command Processor.
Tests all supported commands in the Acquila JSON format.

Prerequisites:
1. The ZMQ server must be running: python run_server.py
2. The 3D Viewer must be running: cd src && python qt_main.py
"""
from acquila_zmq import AcquilaClient
import time


def test_command(client, component, command, arg1="", arg2="", wait_for="ACK"):
    """Helper to send command and print result."""
    print(f"  CMD: {command} | arg1={arg1} | arg2={arg2}")
    try:
        # Use the correct API signature (no timeout parameter)
        result = client.send_command(
            component=component,
            command=command,
            arg1=arg1,
            arg2=arg2,
            wait_for=wait_for
        )
        status = result.get("status", "?") if result else "TIMEOUT"
        message = result.get("message", str(result)) if result else "No response"
        print(f"      → {status}: {message}")
        return result
    except Exception as e:
        print(f"      → EXCEPTION: {e}")
        return None


def main():
    client = AcquilaClient(server_ip="127.0.0.1", inbound_port=50003, outbound_port=50002)
    component = "3dviewer"
    
    print("=" * 70)
    print("3D Viewer ZMQ Command Processor Test")
    print("=" * 70)
    print()
    
    # Group 1: Data Loading
    print("[1] DATA LOADING")
    test_command(client, component, "load_data", arg1="C:/code/antigravity/3dviewer/example_data/recon_schildpad")
    time.sleep(2)
    print()
    
    # Group 2: Rendering
    print("[2] RENDERING")
    test_command(client, component, "set_rendering_mode", arg1="mip")
    test_command(client, component, "set_rendering_mode", arg1="volume")
    test_command(client, component, "set_rendering_mode", arg1="cinematic", arg2="0")
    print()
    
    # Group 3: Transfer Functions
    print("[3] TRANSFER FUNCTIONS")
    test_command(client, component, "set_transfer_function", arg1="rainbow")
    test_command(client, component, "set_transfer_function", arg1="plasma")
    test_command(client, component, "set_transfer_function", arg1="grayscale")
    print()
    
    # Group 4: Parameters
    print("[4] PARAMETERS")
    test_command(client, component, "set_threshold", arg1="0.1")
    test_command(client, component, "set_density", arg1="100")
    test_command(client, component, "set_quality", arg1="2.0")
    print()
    
    # Group 5: Camera
    print("[5] CAMERA")
    test_command(client, component, "rotate", arg1="y", arg2="45")
    test_command(client, component, "zoom", arg1="1")
    test_command(client, component, "set_fov", arg1="30")
    test_command(client, component, "reset_camera")
    print()
    
    # Group 6: Slicing
    print("[6] SLICING")
    test_command(client, component, "set_slice", arg1="z", arg2="50%")
    test_command(client, component, "set_slice", arg1="x", arg2="100")
    print()
    
    # Group 7: Lighting & Shading
    print("[7] LIGHTING & SHADING")
    test_command(client, component, "set_lighting", arg1="headlamp")
    test_command(client, component, "set_specular", arg1="0.8")
    test_command(client, component, "set_shininess", arg1="64")
    test_command(client, component, "set_gradient_weight", arg1="15")
    print()
    
    # Group 8: Cropping
    print("[8] CROPPING")
    test_command(client, component, "crop", arg1="z", arg2="0.2,0.8")
    print()
    
    # Group 9: Status
    print("[9] STATUS QUERY")
    result = test_command(client, component, "get_status")
    if result and result.get("data"):
        print("      Status data:")
        for k, v in result.get("data", {}).items():
            print(f"        {k}: {v}")
    print()
    
    print("=" * 70)
    print("All tests completed!")
    print("=" * 70)


if __name__ == "__main__":
    print("Starting ZMQ Command Processor Test...")
    print("Make sure:")
    print("  1. ZMQ server is running: python run_server.py")
    print("  2. 3D Viewer is running: cd src && python qt_main.py")
    print()
    input("Press Enter to start tests...")
    print()
    
    main()
