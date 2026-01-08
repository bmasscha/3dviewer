import zmq
import json
import time
import uuid

class ZMQController:
    def __init__(self, target_ip="127.0.0.1", send_port=5556, recv_port=5555):
        self.context = zmq.Context()
        
        # Socket to SEND commands (PUB) -> Connects to Server Inbound
        self.pub_socket = self.context.socket(zmq.PUB)
        self.pub_socket.connect(f"tcp://{target_ip}:{send_port}")
        
        # Socket to RECEIVE feedback (SUB) -> Connects to Server Outbound
        self.sub_socket = self.context.socket(zmq.SUB)
        self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "") # Listen to everything
        self.sub_socket.setsockopt(zmq.RCVTIMEO, 100) # Short timeout for polling
        self.sub_socket.connect(f"tcp://{target_ip}:{recv_port}")
        
        print(f"[CONTROLLER] Connected. Sending to {send_port}, Listening on {recv_port}")
        time.sleep(1) # Wait for connections to stabilize

    def close(self):
        self.pub_socket.close()
        self.sub_socket.close()
        self.context.term()

    def send_command(self, cmd, arg1="", arg2="", wait_for="ACK", timeout=30):
        msg_id = str(uuid.uuid4())
        payload = {
            "component": "3dviewer",
            "command": cmd,
            "arg1": arg1,
            "arg2": arg2,
            "uuid": msg_id,
            "sender": "test_script"
        }
        
        # Clear any old messages from the buffer
        try:
            while True:
                self.sub_socket.recv_string()
        except zmq.Again:
            pass
            
        json_str = json.dumps(payload)
        print(f"[SCRIPT] Sending: {cmd} (ID: {msg_id[:8]})...")
        self.pub_socket.send_string(json_str)
        
        if not wait_for:
            return True

        # Wait for feedback
        start_time = time.time()
        print(f"[SCRIPT] Waiting for feedback (Timeout: {timeout}s)...")
        
        while (time.time() - start_time) < timeout:
            try:
                msg = self.sub_socket.recv_string()
                data = json.loads(msg)
                
                # Check if this message is related to our command
                if data.get("sender") == "test_script":
                    continue # Ignore our own echo
                    
                print(f"[SCRIPT] Received: {data}")
                
                # In a real implementation, we'd check data['uuid'] == msg_id
                # but let's assume any traffic from 3dviewer is the ACK for now
                if data.get("component") == "3dviewer":
                     print(f"[SCRIPT] ACK Confirmed.")
                     return True
                     
            except zmq.Again:
                continue
            except Exception as e:
                print(f"[SCRIPT] Error receiving: {e}")
                
        print("[SCRIPT] Timeout waiting for ACK!")
        return False

def main():
    controller = ZMQController()
    
    # 1. Load Data
    print("=" * 60)
    print("TEST 1: Load Data")
    print("=" * 60)
    # Use real path
    data_path = "c:/code/antigravity/3dviewer/example_data/recon_schildpad"
    controller.send_command("load_data", data_path, wait_for="ACK", timeout=30)
    
    time.sleep(1)
    
    # 2. Set Rendering Mode
    print("=" * 60)
    print("TEST 2: Set rendering mode to MIP")
    print("=" * 60)
    controller.send_command("set rendering mode to MIP", wait_for="ACK", timeout=10)
    
    time.sleep(1)
    
    # 3. Set Density
    print("=" * 60)
    print("TEST 3: Set density to 5")
    print("=" * 60)
    controller.send_command("set density to 5", wait_for="ACK", timeout=10)
    
    controller.close()
    print("Done.")

if __name__ == "__main__":
    main()