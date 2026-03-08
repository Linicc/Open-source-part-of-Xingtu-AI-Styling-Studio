import requests
import os
import time

BASE_URL = "http://127.0.0.1:8000"

def test_new_storage_logic():
    print("=== Testing New Storage Logic ===")
    
    image_path = "test_image.jpg"
    if not os.path.exists(image_path):
        print("Test image not found")
        return

    # 模拟一个用户 ID
    test_user_id = f"test_user_{int(time.time())}"
    print(f"Using Test User ID: {test_user_id}")

    try:
        with open(image_path, "rb") as f:
            files = {"file": ("test_image.jpg", f, "image/jpeg")}
            data = {
                "intent": "去眼袋测试",
                "user_id": test_user_id  # 传入新参数
            }
            
            response = requests.post(f"{BASE_URL}/process", files=files, data=data, timeout=30)
            
            if response.status_code == 200:
                print("✅ API Response: Success")
                print(response.json())
            else:
                print(f"❌ API Failed: {response.status_code}")
                print(response.text)

    except Exception as e:
        print(f"❌ Request Error: {e}")

if __name__ == "__main__":
    test_new_storage_logic()
