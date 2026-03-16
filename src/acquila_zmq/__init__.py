"""
Acquila ZMQ Communication Library

A Python library for ZMQ-based communication between Acquila components.
Provides server-client architecture with feedback support and command tracking.
"""

__version__ = "1.0.1"
__author__ = "Acquila Team"
__all__ = ["AcquilaServer", "AcquilaClient", "DEFAULT_OUTBOUND_PORT", "DEFAULT_INBOUND_PORT"]

import zmq
import json
import uuid
import time
import threading

# Default ports
DEFAULT_OUTBOUND_PORT = 5555
DEFAULT_INBOUND_PORT = 5556

class AcquilaServer:
    """
    Emulates the Acquila Main Program (Server).
    """
    def __init__(self, outbound_port=DEFAULT_OUTBOUND_PORT, inbound_port=DEFAULT_INBOUND_PORT):
        self.outbound_port = outbound_port
        self.inbound_port = inbound_port
        self.context = zmq.Context()
        self.socket_out = None
        self.socket_in = None
        self.running = False
        self.command_queue = {} # Tracks active commands by UUID
        self.lock = threading.Lock() # Protects command_queue
        self.on_message_callback = None # Optional callback(msg_json)

    def _setup_sockets(self):
        self.socket_out = self.context.socket(zmq.PUB)
        self.socket_out.bind(f"tcp://*:{self.outbound_port}")
        self.socket_in = self.context.socket(zmq.SUB)
        self.socket_in.bind(f"tcp://*:{self.inbound_port}")
        self.socket_in.setsockopt_string(zmq.SUBSCRIBE, "") 
        print(f"Acquila Server sockets bound on {self.inbound_port} (in) / {self.outbound_port} (out)")

    def start(self, on_message=None):
        self.on_message_callback = on_message
        self._setup_sockets()
        self.running = True
        
        poller = zmq.Poller()
        poller.register(self.socket_in, zmq.POLLIN)
        
        try:
            while self.running:
                socks = dict(poller.poll(timeout=100)) # Poll with 100ms timeout
                if self.socket_in in socks and socks[self.socket_in] == zmq.POLLIN:
                    try:
                        msg = self.socket_in.recv_string()
                        print(f"[SERVER] RAW RECV: {msg}") # Diagnostic log
                        
                        # --- Command Queue Logic ---
                        try:
                            data = json.loads(msg)
                            r_type = data.get("reply type")
                            uuid_val = data.get("UUID")

                            if uuid_val:
                                with self.lock:
                                    if r_type == "SENT":
                                        data["status"] = "PENDING"
                                        self.command_queue[uuid_val] = data
                                        print(f"[SERVER] Queueing: {data.get('command')} for {data.get('component')}")
                                    
                                    elif r_type == "RCV":
                                        if uuid_val in self.command_queue:
                                            self.command_queue[uuid_val]["status"] = "RUNNING"
                                            print(f"[SERVER] Running: {uuid_val}")
                                            
                                    elif r_type in ["ACK", "ERR"]:
                                        if uuid_val in self.command_queue:
                                            print(f"[SERVER] Finished: {uuid_val} ({r_type})")
                                            self.command_queue[uuid_val]["status"] = "FINISHED"
                                            self.command_queue[uuid_val]["reply type"] = r_type
                                            self.command_queue[uuid_val]["reply"] = data.get("reply", "")
                                            self.command_queue[uuid_val]["finish_time"] = time.time()
                            
                            if self.on_message_callback:
                                self.on_message_callback(data)
                                
                        except json.JSONDecodeError:
                            print(f"[SERVER] Raw string received: {msg}")
                            if self.on_message_callback:
                                self.on_message_callback({"raw": msg})
                        # ---------------------------

                        # Simply relay the message to all subscribers
                        self.socket_out.send_string(msg)
                    except zmq.ZMQError as e:
                        print(f"ZMQ Receive error: {e}")
                        break
        except Exception as e:
            print(f"Server execution error: {e}")
        finally:
            self.stop()

    def stop(self):
        self.running = False
        if self.socket_out:
            try:
                self.socket_out.close(linger=0)
            except: pass
            self.socket_out = None
        if self.socket_in:
            try:
                self.socket_in.close(linger=0)
            except: pass
            self.socket_in = None
        print("Acquila Server stopped.")

class AcquilaClient:
    def __init__(self, server_ip="127.0.0.1", outbound_port=DEFAULT_OUTBOUND_PORT, inbound_port=DEFAULT_INBOUND_PORT):
        self.context = zmq.Context()
        self.uuid = str(uuid.uuid4())
        
        # Socket to SEND commands (connects to Server Inbound)
        self.socket_send = self.context.socket(zmq.PUB)
        self.socket_send.connect(f"tcp://{server_ip}:{inbound_port}")
        
        # Socket to RECEIVE (connects to Server Outbound)
        self.socket_recv = self.context.socket(zmq.SUB)
        self.socket_recv.connect(f"tcp://{server_ip}:{outbound_port}")
        self.socket_recv.setsockopt_string(zmq.SUBSCRIBE, "") 
        
        print(f"[CLIENT] Connected to {server_ip}: {inbound_port}(in)/{outbound_port}(out)")
        time.sleep(1.0) # Increased wait for ZMQ PUB/SUB handshake

    def _create_payload(self, component, comp_phys, command, arg1, arg2, reply, reply_type, uuid_val=None):
        return {
            "component": str(component),
            "comp_phys": str(comp_phys),
            "command": str(command),
            "arg1": str(arg1),
            "arg2": str(arg2),
            "reply": str(reply),
            "reply type": str(reply_type), 
            "comp_type": "python_client",
            "tick count": int(time.time() * 1000),
            "UUID": uuid_val if uuid_val else str(uuid.uuid4())
        }

    def send_feedback(self, original_command_data, feedback_msg):
        payload = self._create_payload(
            component=original_command_data.get("component"),
            comp_phys=original_command_data.get("comp_phys"),
            command=original_command_data.get("command"),
            arg1=original_command_data.get("arg1"),
            arg2=original_command_data.get("arg2"),
            reply=feedback_msg,
            reply_type="FDB",
            uuid_val=original_command_data.get("UUID")
        )
        self.socket_send.send_string(json.dumps(payload))

    def send_command(self, component, command, arg1="", arg2="", wait_for="ACK", timeout_ms=10000):
        """
        Standard command sending with improved logging and slightly longer default timeout.
        """
        my_uuid = str(uuid.uuid4())
        payload = self._create_payload(component, "", command, arg1, arg2, "", "SENT", my_uuid)
        
        print(f"[CLIENT] Sending: {command} to {component} (UUID: {my_uuid})")
        self.socket_send.send_string(json.dumps(payload))

        if wait_for == "no wait": return None

        start_time = time.time() * 1000
        while (time.time() * 1000 - start_time) < timeout_ms:
            try:
                rec_string = self.socket_recv.recv_string(flags=zmq.NOBLOCK)
                rec_json = json.loads(rec_string)

                if rec_json.get("UUID") == my_uuid:
                    r_type = rec_json.get("reply type")
                    print(f"   <-- Received response: {r_type} ('{rec_json.get('reply')}')")
                    
                    if r_type == "FDB":
                        if wait_for == "FDB": return rec_json
                    
                    elif r_type == wait_for:
                        return rec_json
                    
                    elif wait_for == "ACK" and r_type == "ACK":
                        return rec_json
                        
            except zmq.Again:
                time.sleep(0.01)
            except Exception as e:
                print(f"[CLIENT] Receive error: {e}")
        
        print(f"[CLIENT] Timeout waiting for {wait_for} (UUID: {my_uuid})")
        return None

    def send_command_until(self, component, command, expected_feedback, interval_ms=500, timeout_ms=30000):
        print(f"[CLIENT] REPEAT UNTIL '{expected_feedback}'...")
        start_time = time.time() * 1000
        
        while (time.time() * 1000 - start_time) < timeout_ms:
            response = self.send_command(component, command, wait_for="ACK", timeout_ms=2000)
            if response:
                if response.get("reply") == expected_feedback:
                    return True
            time.sleep(interval_ms / 1000.0)
        return False

    def listen_and_process(self, physical_name, callback_function):
        print(f"[COMPONENT] Listening as: {physical_name}")
        
        poller = zmq.Poller()
        poller.register(self.socket_recv, zmq.POLLIN)
        
        try:
            while True:
                # Use a small timeout so the interpreter can catch KeyboardInterrupt (Ctrl-C)
                socks = dict(poller.poll(timeout=200)) 
                
                if self.socket_recv in socks:
                    msg = self.socket_recv.recv_string()
                    data = json.loads(msg)
                    
                    if data.get("reply type") == "SENT":
                        tgt_phys = data.get("comp_phys")
                        tgt_abs = data.get("component")
                        
                        if tgt_phys == physical_name or tgt_abs == physical_name:
                            print(f"[COMPONENT] Processing: {data.get('command')}")
                            # 1. Send RCV
                            ack_payload = data.copy()
                            ack_payload["reply type"] = "RCV"
                            self.socket_send.send_string(json.dumps(ack_payload))
                            
                            # 2. Execute Logic
                            try:
                                result = callback_function(self, data)
                                ack_payload["reply type"] = "ACK"
                                ack_payload["reply"] = str(result)
                            except Exception as e:
                                ack_payload["reply type"] = "ERR"
                                ack_payload["reply"] = str(e)
                            
                            # 3. Send Final ACK/ERR
                            self.socket_send.send_string(json.dumps(ack_payload))
        except KeyboardInterrupt:
            print(f"\n[COMPONENT] Stop requested (Ctrl-C). Shutting down {physical_name}...")
        except Exception as e:
            print(f"[COMPONENT] Loop error: {e}")
            time.sleep(0.1)
