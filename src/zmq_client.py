"""
ZMQ Client for 3D Viewer
Receives commands from external script_runner via acquila_zmq server.
"""
from PyQt6.QtCore import QObject, pyqtSignal, QMetaObject, Qt, Q_ARG
import threading
import logging
import queue
from typing import Callable, Optional
from acquila_zmq import AcquilaClient

logger = logging.getLogger(__name__)


class ViewerZMQClient(QObject):
    """
    ZMQ Client for the 3D Viewer.
    Connects to the Acquila ZMQ Server to receive commands.
    """
    # Signals must be defined at class level
    sig_load_data = pyqtSignal(str)   # path
    sig_exec_command = pyqtSignal(str) # command_text
    
    def __init__(self, app_core, server_ip: str = "127.0.0.1", 
                 inbound_port: int = 5555, outbound_port: int = 5556):
        """
        Initialize the ZMQ client.
        """
        super().__init__()
        self.app_core = app_core
        self.server_ip = server_ip
        self.inbound_port = inbound_port
        self.outbound_port = outbound_port
        
        self.client = AcquilaClient(
            server_ip=server_ip,
            inbound_port=inbound_port,
            outbound_port=outbound_port
        )
        self.zmq_thread: Optional[threading.Thread] = None
        self.running = False
        self.on_command_callback: Optional[Callable] = None
        
        # Thread-safe queue for outgoing messages (Feedback/ACKs)
        self.outgoing_queue = queue.Queue()
        
        logger.info(f"ZMQ Client initialized (server: {server_ip}:{inbound_port}/{outbound_port})")

    def send_message(self, data: dict):
        """
        Queue a message to be sent via the ZMQ PUB socket.
        Thread-safe: Can be called from Main Thread.
        """
        self.outgoing_queue.put(data)

    def set_command_callback(self, callback: Callable):
        """
        Set a callback function to be called when a command is received.
        """
        self.on_command_callback = callback
    
    def _handle_command(self, client, command_data: dict) -> str:
        """
        Internal command handler called by ZMQ thread.
        Emits signals to execute on Main Thread.
        """
        try:
            # Direct print to console for debugging
            print(f"\n[ZMQ-CLIENT] RECEIVED MESSAGE: {command_data}")
            
            cmd = command_data.get("command", "")
            arg1 = command_data.get("arg1", "")
            arg2 = command_data.get("arg2", "")
            msg_uuid = command_data.get("uuid", "")
            
            logger.info(f"Received command: {cmd}, arg1={arg1}, arg2={arg2}")
            
            # Helper to queue feedback immediately
            def send_ack(status_msg, status_code="ACK"):
                feedback = {
                    "component": "3dviewer",
                    "command": cmd,
                    "uuid": msg_uuid,
                    "status": status_code,
                    "message": status_msg,
                    "sender": "3dviewer"
                }
                self.send_message(feedback)

            # Handle load_data command
            if cmd == "load_data":
                if not arg1:
                    send_ack("ERROR: No path provided", "ERROR")
                    return "ERROR: load_data requires a path argument"
                
                print(f"[ZMQ-CLIENT] Requesting load_data on MAIN THREAD: {arg1}")
                send_ack("Loading dataset...", "PROCESSING") # Intermediate status
                
                # EMIT SIGNAL to Main Thread
                # We pass the UUID so the main thread can send the final ACK
                self.sig_load_data.emit(f"{arg1}|{msg_uuid}") 
                
                return "SUCCESS"
            
            # Handle AI commands
            else:
                command_text = cmd
                if arg1: command_text += f" {arg1}"
                if arg2: command_text += f" {arg2}"
                
                print(f"[ZMQ-CLIENT] Requesting AI command on MAIN THREAD: {command_text}")
                # For simple commands, we might just let the main thread send the final ACK
                # But sending a "Processing" ACK here keeps the UI responsive
                # send_ack(f"Processing: {command_text}", "PROCESSING")
                
                # EMIT SIGNAL to Main Thread
                self.sig_exec_command.emit(f"{command_text}|{msg_uuid}")
                
                return "SUCCESS"
                    
        except Exception as e:
            error_msg = f"Exception handling command: {str(e)}"
            print(f"[ZMQ-CLIENT] EXCEPTION: {error_msg}")
            logger.exception(error_msg)
            return f"ERROR: {error_msg}"
    
    def start(self, component_name: str = "3dviewer", physical_name: str = "3dviewer"):
        """
        Start the ZMQ client in a background thread.
        """
        if self.running:
            return
        
        self.running = True
        
        def run_zmq():
            import zmq
            import time
            import json
            
            # Using standard ports
            target_ip = "127.0.0.1"
            sub_port = 5555 # LISTENING (Server Out)
            pub_port = 5556 # SENDING (Server In)
            
            ctx = zmq.Context()
            
            # RECEIVER (SUB)
            sub_sock = ctx.socket(zmq.SUB)
            sub_sock.setsockopt_string(zmq.SUBSCRIBE, "") 
            sub_sock.connect(f"tcp://{target_ip}:{sub_port}")
            # Short timeout to allow polling outgoing_queue frequentlhy
            sub_sock.setsockopt(zmq.RCVTIMEO, 50) 
            
            # SENDER (PUB) for Feedback
            pub_sock = ctx.socket(zmq.PUB)
            pub_sock.connect(f"tcp://{target_ip}:{pub_port}")
            
            self.running = True
            print(f"[ZMQ] Client Loop Started. Listening: {sub_port}, Sending: {pub_port}")
            
            while self.running:
                # 1. Process Incoming Messages
                try:
                    msg = sub_sock.recv_string()
                    try:
                        data = json.loads(msg)
                        comp = data.get("component", "")
                        sender = data.get("sender", "")
                        if comp == physical_name and sender != physical_name:
                            self._handle_command(self.client, data)
                    except json.JSONDecodeError:
                        pass
                except zmq.Again:
                    pass # Start polling queue
                except Exception as e:
                    print(f"[ZMQ] Recv error: {e}")
                
                # 2. Process Outgoing Queue
                try:
                    while True: # Drain queue
                        msg_data = self.outgoing_queue.get_nowait()
                        json_str = json.dumps(msg_data)
                        # print(f"[ZMQ] sending: {json_str}")
                        pub_sock.send_string(json_str)
                        self.outgoing_queue.task_done()
                except queue.Empty:
                    pass
                except Exception as e:
                     print(f"[ZMQ] Send error: {e}")

            sub_sock.close()
            pub_sock.close()
            ctx.term()
            print("[ZMQ] Client thread stopped.")

        self.zmq_thread = threading.Thread(
            target=run_zmq,
            daemon=True,
            name="ZMQ-Client-Thread"
        )
        self.zmq_thread.start()
        
        logger.info(f"ZMQ client started (component: {component_name}, physical: {physical_name})")
        print(f"[ZMQ-CLIENT] Client is now LISTENING on physical_name='{physical_name}'")

    
    def stop(self):
        """
        Stop the ZMQ client.
        Note: The acquila_zmq library runs in an infinite loop, so this just marks it as stopped.
        The daemon thread will terminate when the main application exits.
        """
        self.running = False
        logger.info("ZMQ client stopped")
    
    def is_running(self) -> bool:
        """Check if the ZMQ client is running."""
        return self.running and self.zmq_thread is not None and self.zmq_thread.is_alive()
