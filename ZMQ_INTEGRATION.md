# ZMQ Integration for 3D Viewer

This document explains how the 3D Viewer application integrates with the `acquila_zmq` library to receive commands from external script runners.

## Architecture

The 3D Viewer acts as a **ZMQ client** with:
- **Component Name**: `3dviewer`
- **Physical Name**: `3dviewer`

### Components

1. **ZMQ Server** (external, must be running separately)
   - Manages message routing between components
   - Default ports: 5555 (inbound), 5556 (outbound)

2. **3D Viewer Client** (this application)
   - Listens for commands from script_runner
   - Executes commands and sends acknowledgments
   - Updates GUI in response to commands

3. **Script Runner** (external)
   - Sends commands to the 3D Viewer
   - Waits for acknowledgments

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install `acquila_zmq` along with other dependencies.

### 2. Start the ZMQ Server

Before running the 3D Viewer, start the ZMQ server:

```bash
python -m acquila_zmq.server
```

Or if you have a custom server script, run that instead.

### 3. Run the 3D Viewer

```bash
python src/qt_main.py
```

The ZMQ client will automatically start when the application launches. You should see:
```
INFO - ZMQ client started - ready to receive commands
```

## Supported Commands

### 1. Load Data

Load a dataset from a specified path.

**Command**: `load_data`  
**Arguments**: 
- `arg1`: Path to the data folder

**Example**:
```python
client.send_command(
    component="3dviewer",
    command="load_data",
    arg1="/path/to/data",
    wait_for="ACK"
)
```

### 2. AI Commands

All existing AI commands are supported through the ZMQ interface:

- **Rendering Mode**: `set rendering mode to <mode>`
  - Modes: MIP, Average, DVR, Isosurface
  
- **Density**: `set density to <value>`
  - Value: 0.1 to 50.0

- **Transfer Function**: `set transfer function to <name>`
  - Names: Grayscale, Jet, Hot, Cool, Viridis, Plasma, etc.

- **Rotation**: `rotate <degrees>`
  - Degrees: any number

- **Zoom**: `zoom in`, `zoom out`, `zoom to <level>`

- **Slice Navigation**: `slice <axis> <index>`
  - Axis: x, y, z
  - Index: 0 to max dimension

**Example**:
```python
# Change rendering mode
client.send_command(
    component="3dviewer",
    command="set rendering mode to MIP",
    wait_for="ACK"
)

# Adjust density
client.send_command(
    component="3dviewer",
    command="set density to 5",
    wait_for="ACK"
)
```

## Message Protocol

### Request Format

The script_runner sends commands in the following format:

```python
{
    "component": "3dviewer",      # Target component
    "command": "load_data",        # Command name
    "arg1": "/path/to/data",       # First argument (optional)
    "arg2": "",                    # Second argument (optional)
    "reply_type": "SENT"           # Message type
}
```

### Response Flow

1. **RCV Acknowledgment**: Sent immediately when command is received
2. **Feedback** (optional): Progress updates during long operations
3. **ACK/ERR**: Final result when command completes
   - `ACK`: Command succeeded
   - `ERR`: Command failed (includes error message)

## Testing

Use the provided test script to verify the integration:

```bash
python test_zmq_commands.py
```

This script demonstrates:
- Loading a dataset
- Changing rendering modes
- Adjusting parameters
- Executing AI commands

## GUI Integration

When commands are received via ZMQ:

1. **Command Log**: Shows ZMQ commands in purple with results
2. **Auto-Update**: GUI elements automatically sync with command results
3. **View Refresh**: All viewports update after successful commands

Example log output:
```
ZMQ: load_data
Result: Successfully loaded dataset from: /path/to/data
```

## Troubleshooting

### ZMQ Client Not Starting

**Symptom**: No "ZMQ client started" message in logs

**Solutions**:
- Verify `acquila_zmq` is installed: `pip show acquila_zmq`
- Check that ZMQ server is running
- Review console for error messages

### Commands Not Received

**Symptom**: Script_runner sends commands but viewer doesn't respond

**Solutions**:
- Verify component name is exactly `"3dviewer"`
- Check server IP and ports match (default: 127.0.0.1:5555/5556)
- Ensure ZMQ server is running before starting the viewer
- Check firewall settings

### Command Execution Fails

**Symptom**: Commands received but return ERROR

**Solutions**:
- Check command syntax matches AI command format
- Verify file paths are absolute and exist
- Review error message in the response
- Check application logs for detailed error information

## Implementation Details

### Thread Safety

- ZMQ client runs in a background daemon thread
- GUI updates use `QTimer.singleShot(0, ...)` to ensure main thread execution
- Command callbacks are thread-safe

### Component Registration

The client registers with both component and physical names set to `"3dviewer"`:

```python
self.zmq_client.start(component_name="3dviewer", physical_name="3dviewer")
```

This ensures the client receives messages addressed to either field.

### Error Handling

- Exceptions in command handlers are caught and returned as ERROR responses
- GUI remains responsive even if commands fail
- Detailed error messages logged for debugging

## Example Integration

Here's a complete example of a script_runner sending commands:

```python
from acquila_zmq import AcquilaClient

# Initialize client
client = AcquilaClient(server_ip="127.0.0.1")

# Load data
result = client.send_command(
    component="3dviewer",
    command="load_data",
    arg1="c:/data/volume",
    wait_for="ACK",
    timeout=30
)
print(f"Load result: {result}")

# Configure visualization
client.send_command(
    component="3dviewer",
    command="set rendering mode to MIP",
    wait_for="ACK"
)

client.send_command(
    component="3dviewer",
    command="set transfer function to Hot",
    wait_for="ACK"
)

client.send_command(
    component="3dviewer",
    command="set density to 8",
    wait_for="ACK"
)
```

## Future Enhancements

Potential improvements to the ZMQ integration:

1. **Bidirectional Communication**: Send viewer state updates to script_runner
2. **Screenshot Export**: Command to capture and send rendered images
3. **Batch Commands**: Execute multiple commands in sequence
4. **State Queries**: Request current viewer state (rendering mode, density, etc.)
5. **Event Notifications**: Notify script_runner when user changes settings
