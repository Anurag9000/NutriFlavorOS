"""
GPU Device Configuration for NutriFlavorOS ML Models
Centralized CUDA detection and device management
"""
import torch
import logging
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DeviceConfig:
    """Singleton class for GPU device configuration"""
    
    _instance = None
    _device = None
    _device_info = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DeviceConfig, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize device configuration"""
        self._detect_device()
        self._log_device_info()
    
    def _detect_device(self):
        """Detect and set the best available device"""
        if torch.cuda.is_available():
            self._device = torch.device("cuda")
            self._device_info = {
                "type": "cuda",
                "name": torch.cuda.get_device_name(0),
                "count": torch.cuda.device_count(),
                "cuda_version": torch.version.cuda,
                "current_device": torch.cuda.current_device(),
                "memory_allocated": torch.cuda.memory_allocated(0),
                "memory_reserved": torch.cuda.memory_reserved(0),
                "memory_total": torch.cuda.get_device_properties(0).total_memory
            }
        else:
            self._device = torch.device("cpu")
            self._device_info = {
                "type": "cpu",
                "name": "CPU",
                "count": 1,
                "cuda_version": None
            }
    
    def _log_device_info(self):
        """Log device information"""
        if self._device_info["type"] == "cuda":
            logger.info("=" * 60)
            logger.info("🚀 GPU ACCELERATION ENABLED")
            logger.info("=" * 60)
            logger.info(f"Device: {self._device_info['name']}")
            logger.info(f"CUDA Version: {self._device_info['cuda_version']}")
            logger.info(f"GPU Count: {self._device_info['count']}")
            logger.info(f"Total Memory: {self._device_info['memory_total'] / 1024**3:.2f} GB")
            logger.info("=" * 60)
        else:
            logger.warning("=" * 60)
            logger.warning("⚠️  GPU NOT DETECTED - Running on CPU")
            logger.warning("=" * 60)
            logger.warning("For better performance, ensure CUDA is installed:")
            logger.warning("pip install torch==2.1.0+cu118 torchvision==0.16.0+cu118 --index-url https://download.pytorch.org/whl/cu118")
            logger.warning("=" * 60)
    
    @property
    def device(self) -> torch.device:
        """Get the configured device"""
        return self._device
    
    @property
    def is_cuda(self) -> bool:
        """Check if CUDA is available"""
        return self._device.type == "cuda"
    
    @property
    def device_name(self) -> str:
        """Get device name"""
        return self._device_info.get("name", "Unknown")
    
    def get_memory_info(self) -> dict:
        """Get current GPU memory usage"""
        if self.is_cuda:
            return {
                "allocated_gb": torch.cuda.memory_allocated(0) / 1024**3,
                "reserved_gb": torch.cuda.memory_reserved(0) / 1024**3,
                "total_gb": self._device_info["memory_total"] / 1024**3,
                "free_gb": (self._device_info["memory_total"] - torch.cuda.memory_allocated(0)) / 1024**3
            }
        return {}
    
    def reset_peak_memory_stats(self):
        """Reset peak memory statistics"""
        if self.is_cuda:
            torch.cuda.reset_peak_memory_stats()
    
    def empty_cache(self):
        """Clear GPU cache"""
        if self.is_cuda:
            torch.cuda.empty_cache()
            logger.info("GPU cache cleared")


# Global device configuration instance
_device_config = DeviceConfig()


def get_device() -> torch.device:
    """
    Get the configured device (CUDA if available, else CPU)
    
    Returns:
        torch.device: The device to use for tensor operations
    
    Example:
        >>> device = get_device()
        >>> model = MyModel().to(device)
        >>> tensor = torch.randn(10, 10).to(device)
    """
    return _device_config.device


def is_cuda_available() -> bool:
    """
    Check if CUDA is available
    
    Returns:
        bool: True if CUDA is available, False otherwise
    """
    return _device_config.is_cuda


def get_device_name() -> str:
    """
    Get the name of the current device
    
    Returns:
        str: Device name (e.g., "NVIDIA GeForce RTX 3050" or "CPU")
    """
    return _device_config.device_name


def get_memory_info() -> dict:
    """
    Get GPU memory information
    
    Returns:
        dict: Memory statistics (allocated, reserved, total, free in GB)
    """
    return _device_config.get_memory_info()


def to_device(obj, device: Optional[torch.device] = None):
    """
    Move tensor or model to device
    
    Args:
        obj: Tensor, model, or any object with .to() method
        device: Target device (if None, uses default device)
    
    Returns:
        Object moved to device
    
    Example:
        >>> model = to_device(MyModel())
        >>> tensor = to_device(torch.randn(10, 10))
    """
    if device is None:
        device = get_device()
    
    if hasattr(obj, 'to'):
        return obj.to(device)
    return obj


def clear_gpu_cache():
    """Clear GPU cache to free memory"""
    _device_config.empty_cache()


def reset_memory_stats():
    """Reset peak memory statistics"""
    _device_config.reset_peak_memory_stats()


def print_device_info():
    """Print detailed device information"""
    print("\n" + "=" * 60)
    print("DEVICE CONFIGURATION")
    print("=" * 60)
    print(f"Device Type: {_device_config.device}")
    print(f"Device Name: {_device_config.device_name}")
    print(f"CUDA Available: {_device_config.is_cuda}")
    
    if _device_config.is_cuda:
        print(f"CUDA Version: {_device_config._device_info['cuda_version']}")
        print(f"GPU Count: {_device_config._device_info['count']}")
        
        mem_info = get_memory_info()
        print(f"\nMemory Information:")
        print(f"  Total: {mem_info['total_gb']:.2f} GB")
        print(f"  Allocated: {mem_info['allocated_gb']:.2f} GB")
        print(f"  Reserved: {mem_info['reserved_gb']:.2f} GB")
        print(f"  Free: {mem_info['free_gb']:.2f} GB")
    
    print("=" * 60 + "\n")


# Initialize and log device info on import
if __name__ != "__main__":
    logger.info(f"Device configured: {get_device()}")
