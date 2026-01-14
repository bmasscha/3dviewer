import scipy.ndimage
import logging
import numpy as np
from skimage.restoration import denoise_bilateral, denoise_nl_means, estimate_sigma, denoise_tv_chambolle

def apply_3d_gaussian(volume: np.ndarray, sigma: float) -> np.ndarray:
    """
    Applies a 3D Gaussian filter to the volume.
    
    Args:
        volume (np.ndarray): The 3D volume data.
        sigma (float): Standard deviation for Gaussian kernel.
        
    Returns:
        np.ndarray: Filtered volume.
    """
    logging.info(f"Applying Gaussian filter with sigma={sigma}...")
    # gaussian_filter supports generic float sigma or sequence of sigmas
    return scipy.ndimage.gaussian_filter(volume, sigma=sigma)

def apply_3d_median(volume: np.ndarray, size: int) -> np.ndarray:
    """
    Applies a 3D Median filter to the volume.
    
    Args:
        volume (np.ndarray): The 3D volume data.
        size (int): Size of the box for median filter (must be integer).
        
    Returns:
        np.ndarray: Filtered volume.
    """
    logging.info(f"Applying Median filter with size={size}...")
    return scipy.ndimage.median_filter(volume, size=size)


def _normalize(volume):
    v_min, v_max = volume.min(), volume.max()
    if v_max - v_min == 0:
        return volume.astype(np.float32), v_min, v_max
    
    # Convert to float32 and normalize to [0, 1]
    norm_vol = (volume.astype(np.float32) - v_min) / (v_max - v_min)
    return norm_vol, v_min, v_max

def _denormalize(volume, v_min, v_max, original_dtype):
    # Scale back
    restored = volume * (v_max - v_min) + v_min
    # Clip to safety
    if np.issubdtype(original_dtype, np.integer):
        info = np.iinfo(original_dtype)
        restored = np.clip(restored, info.min, info.max)
        return restored.astype(original_dtype)
    return restored


def apply_3d_bilateral(volume: np.ndarray, sigma_spatial: float, sigma_color: float, progress_callback=None, check_cancel=None) -> np.ndarray:
    """
    Applies a 3D Bilateral filter to the volume.
    Applies slice-by-slice (2.5D).
    """
    logging.info(f"Applying Bilateral filter with sigma_spatial={sigma_spatial}, sigma_color={sigma_color}...")
    
    norm_vol, v_min, v_max = _normalize(volume)
    filtered_volume = np.empty_like(norm_vol)
    depth = norm_vol.shape[0]
    
    for i in range(depth):
        if check_cancel and check_cancel():
            logging.info("Bilateral filter cancelled.")
            return None
            
        filtered_volume[i] = denoise_bilateral(
            norm_vol[i], 
            sigma_color=sigma_color, 
            sigma_spatial=sigma_spatial, 
            channel_axis=None
        )
        if progress_callback:
            progress_callback(int((i + 1) / depth * 100))
        
    return _denormalize(filtered_volume, v_min, v_max, volume.dtype)

def apply_3d_nlm(volume: np.ndarray, h: float = 1.15, patch_size: int = 5, patch_distance: int = 6, progress_callback=None, check_cancel=None) -> np.ndarray:
    """
    Applies Non-Local Means Denoising. Slice-by-slice for 2.5D filtering (interactive).
    """
    logging.info(f"Applying NLM filter with h={h}, patch_size={patch_size}, patch_distance={patch_distance}...")
    
    norm_vol, v_min, v_max = _normalize(volume)
    filtered_volume = np.empty_like(norm_vol)
    depth = norm_vol.shape[0]
    
    # Estimate sigma once usually ok, but strictly should be per slice if noise varies.
    # We'll estimate on whole volume for stability.
    sigma_est = np.mean(estimate_sigma(norm_vol))
    logging.info(f"Estimated sigma (approx): {sigma_est}")
    
    for i in range(depth):
        if check_cancel and check_cancel():
            logging.info("NLM filter cancelled.")
            return None

        filtered_volume[i] = denoise_nl_means(
            norm_vol[i], 
            h=h * sigma_est, 
            sigma=sigma_est, 
            fast_mode=True,
            patch_size=patch_size, 
            patch_distance=patch_distance
        )
        if progress_callback:
            progress_callback(int((i + 1) / depth * 100))
                            
    return _denormalize(filtered_volume, v_min, v_max, volume.dtype)

def apply_3d_tv(volume: np.ndarray, weight: float, progress_callback=None, check_cancel=None) -> np.ndarray:
    """
    Applies Total Variation (TV) Denoising per slice (2.5D).
    """
    logging.info(f"Applying TV filter with weight={weight}...")
    
    norm_vol, v_min, v_max = _normalize(volume)
    filtered_volume = np.empty_like(norm_vol)
    depth = norm_vol.shape[0]
    
    for i in range(depth):
        if check_cancel and check_cancel():
            logging.info("TV filter cancelled.")
            return None
            
        filtered_volume[i] = denoise_tv_chambolle(norm_vol[i], weight=weight)
        
        if progress_callback:
            progress_callback(int((i + 1) / depth * 100))
    
    return _denormalize(filtered_volume, v_min, v_max, volume.dtype)

