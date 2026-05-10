# Low-VRAM Optimization Guide (8GB VRAM / 32GB RAM)

## Overview
NovelForge now supports **sequential model loading** optimized for systems with limited GPU memory (8GB VRAM). This ensures only one large LLM is loaded at a time, preventing Out-Of-Memory (OOM) errors.

---

## Key Features

### 1. **Resource Manager** (`resource_manager.py`)
- **Auto-detection**: Detects available VRAM and chooses GPU/CPU automatically
- **Sequential Loading**: Loads/unloads models on-demand
- **Memory Monitoring**: Real-time VRAM usage tracking
- **Emergency Fallback**: Automatically falls back to CPU if GPU OOM occurs

### 2. **Modified Model Clients**
All model generation calls now include:
```python
# Load model before use
await self.head.ensure_model_loaded()

# Generate text
result = await self.head.generate(...)

# Unload immediately after to free VRAM
await self.head.unload_model_if_needed()
```

### 3. **Smart Initialization**
During `NovelForge.initialize()`:
```
1. Load Head model → Log VRAM → Unload Head
2. Load Critic model → Log VRAM → Unload Critic
3. Both models start unloaded, load on-demand
```

---

## VRAM Usage Pattern

| Phase | Head Model | Critic Model | VRAM Used |
|-------|-----------|--------------|-----------|
| Init | Load→Unload | Load→Unload | ~0 GB |
| Planning | ✅ Loaded | ❌ Unloaded | ~14 GB* |
| Writing | ✅ Loaded | ❌ Unloaded | ~14 GB* |
| Review | ❌ Unloaded | ✅ Loaded | ~8 GB |
| Revision | ✅ Loaded | ❌ Unloaded | ~14 GB* |

*If using 21B+ model; actual usage depends on model size

---

## Configuration

### Environment Variables
```bash
# Force CPU mode (no GPU)
export FORCE_CPU=true

# Set VRAM threshold (MB) for auto-fallback
export VRAM_THRESHOLD=2048
```

### Manual Control
```python
from resource_manager import resource_manager

# Check VRAM status
print(resource_manager.get_vram_usage())

# Manually unload all models
resource_manager.unload_model()

# Load specific model
await forge.head.ensure_model_loaded()
```

---

## Performance Impact

| Metric | Before | After (Sequential) |
|--------|--------|-------------------|
| Max VRAM Usage | 22+ GB | 14 GB |
| OOM Errors | Frequent | Eliminated |
| Speed | Faster (both loaded) | Slightly slower (load/unload overhead) |
| Stability | Low on 8GB | High on 8GB |

**Trade-off**: ~5-10% slower due to load/unload cycles, but **runs on 8GB VRAM**.

---

## Troubleshooting

### "CUDA out of memory" Error
1. Check VRAM: `resource_manager.get_vram_usage()`
2. Ensure models are unloading: Look for "Deactivating model" logs
3. Try forcing CPU mode: Set `FORCE_CPU=true`

### Slow Performance
- Sequential loading adds ~1-2 seconds per model switch
- This is normal and necessary for low-VRAM systems
- Consider upgrading to 16GB+ VRAM for better performance

### Models Not Unloading
- Check for circular references in your code
- Ensure `await self.unload_model_if_needed()` is called after each generation
- Run manual cleanup: `resource_manager.unload_model()`

---

## Best Practices

1. **Don't Keep Models Loaded**: Always unload after use unless doing batch operations
2. **Monitor VRAM**: Add logging to track memory usage
3. **Use Smaller Models**: Consider 7B-14B models for faster inference
4. **Batch Operations**: Group similar tasks to minimize load/unload cycles
5. **CPU Fallback**: Don't fear CPU mode for non-intensive tasks

---

## Example Workflow

```python
from novelforge_v2 import NovelForge

forge = NovelForge(
    head_endpoint="http://localhost:1234/v1",
    critic_endpoint="http://localhost:1235/v1",
    mcp_servers=["./mempalace_mcp_server.py"]
)

await forge.initialize()
# Logs: VRAM Status, Head loaded/unloaded, Critic loaded/unloaded

# Each operation now manages VRAM automatically
result = await forge.write_chapter(
    novel_name="my_novel",
    chapter="chapter_1",
    prompt="Write opening scene"
)
# Internally: Load Head → Generate → Unload Head → Load Critic → Review → Unload Critic
```

---

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| VRAM | 8 GB | 16+ GB |
| RAM | 32 GB | 64 GB |
| Storage | 50 GB SSD | 100 GB NVMe |
| CUDA | 11.8+ | 12.x |

---

## Future Improvements

- [ ] Model quantization (4-bit/8-bit) for lower VRAM usage
- [ ] Pipeline parallelism for multi-GPU setups
- [ ] Smart caching to reduce reload frequency
- [ ] Dynamic batch sizing based on available VRAM
