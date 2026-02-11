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
    parser = argparse.ArgumentParser(description="Acquila ZMQ Server")
    parser.add_argument("--out-port", type=int, default=50003, help="Port to send commands on (default: 50003)")
    parser.add_argument("--in-port", type=int, default=50002, help="Port to receive feedback on (default: 50002)")
    args = parser.parse_args()
    print()
    print("Press Ctrl+C to stop the server...")
    print()
    
    # Create and start server
    # Outbound=50003 (Viewer's Inbound), Inbound=50002 (Viewer's Outbound)
    server = AcquilaServer(outbound_port=50003, inbound_port=50002)
    
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