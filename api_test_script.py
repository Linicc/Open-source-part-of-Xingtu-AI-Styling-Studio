import requests
import os

BASE_URL = "http://127.0.0.1:8000"

def test_endpoint(url, method="GET", files=None, data=None):
    print(f"\nTesting {method} {url} ...")
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, files=files, data=data, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        try:
            print("Response JSON:")
            print(response.json())
        except:
            print("Response Text:")
            print(response.text[:500])
            
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

# 1. Test Health Check
print("=== 1. Testing Health Check ===")
test_endpoint(f"{BASE_URL}/")

# 2. Test Debug Endpoint
print("\n=== 2. Testing Debug Endpoint ===")
test_endpoint(f"{BASE_URL}/test")

# 3. Test Process Endpoint (with a sample image)
print("\n=== 3. Testing Process Endpoint ===")
# Use an existing image from the project structure
image_path = "test_image.jpg"

if os.path.exists(image_path):
    print(f"Using image: {image_path}")
    with open(image_path, "rb") as f:
        files = {"file": ("test_image.jpg", f, "image/jpeg")}
        data = {"intent": "去眼袋测试"}
        test_endpoint(f"{BASE_URL}/process", method="POST", files=files, data=data)
else:
    print(f"Test image not found at {image_path}, skipping process test.")
