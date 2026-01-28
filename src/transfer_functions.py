import numpy as np
try:
    import colorcet as cc
    HAS_COLORCET = True
except ImportError:
    HAS_COLORCET = False

def color_to_rgba(color_val, alpha: float = 1.0) -> list:
    if isinstance(color_val, str):
        hex_str = color_val.lstrip('#')
        return [int(hex_str[i:i+2], 16) / 255.0 for i in (0, 2, 4)] + [alpha]
    elif isinstance(color_val, (list, tuple, np.ndarray)):
        # Assume it's already normalized RGB (0-1)
        return list(color_val)[:3] + [alpha]
    return [0.0, 0.0, 0.0, alpha]

def is_categorical(name: str) -> bool:
    """Returns True if the colormap should use sharp (nearest) transitions."""
    return "glasbey" in name.lower()

def get_colormap(name: str, size: int = 256, alpha_ramp: np.ndarray = None) -> np.ndarray:
    """
    Returns a (size, 4) float32 numpy array representing the colormap.
    Slightly better than raw linear interpolation for some maps.
    If alpha_ramp is provided, it overrides the default alpha values.
    """
    t = np.linspace(0, 1, size)
    
    if name == "grayscale":
        # R, G, B, A
        # A simple ramp
        a = t if alpha_ramp is None else alpha_ramp
        arr = np.column_stack([t, t, t, a])
        return arr.astype(np.float32)

    elif name == "viridis":
        # Approximate Viridis
        # Keypoints from matplotlib's viridis
        # 0.0: 0.267, 0.005, 0.329
        # 0.25: 0.283, 0.261, 0.490
        # 0.5: 0.128, 0.543, 0.536
        # 0.75: 0.596, 0.816, 0.252
        # 1.0: 0.993, 0.906, 0.144
        
        kp_pos = [0.0, 0.25, 0.5, 0.75, 1.0]
        kp_r = [0.267, 0.283, 0.128, 0.596, 0.993]
        kp_g = [0.005, 0.261, 0.543, 0.816, 0.906]
        kp_b = [0.329, 0.490, 0.536, 0.252, 0.144]
        
        r = np.interp(t, kp_pos, kp_r)
        g = np.interp(t, kp_pos, kp_g)
        b = np.interp(t, kp_pos, kp_b)
        a = t if alpha_ramp is None else alpha_ramp
        
        return np.column_stack([r, g, b, a]).astype(np.float32)

    elif name == "plasma":
        # Approximate Plasma
        kp_pos = [0.0, 0.25, 0.5, 0.75, 1.0]
        kp_r = [0.050, 0.420, 0.798, 0.958, 0.940]
        kp_g = [0.029, 0.030, 0.258, 0.575, 0.975]
        kp_b = [0.529, 0.650, 0.490, 0.260, 0.130]
        
        r = np.interp(t, kp_pos, kp_r)
        g = np.interp(t, kp_pos, kp_g)
        b = np.interp(t, kp_pos, kp_b)
        a = t if alpha_ramp is None else alpha_ramp
        return np.column_stack([r, g, b, a]).astype(np.float32)

    elif name == "medical":
        # Good for bone CT: Transparent low values, reddish muscle
        # 0.0 - 0.1: Transparent
        # 0.2: Reddish muscle
        # 0.5: White Bone
        
        kp_pos = [0.0, 0.1, 0.2, 0.4, 0.1, 1.0] # Simpler ramp might be safer
        
        # New simplified medical
        # 0.0: Black
        # 0.2: Dark Red
        # 0.5: Skin-ish
        # 0.8: Bone (White)
        
        kp_pos = [0.0, 0.2, 0.5, 0.8, 1.0]
        kp_r = [0.0, 0.4, 0.9, 0.95, 1.0]
        kp_g = [0.0, 0.0, 0.6, 0.90, 1.0]
        kp_b = [0.0, 0.0, 0.5, 0.85, 1.0]
        kp_a = [0.0, 0.05, 0.2, 0.8, 1.0] # Opacity ramp
        
        r = np.interp(t, kp_pos, kp_r)
        g = np.interp(t, kp_pos, kp_g)
        b = np.interp(t, kp_pos, kp_b)
        a = np.interp(t, kp_pos, kp_a) if alpha_ramp is None else alpha_ramp
        
        return np.column_stack([r, g, b, a]).astype(np.float32)

    elif name == "ct_bone":
        # CT Bone: Transparent -> Yellow/Ivory -> White
        # Looks good for high density structures
        kp_pos = [0.0, 0.4, 0.6, 1.0]
        kp_r = [0.0, 0.9, 1.0, 1.0]
        kp_g = [0.0, 0.8, 0.95, 1.0]
        kp_b = [0.0, 0.5, 0.8, 1.0]
        
        r = np.interp(t, kp_pos, kp_r)
        g = np.interp(t, kp_pos, kp_g)
        b = np.interp(t, kp_pos, kp_b)
        a = t if alpha_ramp is None else alpha_ramp
        return np.column_stack([r, g, b, a]).astype(np.float32)

    elif name == "ct_soft_tissue":
        # Soft Tissue / Flesh: Transparent -> Tan -> Orange -> Red
        kp_pos = [0.0, 0.2, 0.5, 1.0]
        kp_r = [0.0, 0.8, 1.0, 0.8]
        kp_g = [0.0, 0.5, 0.6, 0.2]
        kp_b = [0.0, 0.4, 0.4, 0.1]
        
        r = np.interp(t, kp_pos, kp_r)
        g = np.interp(t, kp_pos, kp_g)
        b = np.interp(t, kp_pos, kp_b)
        a = t if alpha_ramp is None else alpha_ramp
        return np.column_stack([r, g, b, a]).astype(np.float32)

    elif name == "ct_muscle":
        # Muscle & Organ: Transparent -> Deep Red -> Brown
        kp_pos = [0.0, 0.3, 0.7, 1.0]
        kp_r = [0.0, 0.6, 0.7, 0.4]
        kp_g = [0.0, 0.1, 0.2, 0.1]
        kp_b = [0.0, 0.1, 0.1, 0.1]
        
        r = np.interp(t, kp_pos, kp_r)
        g = np.interp(t, kp_pos, kp_g)
        b = np.interp(t, kp_pos, kp_b)
        a = t if alpha_ramp is None else alpha_ramp
        return np.column_stack([r, g, b, a]).astype(np.float32)

    elif name == "ct_lung":
        # Lung / Air: Transparent -> Black -> Blue/Cyan
        # Typically inverted in standard viewing (Air is low density)
        # But this map gives blueish tint to lower end if used with proper windowing
        kp_pos = [0.0, 0.3, 0.7, 1.0]
        kp_r = [0.0, 0.0, 0.0, 0.5]
        kp_g = [0.0, 0.0, 0.5, 0.8]
        kp_b = [0.0, 0.0, 1.0, 1.0]
        
        r = np.interp(t, kp_pos, kp_r)
        g = np.interp(t, kp_pos, kp_g)
        b = np.interp(t, kp_pos, kp_b)
        a = t if alpha_ramp is None else alpha_ramp
        return np.column_stack([r, g, b, a]).astype(np.float32)
    
    elif name == "legacy_cool_warm":
        # Diverging: Blue -> White -> Red
        kp_pos = [0.0, 0.5, 1.0]
        kp_r = [0.23, 0.86, 0.70]
        kp_g = [0.29, 0.86, 0.01]
        kp_b = [0.75, 0.86, 0.14]
        # Actually let's use a better standard cool-warm approximation
        # 0.0: Blue (0.23, 0.299, 0.754)
        # 0.5: Light Gray (0.86, 0.86, 0.86)
        # 1.0: Red (0.70, 0.015, 0.14)
        
        r = np.interp(t, kp_pos, kp_r)
        g = np.interp(t, kp_pos, kp_g)
        b = np.interp(t, kp_pos, kp_b)
        a = t if alpha_ramp is None else alpha_ramp
        return np.column_stack([r, g, b, a]).astype(np.float32)

    elif name == "ct_sandstone":
        # CT-Sandstone: Black -> Beige -> Sepia -> White
        kp_pos = [0.0, 0.3, 0.6, 1.0]
        kp_r = [0.0, 0.8, 0.6, 1.0]
        kp_g = [0.0, 0.7, 0.4, 0.95]
        kp_b = [0.0, 0.5, 0.2, 0.8]
        
        r = np.interp(t, kp_pos, kp_r)
        g = np.interp(t, kp_pos, kp_g)
        b = np.interp(t, kp_pos, kp_b)
        a = t if alpha_ramp is None else alpha_ramp
        return np.column_stack([r, g, b, a]).astype(np.float32)

    elif name == "ct_body":
        # Full Body Composite Scheme based on typical Hounsfield Units
        
        # Mapping logic (approximate for normalized range 0..1):
        kp_pos = [0.0, 0.15, 0.25, 0.30, 0.40, 0.60, 0.90, 1.0]
        
        # Colors (R, G, B)
        kp_r = [0.0, 0.0, 0.95, 0.90, 0.60, 0.90, 1.00, 1.00]
        kp_g = [0.0, 0.8, 0.90, 0.40, 0.10, 0.90, 1.00, 1.00]
        kp_b = [0.0, 1.0, 0.60, 0.40, 0.10, 0.80, 1.00, 1.00]
        
        r = np.interp(t, kp_pos, kp_r)
        g = np.interp(t, kp_pos, kp_g)
        b = np.interp(t, kp_pos, kp_b)
        a = t if alpha_ramp is None else alpha_ramp
        return np.column_stack([r, g, b, a]).astype(np.float32)

    elif name == "legacy_rainbow":
        # Classic Rainbow (Violet-Blue-Green-Yellow-Orange-Red)
        kp_pos = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        kp_r = [0.5, 0.0, 0.0, 1.0, 1.0, 1.0]
        kp_g = [0.0, 0.0, 1.0, 1.0, 0.5, 0.0]
        kp_b = [1.0, 1.0, 0.0, 0.0, 0.0, 0.0]
        
        r = np.interp(t, kp_pos, kp_r)
        g = np.interp(t, kp_pos, kp_g)
        b = np.interp(t, kp_pos, kp_b)
        a = t if alpha_ramp is None else alpha_ramp
        return np.column_stack([r, g, b, a]).astype(np.float32)

    elif HAS_COLORCET and name.startswith("cet_"):
        cet_name = name[4:] # Remove "cet_"
        if hasattr(cc, cet_name):
            palette = getattr(cc, cet_name)
            # Interpolate or sample for target size
            n_colors = len(palette)
            raw_data = np.array([color_to_rgba(c) for c in palette], dtype=np.float32)
            
            if is_categorical(name):
                # Nearest neighbor sampling for categorical maps
                indices = np.clip(np.floor(t * n_colors).astype(np.int32), 0, n_colors - 1)
                arr = raw_data[indices]
            else:
                # Linear interpolation for gradients
                t_orig = np.linspace(0, 1, n_colors)
                arr = np.zeros((size, 4), dtype=np.float32)
                for i in range(4):
                    arr[:, i] = np.interp(t, t_orig, raw_data[:, i])
            
            if alpha_ramp is not None:
                arr[:, 3] = alpha_ramp
            else:
                arr[:, 3] = t
                
            return arr
        else:
            return get_colormap("grayscale", size, alpha_ramp)

    else:
        # Fallback to grayscale
        return get_colormap("grayscale", size, alpha_ramp)

def get_combined_tf(name: str, alpha_points: list, size: int = 256) -> np.ndarray:
    """
    Generates a TF by interpolation from alpha_points and combining with base colormap.
    alpha_points: list of (pos, alpha) tuples.
    """
    t = np.linspace(0, 1, size)
    kp_pos = [p[0] for p in alpha_points]
    kp_alpha = [p[1] for p in alpha_points]
    
    alpha_ramp = np.interp(t, kp_pos, kp_alpha).astype(np.float32)
    return get_colormap(name, size, alpha_ramp)
