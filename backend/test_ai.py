import torch
import demucs

print("=" * 50)
print("KARAOKE AI - SYSTEM TEST")
print("=" * 50)

print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"CUDA version: {torch.version.cuda}")
else:
    print("GPU: Not detected - CPU will be used")

print(f"Demucs imported successfully: {demucs.__name__}")

print("=" * 50)
print("SYSTEM TEST COMPLETED")
print("=" * 50)