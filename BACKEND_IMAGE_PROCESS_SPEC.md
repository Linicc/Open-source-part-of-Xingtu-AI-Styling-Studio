# 10K项目 - 后端图像处理接口规范 (V3.0)

本文档定义了**最新的**后端图像处理接口。
**核心变更**：前端不再上传图片到 `/process`，而是直接引用云端档案中的照片。

---

## 🚀 核心流程

1.  **上传档案**：前端调用 `POST /user/profile`，将带有照片（Base64）的档案传给后端。后端会自动保存照片并生成 URL。
2.  **开始分析**：前端调用 `POST /process`，仅需提供 `user_id`。后端会自动去服务器上找刚才存的那张照片进行分析。

---

## 📡 接口定义

### 1. 智能诊断 (Diagnosis)

*   **URL**: `POST /process`
*   **Content-Type**: `application/json` (注意：不再是 multipart/form-data)
*   **Doubao Prompt Rule**: 后端会在图像生成 prompt 开头固定追加 `Keep the face size ratio unchanged.`

#### 请求体 (Request Body)
```json
{
  "user_id": "user_123456",  // 必填: 用户的唯一标识
  "intent": "remove eye bags" // 选填: 用户诉求
}
```

#### 响应体 (Response)
```json
{
  "status": "success",
  "data": {
    "processed_image_url": "http://127.0.0.1:8000/static/uploads/...", // 修复后的图片
    "analysis": "根据您的档案...",
    "mask_coordinates": [[100, 100], [200, 200]],
    "history_id": "record_1772801234"
  },
  "metadata": { ... }
}
```

#### 错误代码 (Error Codes)
*   `PROFILE_MISSING`: 找不到该用户的档案（请先调用保存档案接口）。
*   `PHOTO_MISSING`: 档案里没有照片（请提示用户先拍照）。

---

### 2. 用户档案保存 (Profile Save) - 复习

*   **URL**: `POST /user/profile`
*   **Content-Type**: `application/json`

#### 请求体
```json
{
  "user_id": "user_123456",
  "data": {
    "gender": "女",
    "photo": "data:image/jpeg;base64,..." // 必须包含 Base64 照片
  }
}
```

---

## 💻 前端调用示例 (JavaScript)

```javascript
// 1. 先保存档案 (带照片)
await fetch("http://127.0.0.1:8000/user/profile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
        user_id: "user_001",
        data: { photo: base64String, age: 25 }
    })
});

// 2. 然后直接发起分析 (无需再传图)
const res = await fetch("http://127.0.0.1:8000/process", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
        user_id: "user_001",
        intent: "remove eye bags"
    })
});
const result = await res.json();
console.log(result.data.processed_image_url);
```
