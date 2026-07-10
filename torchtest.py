import torch

def test_pytorch():
    print("--- PyTorch Installation Test ---")
    
    # 1. Check PyTorch version
    print(f"PyTorch Version: {torch.__version__}")
    
    # 2. Check for CUDA (GPU) support
    cuda_available = torch.cuda.is_available()
    print(f"CUDA (GPU) Available: {cuda_available}")
    
    if cuda_available:
        print(f"GPU Device Name: {torch.cuda.get_device_name(0)}")
    else:
        print("Running on: CPU")
        
    print("\n--- Testing Tensor Computation ---")
    
    # 3. Perform a basic tensor operation
    try:
        # Create a 3x3 matrix with random numbers
        x = torch.rand(3, 3)
        print("Successfully created a 3x3 tensor:")
        print(x)
        
        # Test basic math (matrix multiplication)
        y = torch.matmul(x, x)
        print("\nSuccessfully performed matrix multiplication.")
        
    except Exception as e:
        print(f"An error occurred during computation: {e}")

if __name__ == "__main__":
    test_pytorch()