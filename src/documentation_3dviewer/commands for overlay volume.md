# Overlay Volume Commands

This document lists the commands available for controlling the **Overlay (Secondary) Volume** in the 3D Viewer. These commands can be used via the **AI Command Panel** or via **ZMQ Integration**.

## AI Command Panel Usage

To target the Overlay volume instead of the Primary one, simply include the keyword **"overlay"** or **"secondary"** in your command.

### Rendering & Appearance

| Action            | Example Phrase               | Description                                                                   |
| :---------------- | :--------------------------- | :---------------------------------------------------------------------------- |
| **Set Mode**      | "set mode to mip overlay"    | Changes the rendering technique (mip, volume, cinematic, mida, shaded, edge). |
| **Set TF**        | "set tf to plasma overlay"   | Applies a color/opacity transfer function (e.g., viridis, plasma, ct_bone).   |
| **Set Threshold** | "set threshold 0.15 overlay" | Sets the transparency cutoff (0.0 to 1.0).                                    |
| **Set Density**   | "set density 100 overlay"    | Adjusts the overall intensity/opacity of the volume (recommended: 10-200).    |
| **Set Opacity**   | "set opacity 0.5 overlay"    | Global multiplier for the overlay's visibility.                               |

### Data Management

| Action | Example Phrase | Description |
| :--- | :--- | :--- |
| **Load** | "load C:/path/to/data overlay" | Loads a second dataset into the overlay slot. |
| **Crop** | "crop x 0.2 0.8 overlay" | Clips the overlay volume along the specified axis (x, y, or z). |

### spatial Alignment

These commands only affect the overlay volume's position and size relative to the primary volume.

| Action | Example Phrase | Description |
| :--- | :--- | :--- |
| **Set Offset** | "set overlay offset x 0.1" | Shifts the overlay along an axis (values in normalized 0.0-1.0 coords). |
| **Set Scale** | "set overlay scale 1.2" | Uniformly scales the overlay volume. |
| **Fit Overlay** | "fit overlay" | Automatically scales the overlay to match the physical Z-dimension of the primary volume. |
| **Center Overlay** | "center overlay" | Moves the overlay to the approximate center of the viewing area. |

---

## ZMQ Integration (JSON)

For programmatic control, use the standard command names and specify `arg2` as `"1"` (or `1`) to target the overlay slot.

### Example: Setting Overlay Threshold

```json
{
    "component": "3dviewer",
    "command": "set_threshold",
    "arg1": "0.15",
    "arg2": "1"
}
```

### Supported JSON Parameters

The following commands support the `arg2` slot parameter:

- `set_rendering_mode` (or `set_mode`)
- `set_transfer_function` (or `set_tf`)
- `set_threshold`
- `set_density`
- `load_data` (triggers overlay load if requested)
- `crop`
