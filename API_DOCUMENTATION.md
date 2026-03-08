# 10K项目 - API 接入文档

## 1. 基础信息
- **Base URL**: `http://127.0.0.1:8000`
- **在线调试文档**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) (Swagger UI)

## 2. 核心接口：人脸修复与分析

### 请求信息
- **接口地址**: `/process`
- **请求方法**: `POST`
- **Content-Type**: `multipart/form-data`
- **Doubao Prompt Rule**: 后端发送给豆包的 prompt 会以 `Keep the face size ratio unchanged.` 开头

### 请求参数
| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| `file` | File | 是 | 用户上传的人脸图片文件 (jpg/png) |
| `intent` | String | 否 | 用户诉求 (例如: "remove eye bags", "brighten skin tone")，默认为空 |

### 响应示例 (成功)
```json
{
  "status": "success",
  "data": {
    "processed_image": "https://ark-creation-platform.tos-cn-beijing.volces.com/...", // 处理后的图片URL
    "analysis": "根据您的面部特征...", // DeepSeek给出的分析建议
    "user_intent": "fix eye bags", // 解析后的用户意图
    "mask_coordinates": [[300, 400], [350, 400]] // 识别到的遮罩区域中心点
  },
  "metadata": {
    "features": { ... }, // 面部特征数据
    "doubao_error": null,
    "deepseek_error": null
  }
}
```

### 响应示例 (失败 - 未检测到人脸)
```json
{
  "status": "error",
  "message": "未能识别到人脸",
  "step": "FR人脸识别"
}
```

## 3. 代码接入示例

### JavaScript (Fetch API)
```javascript
const formData = new FormData();
const fileInput = document.querySelector('input[type="file"]');
formData.append("file", fileInput.files[0]);
formData.append("intent", "remove eye bags");

fetch("http://127.0.0.1:8000/process", {
  method: "POST",
  body: formData
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error("Error:", error));
```

### Python (Requests)
```python
import requests

url = "http://127.0.0.1:8000/process"
files = {'file': open('face.jpg', 'rb')}
data = {'intent': 'remove eye bags'}

response = requests.post(url, files=files, data=data)
print(response.json())
```

### cURL (命令行)
```bash
curl -X POST "http://127.0.0.1:8000/process" \
     -F "file=@/path/to/your/image.jpg" \
     -F "intent=reduce dark circles"
```
