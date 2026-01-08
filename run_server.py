from acquila_zmq import AcquilaServer
import json

class VerboseServer(AcquilaServer):
    def start(self):
        import zmq
        # Set a timeout so the loop doesn't block forever and can catch Ctrl+C
        self.socket_in.setsockopt(zmq.RCVTIMEO, 1000) 
        
        self.running = True
        print("--- VERBOSE ROUTING ENABLED ---")
        print(f"Server receiving on: 5556")
        print(f"Server broadcasting on: 5555")
        print("Waiting for messages... (Press Ctrl+C to stop)\n")
        
        try:
            while self.running:
                try:
                    # Receive message (now waits max 1 second)
                    msg_str = self.socket_in.recv_string()
                except zmq.Again:
                    # No message received in the last second, just loop again
                    continue
                
                try:
                    data = json.loads(msg_str)
                    comp = data.get('component', 'unknown')
                    cmd = data.get('command', 'unknown')
                    uuid = data.get('uuid', 'no-uuid')
                    print(f"[SERVER] Routed: {comp} -> {cmd} (ID: {uuid[:8]})")
                except:
                    print(f"[SERVER] Routed raw message: {msg_str[:100]}...")
                
                self.socket_out.send_string(msg_str)
        except KeyboardInterrupt:
            print("\n[SERVER] Stopping via Ctrl+C...")
        finally:
            self.stop()

if __name__ == "__main__":
    server = VerboseServer()
    server.start()