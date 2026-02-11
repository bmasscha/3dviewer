# 3D Volume Viewer

A PyQt6-based 3D volume visualization application for CT/X-ray reconstruction data with OpenGL rendering.

## Project Overview

This is a scientific volume viewer designed for viewing CT scan reconstructions. It provides:

- Orthogonal slice views (Axial, Coronal, Sagittal)
- 3D volume rendering with ray marching
- Multiple rendering modes (MIP, Volume Rendering, Cinematic, MIDA, Shaded, Edge Enhanced)
- Transfer function editor with color maps
- AI command interpretation (via Ollama)
- ZMQ-based external control interface
- Image/video export capabilities

## Tech Stack

- **Python 3.x** with virtual environment in `.venv/`
- **PyQt6** - GUI framework
- **PyOpenGL** - OpenGL bindings for volume rendering
- **NumPy** - Array operations
- **tifffile** - TIFF stack loading
- **h5py** - HDF5 file support
- **scipy** - Image filters (Gaussian, Median, Bilateral, NLM, Total Variation)
- **glm (PyGLM)** - Math library for 3D transformations
- **pyzmq** - ZMQ messaging for external control
- **imageio** - Video export

## Directory Structure

```text
src/
├── 3dviewer_gui.py      # Main PyQt6 application window
├── app_core.py          # Core application state and logic
├── renderer.py          # OpenGL texture management and shader programs
├── volume_loader.py     # TIFF/HDF5 volume loading with geometry parsing
├── camera.py            # 3D camera with quaternion-based orientation
├── transfer_functions.py # Color map definitions
├── filters.py           # 3D image filtering (CPU-based)
├── command_interpreter.py # AI/NLP command parsing (Ollama integration)
├── zmq_client.py        # ZMQ client for external messaging
├── zmq_command_processor.py # ZMQ command handling
├── shaders/
│   ├── slice.vert/frag  # 2D slice rendering
│   ├── raymarch.vert/frag # 3D volume ray marching
│   └── vpc_filter.frag  # Virtual phase contrast post-processing
└── widgets/
    ├── gl_view.py       # OpenGL viewport widget
    ├── tf_editor.py     # Transfer function curve editor
    └── import_dialog.py # Advanced import options dialog
```

## Running the Application

```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Run the viewer
python src/3dviewer_gui.py
```

## Key Classes

- **MainWindow** (`3dviewer_gui.py`) - Main Qt window with UI setup
- **AppCore** (`app_core.py`) - Central state management, shader loading, dataset loading
- **VolumeRenderer** (`renderer.py`) - OpenGL 3D texture creation and binding
- **VolumeLoader** (`volume_loader.py`) - File I/O, rescaling, binning, geometry parsing
- **Camera** (`camera.py`) - View/projection matrices, quaternion rotation
- **GLViewWidget** (`widgets/gl_view.py`) - QOpenGLWidget for each viewport

## Rendering Pipeline

1. Volume data loaded as 3D texture (R16 or R8 format)
2. Transfer function as 1D RGBA texture
3. Ray marching shader samples volume along view rays
4. Lighting calculations in fragment shader (Phong model)
5. Optional VPC (Virtual Phase Contrast) post-processing

## Data Formats

- **Input**: TIFF stacks, HDF5 files (`.h5`)
- **Geometry**: Reads XRE settings files (`data settings xre recon.txt`, `geometry recon.txt`) for voxel size, SOD/SDD
- **Output**: PNG images, MP4 videos

## AI Command Panel

The GUI includes an AI command input panel (left sidebar) that accepts natural language commands via Ollama:

**Example commands:**

- `zoom in` / `zoom out` - Adjust camera distance
- `rotate 90` / `rotate x 45` - Rotate view by degrees
- `reset` - Reset camera to default view
- `set mode mip` / `cinematic` / `volume` - Change rendering mode
- `set tf viridis` / `plasma` / `grayscale` - Change transfer function
- `set threshold 0.1` / `set density 50` - Adjust rendering parameters
- `set slice x 50%` - Move slice position
- `overlay set tf plasma` - Control overlay volume settings
- `crop x 0.2 0.8` - Set clipping planes

Commands are processed by `CommandInterpreter` which uses Ollama for NLP parsing, then executed by `AppCore.execute_command_text()`.

## ZMQ Interface

The viewer listens on ports 50003 (inbound) and 50002 (outbound) for external control:

- `load_data` - Load a dataset from path
- `set_transfer_function` - Change colormap
- AI command strings for camera/rendering control

## Development Notes

- OpenGL context sharing is enabled via `AA_ShareOpenGLContexts`
- Shaders are loaded from `src/shaders/` at runtime
- Filter operations run on CPU in background threads with progress callbacks
- Camera uses quaternion-based orientation for smooth rotation

## Agent info

- run all terminal commands in the virtual environment .venv
- answer with short and concise responses
- make clear what you think is the optimal way to go
- if complicated, break it down into sub tasks
- if large changes are required recommend the user to branch the code
