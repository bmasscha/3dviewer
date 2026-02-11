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
from zmq_command_processor import ZMQCommandProcessor

logger = logging.getLogger(__name__)


class ViewerZMQClient(QObject):
    """
    ZMQ Client for the 3D Viewer.
    Connects to the Acquila ZMQ Server to receive commands.
    """
    # Signals must be defined at class level
    sig_load_data = pyqtSignal(dict)
    sig_set_tf = pyqtSignal(dict)
    sig_exec_command = pyqtSignal(dict)
    sig_command_processed = pyqtSignal(str, bool, str) # cmd, success, msg
    
    def __init__(self, app_core, server_ip: str = "127.0.0.1", 
                 inbound_port: int = 50001, outbound_port: int = 50001):
        """
        Initialize the ZMQ client.
        """
        super().__init__()
        self.app_core = app_core
        self.server_ip = server_ip
        self.inbound_port = inbound_port
        self.outbound_port = outbound_port
        
        # Initialize the command processor
        self.command_processor = ZMQCommandProcessor(app_core)
        
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
        Uses ZMQCommandProcessor for structured command handling.
        Emits signals for commands that require Main Thread execution.
        """
        try:
            raw_cmd = command_data.get("command", "")
            cmd = str(raw_cmd).strip().lower()
            arg1 = command_data.get("arg1", "")
            arg2 = command_data.get("arg2", "")
            comp_type = command_data.get("comp_type", "other")
            comp_phys = command_data.get("comp_phys", "3dviewer")
            component = command_data.get("component", "3dviewer")
            tick_count = command_data.get("tick count", 0)
            # acquila_zmq uses uppercase 'UUID', handle both cases
            msg_uuid = command_data.get("UUID", "") or command_data.get("uuid", "")
            
            # Normalize common variants for high-level routing
            if cmd in ["load data", "load"]: cmd = "load_data"
            if cmd in ["set tf", "set_tf", "set transfer function"]: cmd = "set_transfer_function"

            logger.info(f"Received command: {cmd}, arg1={arg1}, arg2={arg2}")
            
            # Helper to queue feedback/ACK via ZMQ
            def send_feedback(status_msg, reply_type="ACK"):
                feedback = {
                    "component": component,
                    "comp_phys": comp_phys,
                    "command": raw_cmd,
                    "arg1": arg1,
                    "arg2": arg2,
                    "reply": status_msg,
                    "reply type": reply_type,
                    "comp_type": comp_type,
                    "tick count": tick_count,
                    "UUID": msg_uuid  
                }
                self.send_message(feedback)

            # 1. IMMEDIATE RCV (Received) acknowledgment
            send_feedback("Command received", "RCV")

            # Prepare metadata for signals
            metadata = {
                "command": cmd,
                "raw_command": raw_cmd,
                "arg1": arg1,
                "arg2": arg2,
                "UUID": msg_uuid,
                "comp_phys": comp_phys,
                "component": component,
                "comp_type": comp_type,
                "tick_count": tick_count
            }
            
            # load_data requires Main Thread for OpenGL operations
            if cmd == "load_data":
                if not arg1:
                    send_feedback("ERROR: No path provided", "ERROR")
                    return "ERROR: load_data requires a path argument"
                
                print(f"[ZMQ-CLIENT] Requesting load_data on MAIN THREAD: {arg1}")
                send_feedback("Loading dataset...", "FDB")
                
                # EMIT SIGNAL to Main Thread
                self.sig_load_data.emit({**metadata, "path": arg1}) 
                return "SUCCESS"

            # set_transfer_function requires Main Thread for GL texture updates
            if cmd == "set_transfer_function":
                if not arg1:
                    send_feedback("ERROR: No transfer function name provided", "ERROR")
                    return "ERROR: Missing TF name"
                
                print(f"[ZMQ-CLIENT] Requesting set_transfer_function on MAIN THREAD: {arg1}")
                send_feedback("Setting transfer function...", "FDB")
                
                slot_val = int(arg2) if arg2 and str(arg2).isdigit() else 0
                self.sig_set_tf.emit({**metadata, "name": arg1, "slot": slot_val})
                return "SUCCESS"
            
            # All other commands: generic AI command support?
            if cmd in ["exec", "command"]:
                if not arg1:
                    send_feedback("ERROR: No command text provided", "ERROR")
                    return "ERROR: Missing command text"
                
                print(f"[ZMQ-CLIENT] Requesting AI command on MAIN THREAD: {arg1}")
                send_feedback("Executing AI command...", "FDB")
                self.sig_exec_command.emit({**metadata, "text": arg1})
                return "SUCCESS"

            # All other structured commands: use ZMQCommandProcessor
            result = self.command_processor.process(command_data)
            
            success = result.get("success", False)
            msg = result.get("message", "")
            
            # Emit signal for thread-safe UI synchronization
            self.sig_command_processed.emit(cmd, success, msg)
                
            if success:
                send_feedback(msg, "ACK")
                return "SUCCESS"
            else:
                send_feedback(msg, "ERROR")
                return f"ERROR: {msg}"
                    
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
            
            # Use instance variables instead of hardcoded defaults
            target_ip = self.server_ip
            sub_port = self.inbound_port   # LISTENING (Server Out)
            pub_port = self.outbound_port  # SENDING (Server In)
            
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
                        # print(f"[ZMQ] SENDING ACK: {json_str[:200]}")
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
