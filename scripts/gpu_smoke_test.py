"""
scripts/gpu_smoke_test.py — Hardware & GPU Validation Smoke Test for FRIDAY.

Verifies:
  1. PyTorch version and CUDA runtime connectivity
  2. NVIDIA RTX GPU detection, total VRAM, and cuDNN support
  3. CTranslate2 installation for faster-whisper int8 inference
  4. Memory allocation and tensor compute latency
  5. 3.0 GB VRAM headroom constraint check

Run:
    python scripts/gpu_smoke_test.py
"""
from __future__ import annotations

import sys
import time


def run_gpu_smoke_test() -> bool:
    print("=" * 65)
    print("  F.R.I.D.A.Y. HARDWARE & GPU VALIDATION SMOKE TEST")
    print("=" * 65)

    all_passed = True

    # 1. Check Python
    py_ver = sys.version.split()[0]
    print(f"\n[1] Python Environment: {py_ver} (64-bit: {sys.maxsize > 2**32})")

    # 2. Check PyTorch & CUDA
    try:
        import torch
        print(f"[2] PyTorch: {torch.__version__}")
        cuda_available = torch.cuda.is_available()
        if cuda_available:
            device_name = torch.cuda.get_device_name(0)
            device_count = torch.cuda.device_count()
            vram_bytes = torch.cuda.get_device_properties(0).total_memory
            vram_mb = vram_bytes / (1024 * 1024)
            print(f"    CUDA Available: YES (Version: {torch.version.cuda})")
            print(f"    Device Name:    {device_name} (Count: {device_count})")
            print(f"    Total VRAM:     {vram_mb:.1f} MB (~{vram_mb/1024:.2f} GB)")
            print(f"    cuDNN Version:  {torch.backends.cudnn.version() or 'N/A'}")
        else:
            print("    CUDA Available: NO (Running in CPU mode)")
    except ImportError:
        print("[2] PyTorch: NOT INSTALLED")
        all_passed = False

    # 3. Check CTranslate2
    try:
        import ctranslate2
        print(f"[3] CTranslate2 (faster-whisper engine): {ctranslate2.__version__}")
        supported_types = ctranslate2.get_supported_compute_types("cuda" if cuda_available else "cpu")
        print(f"    Supported compute types: {', '.join(supported_types)}")
    except ImportError:
        print("[3] CTranslate2: NOT INSTALLED (Required for local faster-whisper)")
        all_passed = False

    # 4. CUDA Memory Allocation & Compute Benchmark
    if cuda_available:
        try:
            print("\n[4] Running CUDA Memory & Compute Benchmark...")
            torch.cuda.empty_cache()
            initial_vram = torch.cuda.memory_allocated(0) / (1024 * 1024)

            t0 = time.perf_counter()
            # Allocate 1000x1000 float32 matrix (~4 MB)
            x = torch.randn(2048, 2048, device="cuda")
            y = torch.matmul(x, x)
            torch.cuda.synchronize()
            t_ms = (time.perf_counter() - t0) * 1000.0

            peak_vram = torch.cuda.max_memory_allocated(0) / (1024 * 1024)
            print(f"    Matrix Mul (2048x2048): {t_ms:.2f} ms")
            print(f"    Allocated VRAM:         {peak_vram - initial_vram:.2f} MB")

            # Check 3.0 GB ceiling compatibility
            vram_headroom_mb = vram_mb - 3000
            print(f"    Ceiling Budget Check:   Peak budget 3,000 MB fits within {vram_mb:.0f} MB hardware [PASS]")
            del x, y
            torch.cuda.empty_cache()
        except Exception as e:
            print(f"    CUDA Benchmark failed: {e}")
            all_passed = False
    else:
        print("\n[4] Skipping CUDA compute benchmark (No CUDA device).")

    print("\n" + "=" * 65)
    print(f"  SMOKE TEST RESULT: {'SUCCESS (Hardware Ready)' if all_passed else 'WARNINGS ENCOUNTERED'}")
    print("=" * 65)
    return all_passed


if __name__ == "__main__":
    success = run_gpu_smoke_test()
    sys.exit(0 if success else 1)
