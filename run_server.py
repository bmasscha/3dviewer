"""
ZMQ Server for 3D Viewer - Acquila Protocol
Runs the message relay server for ZMQ communication between components.

Usage:
    python run_server.py

The server routes messages between clients (script_runner, 3dviewer, etc.)
"""
from acquila_zmq import AcquilaServer
import signal
import sys


def main():
    print("=" * 60)
    print("Acquila ZMQ Server")
    print("=" * 60)
    print()
    print("Default ports:")
    print("  Outbound (Server -> Clients): 5555")
    print("  Inbound  (Clients -> Server): 5556")
    print()
    print("Press Ctrl+C to stop the server...")
    print()
    
    # Create and start the server
    server = AcquilaServer()
    
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n[SERVER] Shutting down...")
        server.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start the server (blocking)
    try:
        server.start()
    except Exception as e:
        print(f"[SERVER] Error: {e}")
        server.stop()


if __name__ == "__main__":
    main()