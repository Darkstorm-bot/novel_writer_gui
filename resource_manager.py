"""
Resource Manager for Low-VRAM Environments
Handles sequential model loading and GPU memory cleanup.
"""
import torch
import gc
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class ResourceManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ResourceManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized:
            return
        self.current_model = None
        self.device = self._get_device()
        self.initialized = True
        logger.info(f"ResourceManager initialized on {self.device}")

    def _get_device(self) -> str:
        """Determine best available device."""
        if torch.cuda.is_available():
            # Check VRAM availability
            free_mem = torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated()
            if free_mem < 2 * 1024**3:  # Less than 2GB free
                logger.warning("Low VRAM detected. Falling back to CPU for safety.")
                return "cpu"
            return "cuda"
        return "cpu"

    def get_vram_usage(self) -> dict:
        """Get current VRAM usage stats."""
        if self.device == "cuda":
            allocated = torch.cuda.memory_allocated(self.device) / 1024**2
            reserved = torch.cuda.memory_reserved(self.device) / 1024**2
            total = torch.cuda.get_device_properties(0).total_memory / 1024**2
            return {
                "allocated_mb": round(allocated, 2),
                "reserved_mb": round(reserved, 2),
                "total_mb": round(total, 2),
                "free_mb": round(total - allocated, 2),
                "usage_percent": round((allocated / total) * 100, 2)
            }
        return {"status": "CPU mode", "allocated_mb": 0}

    def unload_model(self, model: Optional[any] = None):
        """
        Explicitly unload a model from VRAM.
        Critical for 8GB VRAM systems to prevent OOM.
        """
        logger.info("Initiating model unload sequence...")
        
        if model is not None:
            try:
                del model
            except Exception as e:
                logger.warning(f"Error deleting model reference: {e}")
        
        # Force garbage collection
        gc.collect()
        
        # Clear CUDA cache if on GPU
        if self.device == "cuda":
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            
        self.current_model = None
        
        usage = self.get_vram_usage()
        logger.info(f"Model unloaded. VRAM Status: {usage['allocated_mb']}MB / {usage['total_mb']}MB used")

    def load_model_safe(self, model_loader_func, model_name: str):
        """
        Safely load a model after ensuring VRAM is clear.
        
        Args:
            model_loader_func: Callable that returns the loaded model
            model_name: Name of the model for logging
        """
        # Ensure previous model is gone
        if self.current_model is not None:
            self.unload_model(self.current_model)
        
        logger.info(f"Loading model: {model_name} on {self.device}...")
        initial_usage = self.get_vram_usage()
        logger.info(f"Pre-load VRAM: {initial_usage.get('allocated_mb', 0)}MB")

        try:
            # Load model
            model = model_loader_func()
            
            # Move to device if not already done by loader
            if hasattr(model, 'to'):
                model = model.to(self.device)
            
            self.current_model = model
            
            final_usage = self.get_vram_usage()
            logger.info(f"✅ {model_name} loaded successfully.")
            logger.info(f"Post-load VRAM: {final_usage.get('allocated_mb', 0)}MB ({final_usage.get('usage_percent', 0)}%)")
            
            return model
            
        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                logger.critical("OOM Error during load. Attempting emergency cleanup...")
                self.unload_model()
                # Try loading on CPU as last resort
                logger.warning("Retrying load on CPU due to OOM...")
                try:
                    model = model_loader_func()
                    model = model.to("cpu")
                    self.current_model = model
                    return model
                except Exception as cpu_e:
                    logger.error(f"Failed to load on CPU: {cpu_e}")
                    raise
            raise

# Global instance
resource_manager = ResourceManager()
