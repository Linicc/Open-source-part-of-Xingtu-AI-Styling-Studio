# 推荐项目数据标准（后端数据库与前后端通信）

## 1. 目标

本规范用于统一“推荐项目”能力的数据结构与接口协议，确保前端稳定渲染以下四类推荐卡片：

1. 推荐商户
2. 推荐医生
3. 推荐项目
4. 推荐品牌

---

## 2. 总体约束

- 推荐结果必须按四类分组返回，前端按分组顺序渲染。
- 每个推荐项必须包含 `id`、`name`、`score`、`reason`。
- 所有图片字段必须返回可直接访问的 URL。
- 货币统一 `CNY`，价格以“分”为整数存储（`min_price_cent`、`max_price_cent`）。
- 时间统一 UTC ISO 8601（例如 `2026-03-08T12:00:00Z`）。

---

## 3. 数据库架构

## 3.1 维表/主数据表

### merchants（商户）
- `id` (PK, varchar)
- `name` (varchar, not null)
- `city` (varchar, index)
- `district` (varchar, nullable)
- `address` (varchar, nullable)
- `lat` (decimal, nullable)
- `lng` (decimal, nullable)
- `rating` (decimal(2,1), nullable)
- `cover_image_url` (varchar, nullable)
- `tags` (json, nullable)
- `is_active` (tinyint, default 1)
- `created_at` / `updated_at` (datetime)

### doctors（医生）
- `id` (PK, varchar)
- `merchant_id` (FK -> merchants.id, index)
- `name` (varchar, not null)
- `title` (varchar, nullable)
- `specialties` (json, nullable)
- `years_experience` (int, nullable)
- `rating` (decimal(2,1), nullable)
- `avatar_url` (varchar, nullable)
- `tags` (json, nullable)
- `is_active` (tinyint, default 1)
- `created_at` / `updated_at` (datetime)

### treatments（项目）
- `id` (PK, varchar)
- `name` (varchar, not null)
- `category` (varchar, index)
- `risk_level` (varchar, nullable)
- `downtime_level` (varchar, nullable)
- `description` (text, nullable)
- `cover_image_url` (varchar, nullable)
- `tags` (json, nullable)
- `is_active` (tinyint, default 1)
- `created_at` / `updated_at` (datetime)

### brands（品牌）
- `id` (PK, varchar)
- `name` (varchar, not null)
- `origin_country` (varchar, nullable)
- `description` (text, nullable)
- `logo_url` (varchar, nullable)
- `tags` (json, nullable)
- `is_active` (tinyint, default 1)
- `created_at` / `updated_at` (datetime)

## 3.2 关系表

### doctor_treatment_map
- `doctor_id` (FK -> doctors.id)
- `treatment_id` (FK -> treatments.id)
- `priority` (int, default 0)
- 联合唯一键：`(doctor_id, treatment_id)`

### merchant_treatment_offer
- `id` (PK, varchar)
- `merchant_id` (FK -> merchants.id, index)
- `treatment_id` (FK -> treatments.id, index)
- `brand_id` (FK -> brands.id, nullable, index)
- `doctor_id` (FK -> doctors.id, nullable, index)
- `min_price_cent` (int, nullable)
- `max_price_cent` (int, nullable)
- `currency` (varchar, default 'CNY')
- `is_active` (tinyint, default 1)
- `created_at` / `updated_at` (datetime)

## 3.3 推荐结果落库（可审计）

### recommendation_result
- `id` (PK, varchar)
- `user_id` (varchar, index)
- `history_id` (varchar, nullable, index)
- `request_intent` (varchar, nullable)
- `source_analysis` (text, nullable)
- `model_version` (varchar, nullable)
- `created_at` (datetime, index)

### recommendation_item
- `id` (PK, varchar)
- `result_id` (FK -> recommendation_result.id, index)
- `category` (enum: merchant/doctor/treatment/brand, index)
- `entity_id` (varchar, not null, index)
- `score` (decimal(5,4), not null)
- `reason` (varchar, not null)
- `rank` (int, not null)
- `payload` (json, not null)
- 联合唯一键：`(result_id, category, entity_id)`

---

## 4. 前后端通信标准

## 4.1 获取推荐

- URL：`POST /recommendations`
- Content-Type：`application/json`

请求体：
```json
{
  "user_id": "user_123456",
  "history_id": "record_1772801234",
  "intent": "想改善眼袋和法令纹",
  "limit_per_category": 5
}
```

响应体（成功）：
```json
{
  "status": "success",
  "data": {
    "result_id": "rec_1772899000",
    "categories": [
      {
        "type": "merchant",
        "title": "推荐商户",
        "items": [
          {
            "id": "m_1001",
            "name": "星和医美中心",
            "score": 0.9621,
            "reason": "距离近且眼周年轻化案例匹配度高",
            "cover_image_url": "https://...",
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
            "id": "d_2044",
            "name": "王医生",
            "score": 0.9512,
            "reason": "擅长眼袋与中面部联合改善",
            "avatar_url": "https://...",
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
            "id": "t_5010",
            "name": "眶隔脂肪释放",
            "score": 0.9448,
            "reason": "对眼袋与泪沟联合改善效果更稳定",
            "cover_image_url": "https://...",
            "risk_level": "中",
            "downtime_level": "中"
          }
        ]
      },
      {
        "type": "brand",
        "title": "推荐品牌",
        "items": [
          {
            "id": "b_8901",
            "name": "乔雅登",
            "score": 0.9123,
            "reason": "与当前诉求匹配度高且材料稳定性好",
            "logo_url": "https://...",
            "origin_country": "美国"
          }
        ]
      }
    ]
  }
}
```

失败响应：
```json
{
  "status": "error",
  "code": "RECOMMENDATION_NOT_AVAILABLE",
  "message": "推荐引擎暂不可用"
}
```

---

## 5. 分类与字段白名单

前端仅依赖以下字段，后端需保证稳定：

- 通用字段：`id`, `name`, `score`, `reason`
- merchant：`cover_image_url`, `city`, `district`, `rating`
- doctor：`avatar_url`, `title`, `years_experience`
- treatment：`cover_image_url`, `risk_level`, `downtime_level`
- brand：`logo_url`, `origin_country`

未在白名单中的扩展字段请放入 `payload`，前端默认忽略。

---

## 6. 排序与去重规则

- 同一分类内按 `score DESC, rank ASC` 返回。
- 同一 `entity_id` 在同一 `result_id + category` 下不可重复。
- 四类分类都应返回；若某类无数据，返回空数组而非省略分类。

---

## 7. 版本与兼容

- 建议请求头增加：`X-Recommendation-Version: 1`
- 后端新增字段应向后兼容，不删除白名单字段。
- 若结构有破坏性变更，必须升级版本号并保留旧版本至少一个迭代周期。
