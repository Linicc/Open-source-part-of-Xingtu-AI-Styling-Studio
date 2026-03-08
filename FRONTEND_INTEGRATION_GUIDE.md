# 10K项目前端接入指南 (Detailed Guide)

这份文档旨在指导前端开发人员如何从零开始接入 10K 项目的人脸修复 API。

## 🌐 1. 基础配置
- **Base API URL**: `http://127.0.0.1:8000`
- **协议**: HTTP
- **跨域 (CORS)**: 后端已配置允许所有源 (`*`)，前端可直接调用，无需代理。

---

## 📦 2. 数据结构 (TypeScript 定义)

为了方便前端开发，我们定义了以下 TypeScript 接口。您可以直接复制到项目中使用。

```typescript
// API 响应基础结构
interface ApiResponse<T> {
  status: "success" | "error";
  data?: T;          // 成功时有此字段
  message?: string;  // 失败时有此字段
  step?: string;     // 失败步骤 (例如 "FR人脸识别")
  metadata?: ApiMetadata;
}

// 核心业务数据
interface ProcessResult {
  processed_image: string | null;  // 修复后的图片 URL (可能为空，如果修复失败)
  analysis: string | null;         // DeepSeek 提供的容貌分析建议
  user_intent: string;             // 解析后的用户意图 (如 "fix eye bags")
  mask_coordinates: Array<[number, number]>; // 识别到的缺陷区域中心点 [[x, y], ...]
}

// 元数据 (调试与特征)
interface ApiMetadata {
  features: FaceFeatures;
  doubao_error: string | null;     // 豆包API是否有错
  deepseek_error: string | null;   // DeepSeek API是否有错
}

// 面部特征数据
interface FaceFeatures {
  nose_length: number;
  face_width: number;
  face_height: number;
  timestamp: number;
}
```

---

## 🛠️ 3. 完整接入流程

### 第一步：文件上传与预览
在调用 API 之前，建议先在前端展示用户选择的图片。

```javascript
// HTML: <input type="file" id="uploadInput" accept="image/*">
// HTML: <img id="previewImg" src="" style="display:none; max-width: 300px;">

document.getElementById('uploadInput').addEventListener('change', function(e) {
    const file = e.target.files[0];
    if (file) {
        // 创建本地预览 URL
        const previewUrl = URL.createObjectURL(file);
        const img = document.getElementById('previewImg');
        img.src = previewUrl;
        img.style.display = 'block';
    }
});
```

### 第二步：构造请求与发送
使用 `FormData` 对象来封装文件和参数。

**关键点**：
- `file` 字段必须是二进制文件对象。
- `intent` 字段是可选的，用户可以输入 "reduce dark circles"、"slim face" 等。

```javascript
async function uploadAndProcess(file, userIntent = "") {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("intent", userIntent);

    try {
        // 显示 Loading 状态
        showLoading(true); 

        const response = await fetch("http://127.0.0.1:8000/process", {
            method: "POST",
            body: formData
        });

        const result = await response.json();
        return result;

    } catch (error) {
        console.error("网络请求失败:", error);
        alert("网络连接异常，请检查网络");
        return null;
    } finally {
        // 隐藏 Loading 状态
        showLoading(false);
    }
}
```

### 第三步：处理响应结果

后端返回的结果可能有三种情况：
1.  **成功** (`status: "success"`)：正常展示修复图和建议。
2.  **业务失败** (`status: "error"`)：如未检测到人脸。
3.  **部分成功**：如修复图生成了，但分析建议失败（检查 `metadata` 中的 error 字段）。

```javascript
function handleResponse(result) {
    if (!result) return;

    // 1. 严重错误 (如未检测到人脸)
    if (result.status === "error") {
        alert(`处理失败: ${result.message} (步骤: ${result.step})`);
        return;
    }

    const data = result.data;
    const meta = result.metadata;

    // 2. 检查是否有遮罩区域
    if (!data.mask_coordinates || data.mask_coordinates.length === 0) {
        alert("未检测到需要修复的区域 (如眼袋)，请尝试更清晰的照片");
        return;
    }

    // 3. 展示修复后的图片
    if (data.processed_image) {
        displayResultImage(data.processed_image);
    } else {
        // 如果图片生成失败 (doubao_error)
        console.warn("图片生成失败:", meta.doubao_error);
        alert("图片修复服务暂时不可用，但分析已完成");
    }

    // 4. 展示分析建议
    if (data.analysis) {
        displayAnalysisText(data.analysis);
    }
}
```

---

## 💻 4. 框架代码示例

### React 示例组件

```jsx
import React, { useState } from 'react';

const FaceFixer = () => {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setLoading(true);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("intent", "remove eye bags");

    try {
      const res = await fetch("http://127.0.0.1:8000/process", {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      setResult(data);
    } catch (err) {
      alert("请求失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-4">
      <h1>AI 人脸修复</h1>
      <input type="file" onChange={handleUpload} disabled={loading} />
      
      {loading && <p>正在处理中，请稍候...</p>}

      {result && result.status === 'success' && (
        <div className="mt-4">
          <h3>处理结果</h3>
          {/* 对比图展示 */}
          <div className="flex gap-4">
            <div className="flex-1">
               <p>修复后:</p>
               {result.data.processed_image ? (
                 <img src={result.data.processed_image} alt="After" className="w-full" />
               ) : (
                 <p className="text-red-500">图片生成失败</p>
               )}
            </div>
          </div>
          
          {/* 分析建议 */}
          <div className="mt-4 p-4 bg-gray-100 rounded">
            <h4>专业建议:</h4>
            <p>{result.data.analysis}</p>
          </div>
        </div>
      )}

      {result && result.status === 'error' && (
        <div className="text-red-500 mt-4">
          错误: {result.message}
        </div>
      )}
    </div>
  );
};

export default FaceFixer;
```

---

## ⚠️ 5. 常见问题 (FAQ)

**Q1: 图片上传大小有限制吗？**
A: 服务器目前未设置严格限制，但建议控制在 **10MB** 以内，以免超时。推荐使用 jpg 或 png 格式。

**Q2: 为什么提示“未能识别到人脸”？**
A: 后端集成了严格的 FR (Face Recognition) 校验。请确保照片中包含清晰的正脸，且不要遮挡面部关键区域。

**Q3: 接口响应慢怎么办？**
A: 整个流程包含 YOLO 识别、豆包图像生成、DeepSeek 推理，通常需要 **5-10秒**。前端**务必**要设计 Loading 状态，避免用户重复点击。

**Q4: 图片 URL 有效期是多久？**
A: 返回的 `processed_image` URL 是云存储的临时链接（通常 1-2 小时有效）。如果前端需要持久化，请自行转存或下载。
