import numpy as np

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

    elif name == "rainbow":
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
