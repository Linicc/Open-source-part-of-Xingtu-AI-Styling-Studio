# 推荐信息前端对接文档（当前后端实现）

本文档基于当前后端代码实现，供前端直接对接使用。

---

## 1. 接口总览

- 生成推荐并落库：`POST /recommendations`
- 按结果ID读取：`GET /recommendations/result?result_id=...`
- 按用户快速取最近一条：`GET /recommendations/latest?user_id=...`

---

## 2. 生成推荐

### 2.1 请求

- URL：`POST /recommendations`
- Content-Type：`application/json`

请求体：

```json
{
  "user_id": "user_123456",
  "history_id": "record_1772801234",
  "intent": "想改善眼袋和法令纹",
  "limit_per_category": 2
}
```

字段说明：

- `user_id`：必填，用户标识
- `history_id`：可选，关联诊断历史ID
- `intent`：可选，用户诉求文本
- `limit_per_category`：可选，每类返回条数（后端自动约束到 1~10）

### 2.2 成功响应

```json
{
  "status": "success",
  "data": {
    "result_id": "rec_1772901233832",
    "categories": [
      {
        "type": "merchant",
        "title": "推荐商户",
        "items": [
          {
            "id": "m_1001",
            "name": "星和医美中心",
            "score": 0.976,
            "reason": "地理位置方便，且该机构在目标项目上口碑稳定",
            "cover_image_url": "https://example.com/images/merchant_xinghe.jpg",
            "city": "北京",
            "district": "朝阳区",
            "rating": 4.8
          }
        ]
      },
      {
        "type": "doctor",
        "title": "推荐医生",
        "items": [
          {
            "id": "d_2001",
            "name": "王医生",
            "score": 0.9999,
            "reason": "医生经验与诉求匹配，临床风格偏自然精细",
            "avatar_url": "https://example.com/images/doctor_wang.jpg",
            "title": "主治医师",
            "years_experience": 12
          }
        ]
      },
      {
        "type": "treatment",
        "title": "推荐项目",
        "items": [
          {
            "id": "t_5002",
            "name": "玻尿酸填充",
            "score": 0.9,
            "reason": "该项目与当前面部问题匹配度高，方案成熟",
            "cover_image_url": "https://example.com/images/treatment_fill.jpg",
            "risk_level": "低",
            "downtime_level": "低"
          }
        ]
      },
      {
        "type": "brand",
        "title": "推荐品牌",
        "items": [
          {
            "id": "b_8001",
            "name": "乔雅登",
            "score": 0.85,
            "reason": "材料稳定性与临床反馈较好，适配常见诉求",
            "logo_url": "https://example.com/images/brand_qiaoyadeng.jpg",
            "origin_country": "美国"
          }
        ]
      }
    ]
  }
}
```

### 2.3 失败响应

```json
{
  "status": "error",
  "code": "INVALID_REQUEST",
  "message": "必须提供 user_id"
}
```

---

## 3. 查询单次推荐结果

### 3.1 请求

- URL：`GET /recommendations/result?result_id=rec_xxx`

### 3.2 成功响应

```json
{
  "status": "success",
  "data": {
    "id": "rec_1772901233832",
    "user_id": "user_123456",
    "history_id": "record_1772801234",
    "request_intent": "想改善眼袋和法令纹",
    "created_at": "2026-03-07T16:33:53Z",
    "categories": []
  }
}
```

### 3.3 失败响应

```json
{
  "status": "error",
  "code": "NOT_FOUND",
  "message": "未找到该推荐结果"
}
```

---

## 4. 按用户读取最近推荐

### 4.1 请求

- URL：`GET /recommendations/latest?user_id=user_123456`

### 4.2 成功响应

```json
{
  "status": "success",
  "data": {
    "id": "rec_1772901233832",
    "user_id": "user_123456",
    "history_id": "record_1772801234",
    "request_intent": "想改善眼袋和法令纹",
    "created_at": "2026-03-07T16:33:53Z",
    "categories": []
  }
}
```

### 4.3 失败响应

```json
{
  "status": "error",
  "code": "NOT_FOUND",
  "message": "该用户暂无推荐记录"
}
```

---

## 5. 前端渲染建议

- 渲染顺序按 `categories` 返回顺序展示
- 每类卡片至少依赖：`id`、`name`、`score`、`reason`
- 分类型字段：
  - merchant：`cover_image_url`、`city`、`district`、`rating`
  - doctor：`avatar_url`、`title`、`years_experience`
  - treatment：`cover_image_url`、`risk_level`、`downtime_level`
  - brand：`logo_url`、`origin_country`

---

## 6. 当前实现注意事项

- `type` 当前是英文枚举：`merchant` / `doctor` / `treatment` / `brand`
- `title` 与推荐文案为中文，适合中文前端直接展示
- 本接口当前使用 SQLite 持久化（并保留单次结果快照文件），前端接口不受影响
