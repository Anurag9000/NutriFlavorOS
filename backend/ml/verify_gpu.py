"""
GPU Verification Script for NutriFlavorOS ML Models
Tests CUDA availability, GPU detection, and model performance
"""
import torch
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.device_config import (
    get_device, 
    is_cuda_available, 
    get_device_name, 
    get_memory_info,
    print_device_info
)


def print_section(title):
    """Print formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_cuda_availability():
    """Test 1: CUDA Availability"""
    print_section("TEST 1: CUDA AVAILABILITY")
    
    print(f"PyTorch Version: {torch.__version__}")
    print(f"CUDA Available: {torch.cuda.is_available()}")
    
    if torch.cuda.is_available():
        print(f"✅ CUDA is available!")
        print(f"CUDA Version: {torch.version.cuda}")
        print(f"cuDNN Version: {torch.backends.cudnn.version()}")
        print(f"GPU Count: {torch.cuda.device_count()}")
        
        for i in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(i)
            print(f"\nGPU {i}: {props.name}")
            print(f"  Compute Capability: {props.major}.{props.minor}")
            print(f"  Total Memory: {props.total_memory / 1024**3:.2f} GB")
            print(f"  Multi-Processors: {props.multi_processor_count}")
        
        return True
    else:
        print("❌ CUDA is NOT available")
        print("\nPossible reasons:")
        print("1. NVIDIA GPU drivers not installed")
        print("2. PyTorch CPU-only version installed")
        print("3. CUDA toolkit not installed")
        print("\nTo fix, install CUDA-enabled PyTorch:")
        print("pip install torch==2.1.0+cu118 torchvision==0.16.0+cu118 --index-url https://download.pytorch.org/whl/cu118")
        return False


def test_device_config():
    """Test 2: Device Configuration"""
    print_section("TEST 2: DEVICE CONFIGURATION")
    
    device = get_device()
    print(f"Configured Device: {device}")
    print(f"Device Type: {device.type}")
    print(f"Device Name: {get_device_name()}")
    print(f"Is CUDA: {is_cuda_available()}")
    
    if is_cuda_available():
        mem_info = get_memory_info()
        print(f"\nGPU Memory:")
        print(f"  Total: {mem_info['total_gb']:.2f} GB")
        print(f"  Allocated: {mem_info['allocated_gb']:.4f} GB")
        print(f"  Reserved: {mem_info['reserved_gb']:.4f} GB")
        print(f"  Free: {mem_info['free_gb']:.2f} GB")
        print("✅ Device configuration successful!")
        return True
    else:
        print("⚠️  Running on CPU")
        return False


def test_model_gpu_usage():
    """Test 3: Model GPU Usage"""
    print_section("TEST 3: MODEL GPU USAGE")
    
    try:
        from ml.taste_predictor import DeepTastePredictor
        from ml.recipe_vision import RecipeVisionAnalyzer
        from ml.health_predictor import HealthOutcomePredictor
        from ml.meal_planner_rl import RLMealPlanner
        from ml.recipe_generator_nlp import NLPRecipeGenerator
        from ml.grocery_predictor import GroceryPredictor
        
        models_info = []
        
        # Test 1: Taste Predictor
        print("\n1. Testing DeepTastePredictor...")
        taste_model = DeepTastePredictor()
        device = next(taste_model.parameters()).device
        print(f"   Device: {device}")
        models_info.append(("DeepTastePredictor", device))
        
        # Test 2: Recipe Vision
        print("\n2. Testing RecipeVisionAnalyzer...")
        vision_model = RecipeVisionAnalyzer(pretrained=False)  # Skip pretrained to save time
        device = next(vision_model.parameters()).device
        print(f"   Device: {device}")
        models_info.append(("RecipeVisionAnalyzer", device))
        
        # Test 3: Health Predictor
        print("\n3. Testing HealthOutcomePredictor...")
        health_predictor = HealthOutcomePredictor()
        device = next(health_predictor.model.parameters()).device
        print(f"   Device: {device}")
        models_info.append(("HealthOutcomePredictor", device))
        
        # Test 4: RL Meal Planner
        print("\n4. Testing RLMealPlanner...")
        rl_planner = RLMealPlanner()
        device = next(rl_planner.policy.parameters()).device
        print(f"   Device: {device}")
        models_info.append(("RLMealPlanner", device))
        
        # Test 5: NLP Recipe Generator
        print("\n5. Testing NLPRecipeGenerator...")
        nlp_generator = NLPRecipeGenerator()
        device = next(nlp_generator.model.parameters()).device
        print(f"   Device: {device}")
        models_info.append(("NLPRecipeGenerator", device))
        
        # Test 6: Grocery Predictor
        print("\n6. Testing GroceryPredictor...")
        grocery_predictor = GroceryPredictor(user_id="test_user")
        device = next(grocery_predictor.model.parameters()).device
        print(f"   Device: {device}")
        models_info.append(("GroceryPredictor", device))
        
        # Summary
        print("\n" + "-" * 70)
        print("MODEL DEVICE SUMMARY:")
        print("-" * 70)
        
        all_on_gpu = True
        for model_name, device in models_info:
            status = "✅" if device.type == "cuda" else "❌"
            print(f"{status} {model_name:30s} -> {device}")
            if device.type != "cuda":
                all_on_gpu = False
        
        if all_on_gpu and is_cuda_available():
            print("\n✅ All models successfully loaded on GPU!")
            return True
        elif not is_cuda_available():
            print("\n⚠️  All models on CPU (CUDA not available)")
            return True
        else:
            print("\n❌ Some models failed to load on GPU")
            return False
            
    except Exception as e:
        print(f"❌ Error testing models: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_gpu_inference():
    """Test 4: GPU Inference Performance"""
    print_section("TEST 4: GPU INFERENCE PERFORMANCE")
    
    if not is_cuda_available():
        print("⚠️  Skipping performance test (CUDA not available)")
        return True
    
    try:
        import time
        from ml.taste_predictor import DeepTastePredictor
        
        print("Testing inference speed with DeepTastePredictor...")
        model = DeepTastePredictor()
        
        # Create dummy input
        user_genome = {f"compound_{i}": 0.5 for i in range(100)}
        recipe_profile = {f"compound_{i}": 0.3 for i in range(100)}
        
        # Warmup
        print("Warming up GPU...")
        for _ in range(5):
            model.predict_single(user_genome, recipe_profile)
        
        # Benchmark
        print("Running benchmark (100 inferences)...")
        start_time = time.time()
        for _ in range(100):
            score, conf = model.predict_single(user_genome, recipe_profile)
        end_time = time.time()
        
        total_time = end_time - start_time
        avg_time = total_time / 100
        
        print(f"\nResults:")
        print(f"  Total time: {total_time:.3f} seconds")
        print(f"  Average time per inference: {avg_time*1000:.2f} ms")
        print(f"  Throughput: {100/total_time:.1f} inferences/second")
        
        # Check memory usage
        if is_cuda_available():
            mem_info = get_memory_info()
            print(f"\nGPU Memory After Inference:")
            print(f"  Allocated: {mem_info['allocated_gb']:.4f} GB")
            print(f"  Reserved: {mem_info['reserved_gb']:.4f} GB")
        
        print("✅ GPU inference test successful!")
        return True
        
    except Exception as e:
        print(f"❌ Error during inference test: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all GPU verification tests"""
    print("\n" + "=" * 70)
    print("  NutriFlavorOS GPU Verification Suite")
    print("  Testing RTX 3050 GPU Detection and Performance")
    print("=" * 70)
    
    results = {
        "CUDA Availability": test_cuda_availability(),
        "Device Configuration": test_device_config(),
        "Model GPU Usage": test_model_gpu_usage(),
        "GPU Inference": test_gpu_inference()
    }
    
    # Final Summary
    print_section("FINAL SUMMARY")
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTests Passed: {passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        print("\n🎉 ALL TESTS PASSED! GPU is properly configured.")
        if is_cuda_available():
            print(f"🚀 Your {get_device_name()} is ready for ML inference!")
    else:
        print("\n⚠️  Some tests failed. Please review the output above.")
    
    print("=" * 70 + "\n")
    
    return passed_tests == total_tests


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
