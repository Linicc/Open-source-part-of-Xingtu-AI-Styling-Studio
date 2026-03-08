"""
完整工作流测试封装
严格按照 Mermaid 流程图实现:
1. FR人脸识别（守门员）- 失败直接返回错误
2. 提取特征并储存
3. 诉求过滤器 - 理解用户真实目标（修复眼袋）
4. YOLO生成黄色遮罩，记录中心点坐标
5. 豆包API图像处理
6. DeepSeek API容貌分析
7. 整合结果返回前端
"""

import os
import cv2
import json
import time
import base64
import sqlite3
import numpy as np
import requests
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel

# 尝试导入 face_recognition
try:
    import face_recognition
    FR_AVAILABLE = True
except ImportError:
    FR_AVAILABLE = False
    print("⚠️ face_recognition 未安装，使用模拟模式")

# 导入 YOLO
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("⚠️ ultralytics 未安装")

# 加载环境变量
load_dotenv()

# ============ 全局配置 ============
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "processed"  # 旧的输出目录，保留兼容性
USER_DATA_DIR = DATA_DIR / "users"
MEDIA_DIR = DATA_DIR / "uploads"
RECOMMENDATION_STORE_DIR = DATA_DIR / "recommendation_store"
MOCK_RECOMMENDATION_DB_FILE = DATA_DIR / "mock_recommendation_db.json"
RECOMMENDATION_SQLITE_FILE = RECOMMENDATION_STORE_DIR / "recommendation.db"

# 确保目录存在
for d in [OUTPUT_DIR, USER_DATA_DIR, MEDIA_DIR, RECOMMENDATION_STORE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# API 配置
VOLC_API_KEY = os.getenv("VOLC_API_KEY")
VOLC_API_URL = os.getenv("VOLC_API_URL", "https://ark.cn-beijing.volces.com/api/v3/images/generations")
VOLC_MODEL = os.getenv("VOLC_MODEL", "doubao-seedream-4-5-251128")

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")

# YOLO 模型路径
YOLO_MODEL_PATH = None
yolo_model = None

# ============ FastAPI 应用 ============
app = FastAPI(title="10K项目完整工作流")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ 初始化 YOLO ============
def find_yolo_model():
    """查找最佳 YOLO 模型"""
    configured_path = os.getenv("YOLO_MODEL_PATH")
    if configured_path:
        configured = Path(configured_path)
        if not configured.is_absolute():
            configured = PROJECT_ROOT / configured
        if configured.exists():
            return str(configured)

    default_path = PROJECT_ROOT / "models" / "yolo" / "weights" / "best.pt"
    if default_path.exists():
        return str(default_path)
    return None


@app.on_event("startup")
async def startup_event():
    """启动时加载模型"""
    global yolo_model, YOLO_MODEL_PATH

    YOLO_MODEL_PATH = find_yolo_model()
    if YOLO_MODEL_PATH and YOLO_AVAILABLE:
        print(f"🚀 Loading YOLO from: {YOLO_MODEL_PATH}")
        yolo_model = YOLO(YOLO_MODEL_PATH)
    else:
        print("⚠️ YOLO 模型未找到或未安装")
    initialize_recommendation_sqlite(sync_catalog=True)


# ============ Step 1: FR人脸识别系统（守门员）============
def fr_face_check(img_rgb):
    """
    FR人脸识别系统 - 守门员角色
    返回: (是否识别到人脸, 人脸位置列表)
    """
    if not FR_AVAILABLE:
        # 模拟模式：假设所有图片都有人脸
        print("⚠️ [模拟模式] FR检测跳过")
        h, w = img_rgb.shape[:2]
        return True, [(0, w, h, 0)]

    face_locations = face_recognition.face_locations(img_rgb)

    if not face_locations:
        return False, []

    return True, face_locations


# ============ Step 2: 提取人脸特征并储存 ============
def extract_and_save_features(img_rgb, face_locations, user_id="anonymous"):
    """
    提取人脸特征指标并储存到文件
    返回: features 字典
    """
    timestamp = int(time.time())
    features = {
        "timestamp": timestamp,
        "face_location": face_locations[0] if face_locations else None,
        "nose_length": 0.0,
        "face_width": 0.0,
        "face_height": 0.0
    }

    if FR_AVAILABLE and face_locations:
        try:
            face_landmarks = face_recognition.face_landmarks(img_rgb, face_locations)[0]

            # 计算鼻梁长度
            nose_bridge = face_landmarks.get('nose_bridge', [])
            if len(nose_bridge) >= 2:
                nose_length = np.linalg.norm(
                    np.array(nose_bridge[0]) - np.array(nose_bridge[-1])
                )
                features["nose_length"] = float(nose_length)

            # 计算脸部宽度和高度
            top, right, bottom, left = face_locations[0]
            features["face_width"] = float(right - left)
            features["face_height"] = float(bottom - top)

        except Exception as e:
            print(f"⚠️ 特征提取失败: {e}")
    else:
        # 模拟模式
        h, w = img_rgb.shape[:2]
        features["nose_length"] = float(h * 0.1)
        features["face_width"] = float(w * 0.6)
        features["face_height"] = float(h * 0.7)

    # 1. 兼容旧模式: 储存到 processed
    feature_file_old = OUTPUT_DIR / f"features_{timestamp}.json"
    with open(feature_file_old, "w", encoding="utf-8") as f:
        json.dump(features, f, indent=2, ensure_ascii=False)

    # 2. 新模式: 储存到用户档案 (如果提供了 user_id)
    if user_id and user_id != "anonymous":
        user_dir = USER_DATA_DIR / f"user_{user_id}" / "medical_record"
        user_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存诊断记录
        record_file = user_dir / f"diagnosis_{timestamp}.json"
        with open(record_file, "w", encoding="utf-8") as f:
            json.dump({
                "diagnosis_id": f"D{timestamp}",
                "timestamp": timestamp,
                "user_id": user_id,
                "features": features
            }, f, indent=2, ensure_ascii=False)
        print(f"📂 用户档案已更新: {record_file}")

    print(f"💾 特征已保存至: {feature_file_old}")
    return features


# ============ Step 3: 诉求过滤器 ============
def parse_user_intent(user_input):
    """
    诉求过滤器 - 理解用户真实目标
    当前只做眼袋修复，所以真实目标就是修复眼袋
    """
    if not user_input or len(user_input.strip()) < 1:
        return "修复眼袋"

    text = user_input.lower()

    if "眼袋" in text or "eye" in text or "bag" in text or "黑眼圈" in text:
        return "修复眼袋"
    if "法令纹" in text or "nasolabial" in text or "smile line" in text:
        return "淡化法令纹"
    if "都要" in text or "一起" in text or "整体" in text or "all" in text:
        return "综合优化"
    return "修复眼袋"


def get_utc_iso_timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_recommendation_conn():
    conn = sqlite3.connect(str(RECOMMENDATION_SQLITE_FILE))
    conn.row_factory = sqlite3.Row
    return conn


def sync_mock_catalog_to_sqlite(cur):
    seed = read_json_file(MOCK_RECOMMENDATION_DB_FILE, {})
    merchants = seed.get("merchants", [])
    doctors = seed.get("doctors", [])
    treatments = seed.get("treatments", [])
    brands = seed.get("brands", [])
    offers = seed.get("merchant_treatment_offer", [])
    cur.execute("DELETE FROM merchant_treatment_offer")
    cur.execute("DELETE FROM doctors")
    cur.execute("DELETE FROM merchants")
    cur.execute("DELETE FROM treatments")
    cur.execute("DELETE FROM brands")
    cur.executemany(
        "INSERT OR REPLACE INTO merchants (id, name, city, district, address, rating, cover_image_url, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(x.get("id"), x.get("name"), x.get("city"), x.get("district"), x.get("address"), x.get("rating"), x.get("cover_image_url"), x.get("is_active", 1)) for x in merchants]
    )
    cur.executemany(
        "INSERT OR REPLACE INTO doctors (id, merchant_id, name, title, specialties, years_experience, rating, avatar_url, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(x.get("id"), x.get("merchant_id"), x.get("name"), x.get("title"), json.dumps(x.get('specialties', []), ensure_ascii=False), x.get("years_experience"), x.get("rating"), x.get("avatar_url"), x.get("is_active", 1)) for x in doctors]
    )
    cur.executemany(
        "INSERT OR REPLACE INTO treatments (id, name, category, risk_level, downtime_level, description, cover_image_url, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(x.get("id"), x.get("name"), x.get("category"), x.get("risk_level"), x.get("downtime_level"), x.get("description"), x.get("cover_image_url"), x.get("is_active", 1)) for x in treatments]
    )
    cur.executemany(
        "INSERT OR REPLACE INTO brands (id, name, origin_country, description, logo_url, is_active) VALUES (?, ?, ?, ?, ?, ?)",
        [(x.get("id"), x.get("name"), x.get("origin_country"), x.get("description"), x.get("logo_url"), x.get("is_active", 1)) for x in brands]
    )
    cur.executemany(
        "INSERT OR REPLACE INTO merchant_treatment_offer (id, merchant_id, treatment_id, brand_id, doctor_id, min_price_cent, max_price_cent, currency, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(x.get("id"), x.get("merchant_id"), x.get("treatment_id"), x.get("brand_id"), x.get("doctor_id"), x.get("min_price_cent"), x.get("max_price_cent"), x.get("currency", "CNY"), x.get("is_active", 1)) for x in offers]
    )


def initialize_recommendation_sqlite(sync_catalog=False):
    conn = get_recommendation_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS merchants (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            city TEXT,
            district TEXT,
            address TEXT,
            rating REAL,
            cover_image_url TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id TEXT PRIMARY KEY,
            merchant_id TEXT,
            name TEXT NOT NULL,
            title TEXT,
            specialties TEXT,
            years_experience INTEGER,
            rating REAL,
            avatar_url TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS treatments (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            risk_level TEXT,
            downtime_level TEXT,
            description TEXT,
            cover_image_url TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS brands (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            origin_country TEXT,
            description TEXT,
            logo_url TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS merchant_treatment_offer (
            id TEXT PRIMARY KEY,
            merchant_id TEXT,
            treatment_id TEXT,
            brand_id TEXT,
            doctor_id TEXT,
            min_price_cent INTEGER,
            max_price_cent INTEGER,
            currency TEXT DEFAULT 'CNY',
            is_active INTEGER DEFAULT 1
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS recommendation_result (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            history_id TEXT,
            request_intent TEXT,
            source_analysis TEXT,
            model_version TEXT,
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS recommendation_item (
            id TEXT PRIMARY KEY,
            result_id TEXT,
            category TEXT,
            entity_id TEXT,
            score REAL,
            reason TEXT,
            rank INTEGER,
            payload TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_merchants_active_rating ON merchants (is_active, rating DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_doctors_active_rating ON doctors (is_active, rating DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_treatments_active ON treatments (is_active)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_brands_active ON brands (is_active)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rr_user_created ON recommendation_result (user_id, created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rr_history ON recommendation_result (history_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ri_result_category_rank ON recommendation_item (result_id, category, rank)")
    if sync_catalog:
        sync_mock_catalog_to_sqlite(cur)
    conn.commit()
    conn.close()


def read_json_file(file_path, default_value):
    try:
        if not file_path.exists():
            return default_value
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_value


def write_json_file(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def normalize_limit(limit_value):
    if not isinstance(limit_value, int):
        return 5
    if limit_value < 1:
        return 1
    if limit_value > 10:
        return 10
    return limit_value


def score_bias_from_intent(intent_text):
    text = (intent_text or "").lower()
    if ("眼袋" in text) or ("黑眼圈" in text) or ("eye" in text) or ("bag" in text):
        return {"merchant": 0.03, "doctor": 0.05, "treatment": 0.06, "brand": 0.02}
    if ("法令纹" in text) or ("抗衰" in text) or ("年轻化" in text):
        return {"merchant": 0.02, "doctor": 0.04, "treatment": 0.05, "brand": 0.03}
    return {"merchant": 0.01, "doctor": 0.01, "treatment": 0.01, "brand": 0.01}


def clamp_score(value):
    if value < 0:
        return 0.0
    if value > 0.9999:
        return 0.9999
    return round(value, 4)


def build_recommendation_categories(request_intent, limit_per_category):
    conn = get_recommendation_conn()
    cur = conn.cursor()
    bias = score_bias_from_intent(request_intent)
    categories = []

    merchants = []
    rows = cur.execute("SELECT id, name, city, district, rating, cover_image_url FROM merchants WHERE is_active = 1 ORDER BY rating DESC LIMIT ?", (limit_per_category,)).fetchall()
    for row in rows:
        rating = float(row["rating"] if row["rating"] is not None else 4.5)
        score = clamp_score(0.85 + (rating / 50.0) + bias["merchant"])
        merchants.append({
            "id": row["id"],
            "name": row["name"],
            "score": score,
            "reason": "地理位置方便，且该机构在目标项目上口碑稳定",
            "cover_image_url": row["cover_image_url"],
            "city": row["city"],
            "district": row["district"],
            "rating": row["rating"]
        })
    categories.append({
        "type": "merchant",
        "title": "推荐商户",
        "items": merchants
    })

    doctors = []
    rows = cur.execute("SELECT id, name, title, years_experience, rating, avatar_url FROM doctors WHERE is_active = 1 ORDER BY rating DESC, years_experience DESC LIMIT ?", (limit_per_category,)).fetchall()
    for row in rows:
        rating = float(row["rating"] if row["rating"] is not None else 4.5)
        years_experience = int(row["years_experience"] if row["years_experience"] is not None else 5)
        score = clamp_score(0.82 + (rating / 50.0) + min(years_experience / 200.0, 0.05) + bias["doctor"])
        doctors.append({
            "id": row["id"],
            "name": row["name"],
            "score": score,
            "reason": "医生经验与诉求匹配，临床风格偏自然精细",
            "avatar_url": row["avatar_url"],
            "title": row["title"],
            "years_experience": row["years_experience"]
        })
    categories.append({
        "type": "doctor",
        "title": "推荐医生",
        "items": doctors
    })

    treatments = []
    rows = cur.execute("SELECT id, name, risk_level, downtime_level, cover_image_url FROM treatments WHERE is_active = 1 LIMIT ?", (limit_per_category,)).fetchall()
    for row in rows:
        risk_level = row["risk_level"] if row["risk_level"] else "中"
        base_score = 0.84 if risk_level == "低" else 0.80
        score = clamp_score(base_score + bias["treatment"])
        treatments.append({
            "id": row["id"],
            "name": row["name"],
            "score": score,
            "reason": "该项目与当前面部问题匹配度高，方案成熟",
            "cover_image_url": row["cover_image_url"],
            "risk_level": row["risk_level"],
            "downtime_level": row["downtime_level"]
        })
    treatments.sort(key=lambda x: x["score"], reverse=True)
    categories.append({
        "type": "treatment",
        "title": "推荐项目",
        "items": treatments
    })

    brands = []
    rows = cur.execute("SELECT id, name, origin_country, logo_url FROM brands WHERE is_active = 1 LIMIT ?", (limit_per_category,)).fetchall()
    for row in rows:
        score = clamp_score(0.83 + bias["brand"])
        brands.append({
            "id": row["id"],
            "name": row["name"],
            "score": score,
            "reason": "材料稳定性与临床反馈较好，适配常见诉求",
            "logo_url": row["logo_url"],
            "origin_country": row["origin_country"]
        })
    brands.sort(key=lambda x: x["score"], reverse=True)
    categories.append({
        "type": "brand",
        "title": "推荐品牌",
        "items": brands
    })
    conn.close()
    return categories


def persist_recommendation_to_store(user_id, history_id, request_intent, categories):
    created_at = get_utc_iso_timestamp()
    result_id = f"rec_{int(time.time() * 1000)}"
    conn = get_recommendation_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO recommendation_result (id, user_id, history_id, request_intent, source_analysis, model_version, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (result_id, user_id, history_id, request_intent, "", "sqlite_v1_zh", created_at)
    )
    for category in categories:
        category_type = category.get("type")
        for idx, item in enumerate(category.get("items", []), start=1):
            cur.execute(
                "INSERT INTO recommendation_item (id, result_id, category, entity_id, score, reason, rank, payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (f"{result_id}_{category_type}_{idx}", result_id, category_type, item.get("id"), item.get("score"), item.get("reason"), idx, json.dumps(item, ensure_ascii=False))
            )
    conn.commit()
    conn.close()
    write_json_file(RECOMMENDATION_STORE_DIR / f"{result_id}.json", {
        "id": result_id,
        "user_id": user_id,
        "history_id": history_id,
        "request_intent": request_intent,
        "created_at": created_at,
        "categories": categories
    })
    return result_id


def load_recommendation_result_from_sqlite(result_id):
    conn = get_recommendation_conn()
    cur = conn.cursor()
    header = cur.execute(
        "SELECT id, user_id, history_id, request_intent, created_at FROM recommendation_result WHERE id = ?",
        (result_id,)
    ).fetchone()
    if not header:
        conn.close()
        return None
    rows = cur.execute(
        "SELECT category, payload, rank FROM recommendation_item WHERE result_id = ? ORDER BY category, rank ASC",
        (result_id,)
    ).fetchall()
    conn.close()
    grouped = {"merchant": [], "doctor": [], "treatment": [], "brand": []}
    for row in rows:
        category = row["category"]
        if category not in grouped:
            grouped[category] = []
        grouped[category].append(json.loads(row["payload"]))
    categories = []
    for category_type, title in [("merchant", "推荐商户"), ("doctor", "推荐医生"), ("treatment", "推荐项目"), ("brand", "推荐品牌")]:
        categories.append({
            "type": category_type,
            "title": title,
            "items": grouped.get(category_type, [])
        })
    return {
        "id": header["id"],
        "user_id": header["user_id"],
        "history_id": header["history_id"],
        "request_intent": header["request_intent"],
        "created_at": header["created_at"],
        "categories": categories
    }


def load_latest_recommendation_by_user(user_id):
    conn = get_recommendation_conn()
    cur = conn.cursor()
    row = cur.execute(
        "SELECT id FROM recommendation_result WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return load_recommendation_result_from_sqlite(row["id"])


# ============ Step 4: YOLO生成黄色遮罩 ============
def yolo_generate_yellow_mask(img, user_target):
    """
    YOLO系统：生成黄色遮罩标记眼袋，记录遮罩中心点坐标
    返回: (遮罩图像, 中心点坐标列表)
    """
    if not yolo_model or not YOLO_AVAILABLE:
        print("⚠️ YOLO未加载，返回原图")
        return img, []

    # YOLO预测
    results = yolo_model.predict(img, conf=0.25, iou=0.6, verbose=False, retina_masks=True)
    result = results[0]

    if not result.masks:
        print("⚠️ YOLO未检测到任何区域")
        return img, []

    masks = result.masks.data.cpu().numpy()
    boxes = result.boxes.data.cpu().numpy()
    h, w = img.shape[:2]

    overlay = img.copy()
    coords = []

    for i, mask in enumerate(masks):
        cls_id = int(boxes[i, 5])
        label = result.names[cls_id]

        # 根据用户意图过滤
        if user_target == "修复眼袋" and label != "eye_bag":
            continue

        # 调整 mask 大小
        mask_resized = cv2.resize(mask, (w, h))

        # 黄色遮罩 (BGR: 0, 255, 255)
        yellow_color = (0, 255, 255)
        overlay[mask_resized > 0.5] = yellow_color

        # 记录遮罩中心点坐标
        x1, y1, x2, y2 = boxes[i, :4]
        cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
        coords.append({
            "label": label,
            "center": [cx, cy],
            "box": [int(x1), int(y1), int(x2), int(y2)]
        })

    # 混合遮罩层（半透明）
    cv2.addWeighted(overlay, 0.5, img, 0.5, 0, img)

    # 保存调试图片
    debug_path = OUTPUT_DIR / f"debug_mask_{int(time.time())}.jpg"
    cv2.imwrite(str(debug_path), img)
    print(f"🐛 调试图片已保存: {debug_path}")

    print(f"📍 YOLO生成遮罩中心点: {coords}")
    return img, coords


# ============ Step 5: 豆包API图像处理 ============
def select_prompt_key_by_target(user_target):
    target = (user_target or "").strip()
    if "法令纹" in target:
        return "nasolabial_fold"
    if "综合" in target:
        return "all"
    return "eye_bag"


def load_prompt_config(user_target):
    default_prompt = "raw photo, 2k, hyper-realistic, soft lighting, natural skin texture, remove the yellow mask overlay, eliminate eye bags, smooth under-eye area, blend skin tone seamlessly"
    prompt = default_prompt
    width = None
    height = None
    prompt_key = select_prompt_key_by_target(user_target)
    candidate_paths = [
        PROJECT_ROOT / "data" / "prompt_library.json",
        PROJECT_ROOT / "data" / "system" / "prompt_library.json"
    ]
    selected_path = None
    for p in candidate_paths:
        if p.exists():
            selected_path = p
            break
    if selected_path:
        try:
            with open(selected_path, "r", encoding="utf-8") as f:
                lib = json.load(f)
            config = lib.get(prompt_key) or lib.get("eye_bag")
            if isinstance(config, dict):
                prompt = config.get("prompt", prompt)
                width = config.get("width")
                height = config.get("height")
            elif isinstance(config, str):
                prompt = config
            print(f"📚 Prompt库: {selected_path.name}, key={prompt_key}")
        except Exception as e:
            print(f"⚠️ Prompt库加载失败: {e}")
    return prompt, width, height


def call_doubao_api(masked_img, user_target):
    """
    调用豆包API进行图像处理
    """
    if not VOLC_API_KEY:
        return None, "VOLC_API_KEY 未设置"

    # 编码图像为base64
    _, buffer = cv2.imencode('.jpg', masked_img)
    img_b64 = base64.b64encode(buffer).decode('utf-8')

    prompt, width, height = load_prompt_config(user_target)
    prompt_prefix = "Keep the face size ratio unchanged. "
    if not prompt.startswith(prompt_prefix):
        prompt = f"{prompt_prefix}{prompt}"

    headers = {"Authorization": f"Bearer {VOLC_API_KEY}"}
    payload = {
        "model": VOLC_MODEL,
        "prompt": prompt,
        "image": f"data:image/jpeg;base64,{img_b64}"
    }

    if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
        # 根据用户指示： "size": "1728x2304"
        payload["size"] = f"{width}x{height}"


    try:
        resp = requests.post(VOLC_API_URL, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            url = resp.json().get('data', [{}])[0].get('url')
            return url, None
        else:
            return None, f"豆包API错误: {resp.status_code} - {resp.text}"
    except Exception as e:
        return None, f"豆包API请求失败: {str(e)}"


# ============ Step 6: DeepSeek API容貌分析 ============
def call_deepseek_api(features, user_intent):
    """
    调用DeepSeek API进行容貌分析
    输入: 计算脚本处理后的特征数据
    输出: 面部改善建议
    """
    # 构造分析prompt
    analysis_prompt = f"""
你是一位专业医美顾问。请基于以下面部特征数据，给出实用的面部改善建议。

【面部特征数据】
- 鼻梁长度：{features.get('nose_length', 0):.1f}px
- 脸部宽度：{features.get('face_width', 0):.1f}px
- 脸部高度：{features.get('face_height', 0):.1f}px

【用户目标】{user_intent}

请用中文给出 2-3 条简洁建议，语气温和、专业、可执行。
"""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    # 规范化 DeepSeek API 使用逻辑：
    # 1. 切换模型为 deepseek-reasoner 以开启思考模式
    # 2. 移除 temperature 参数（在思考模式下不生效）
    # 3. 提取 reasoning_content（思维链）以供参考
    payload = {
        "model": "deepseek-reasoner",
        "messages": [
            {"role": "system", "content": "你是一位资深医美顾问，擅长面部分析与改善建议。请始终使用中文回答。"},
            {"role": "user", "content": analysis_prompt}
        ]
        # "temperature": 0.1  <-- 已移除，deepseek-reasoner 不支持此参数
    }

    try:
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60) # 思考模式可能需要更长时间，增加超时
        if resp.status_code == 200:
            result = resp.json()
            choice = result['choices'][0]['message']
            content = choice['content']
            
            # 尝试提取思维链内容 (仅内部调试用，不输出)
            # reasoning_content = choice.get('reasoning_content', '')
            
            return content, None
        else:
            return None, f"DeepSeek API错误: {resp.status_code} - {resp.text}"
    except Exception as e:
        return None, f"DeepSeek API请求失败: {str(e)}"


# ============ 主处理端点 ============
import base64
import re

# ============ 用户档案管理 API ============

class UserProfileRequest(BaseModel):
    user_id: str
    data: dict

@app.post("/user/profile")
async def save_user_profile(request: UserProfileRequest):
    """
    保存/更新用户档案到云端
    支持自动处理 Base64 图片
    """
    try:
        user_dir = USER_DATA_DIR / f"{request.user_id}"
        user_dir.mkdir(parents=True, exist_ok=True)
        
        # 处理头像: 如果是 Base64，转存为文件
        profile_data = request.data.copy()
        photo_data = profile_data.get("photo")
        
        if photo_data and isinstance(photo_data, str) and photo_data.startswith("data:image"):
            # 这是一个新上传的 Base64 图片
            saved_url = save_base64_image(photo_data, request.user_id)
            if saved_url:
                profile_data["photo"] = saved_url
        
        # 保存 JSON
        profile_file = user_dir / "profile.json"
        with open(profile_file, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, indent=2, ensure_ascii=False)
            
        print(f"💾 用户档案已保存: {request.user_id}")
        # ⚠️ 注意: 这里必须返回包含更新后 URL 的 data，否则前端还是拿着旧的 Base64
        return {"status": "success", "message": "档案已同步至云端", "data": profile_data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def save_base64_image(base64_str, user_id):
    """
    将 Base64 字符串保存为图片文件
    返回: 图片的相对 URL
    """
    try:
        if "," in base64_str:
            header, encoded = base64_str.split(",", 1)
        else:
            return None 
            
        ext = "jpg"
        if "png" in header: ext = "png"
        elif "jpeg" in header: ext = "jpg"
        
        img_data = base64.b64decode(encoded)
        
        timestamp = int(time.time())
        date_path = time.strftime("%Y/%m/%d")
        upload_dir = MEDIA_DIR / date_path
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{user_id}_avatar_{timestamp}.{ext}"
        filepath = upload_dir / filename
        
        with open(filepath, "wb") as f:
            f.write(img_data)
            
        url = f"/static/uploads/{date_path}/{filename}"
        print(f"🖼️ Base64 头像已转存: {url}")
        return url
    except Exception as e:
        print(f"⚠️ Base64 图片保存失败: {e}")
        return None


@app.get("/user/profile")
async def get_user_profile(user_id: str):
    """
    获取用户档案
    """
    profile_file = USER_DATA_DIR / f"{user_id}" / "profile.json"
    if profile_file.exists():
        with open(profile_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

@app.get("/user/history")
async def get_user_history(user_id: str):
    """
    获取用户历史诊断记录列表
    """
    history_dir = USER_DATA_DIR / f"{user_id}" / "history"
    if not history_dir.exists():
        return []
    
    history_list = []
    try:
        # 遍历所有 json 文件
        for file in sorted(history_dir.glob("record_*.json"), reverse=True):
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                history_list.append(data)
    except Exception as e:
        print(f"⚠️ 读取历史记录失败: {e}")
        
    return history_list

# ============ 完整工作流主端点 ============

class ProcessRequest(BaseModel):
    user_id: str
    intent: str = ""


class RecommendationRequest(BaseModel):
    user_id: str
    history_id: str = ""
    intent: str = ""
    limit_per_category: int = 5


@app.post("/recommendations")
async def create_recommendations(request: RecommendationRequest):
    if not request.user_id:
        return {"status": "error", "code": "INVALID_REQUEST", "message": "必须提供 user_id"}

    initialize_recommendation_sqlite()
    limit_per_category = normalize_limit(request.limit_per_category)
    categories = build_recommendation_categories(request.intent, limit_per_category)
    result_id = persist_recommendation_to_store(
        user_id=request.user_id,
        history_id=request.history_id,
        request_intent=request.intent,
        categories=categories
    )

    return {
        "status": "success",
        "data": {
            "result_id": result_id,
            "categories": categories
        }
    }


@app.get("/recommendations/result")
async def get_recommendation_result(result_id: str):
    if not result_id:
        return {"status": "error", "code": "INVALID_REQUEST", "message": "必须提供 result_id"}
    initialize_recommendation_sqlite()
    data = load_recommendation_result_from_sqlite(result_id)
    if data is None:
        return {"status": "error", "code": "NOT_FOUND", "message": "未找到该推荐结果"}
    return {"status": "success", "data": data}


@app.get("/recommendations/latest")
async def get_latest_recommendation(user_id: str):
    if not user_id:
        return {"status": "error", "code": "INVALID_REQUEST", "message": "必须提供 user_id"}
    initialize_recommendation_sqlite()
    data = load_latest_recommendation_by_user(user_id)
    if data is None:
        return {"status": "error", "code": "NOT_FOUND", "message": "该用户暂无推荐记录"}
    return {"status": "success", "data": data}


@app.post("/recommendations/sync-mock-db")
async def sync_mock_recommendation_db():
    initialize_recommendation_sqlite(sync_catalog=True)
    return {"status": "success", "message": "模拟数据库已同步到SQLite"}

@app.post("/process")
async def process_full_workflow(request: ProcessRequest):
    """
    完整工作流主端点 (云端全托管模式 - 无需上传图片)
    1. 根据 user_id 读取云端档案
    2. 从档案中获取已存在的图片路径
    3. 执行分析
    4. 自动归档结果
    """
    user_id = request.user_id
    intent = request.intent
    
    print("\n" + "="*60)
    print(f"🎬 开始执行完整工作流 (User: {user_id})")
    print("="*60)

    # 1. 强制检查档案
    if not user_id:
         return {"status": "error", "message": "必须提供 user_id"}

    profile_file = USER_DATA_DIR / f"{user_id}" / "profile.json"
    if not profile_file.exists():
        return {
            "status": "error", 
            "message": "用户档案不存在，请先调用 /user/profile 完善信息",
            "code": "PROFILE_MISSING"
        }

    # 2. 读取档案并获取图片路径
    try:
        with open(profile_file, "r", encoding="utf-8") as f:
            user_profile = json.load(f)
        
        photo_url = user_profile.get("photo")
        if not photo_url:
             return {"status": "error", "message": "档案中未找到照片，请先在档案页面上传照片"}
             
        # 将 URL (/static/uploads/...) 转换为本地文件路径
        # 假设 URL 格式为 /static/uploads/2026/03/06/xxx.jpg
        # 本地路径应为 PROJECT_ROOT / data / uploads / 2026/03/06 / xxx.jpg
        
        # 去掉 /static/ 前缀
        relative_path = photo_url.replace("/static/", "", 1)
        # 拼接绝对路径 (DATA_DIR 的父级是 PROJECT_ROOT)
        image_path = PROJECT_ROOT / "data" / relative_path.replace("uploads/", "uploads/", 1) # 这里路径拼接要小心
        
        # 更稳健的路径转换方式：
        # URL: /static/uploads/2026/03/06/xxx.jpg
        # File: .../10k_project/data/uploads/2026/03/06/xxx.jpg
        if "/static/uploads/" in photo_url:
            suffix = photo_url.split("/static/uploads/")[1]
            image_path = MEDIA_DIR / suffix
        else:
            # 兼容旧数据或异常情况
            return {"status": "error", "message": f"无效的图片路径格式: {photo_url}"}

        print(f"📸 从服务器加载图片: {image_path}")
        
        if not image_path.exists():
            return {"status": "error", "message": "服务器上找不到该图片文件，可能已被删除"}

    except Exception as e:
        return {"status": "error", "message": f"档案读取失败: {str(e)}"}

    # Step 0: 读取图片
    try:
        # 使用 cv2 读取本地文件
        # 注意: cv2.imread 不支持中文路径，最好用 np.fromfile
        img = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)

        if img is None:
            return {"status": "error", "message": "无法解码图片文件"}

        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        original_url = photo_url # 原始图片就是档案里的这张

    except Exception as e:
        return {"status": "error", "message": f"图像读取失败: {str(e)}"}

    # ============================================
    # Step 1: FR人脸识别系统（守门员）
    # ============================================

    print("\n🔍 [Step 1] FR人脸识别系统（守门员）")
    has_face, face_locations = fr_face_check(img_rgb)

    if not has_face:
        return {
            "status": "error",
            "message": "未能识别到人脸",
            "step": "FR人脸识别"
        }

    # ============================================
    # Step 2: 提取特征
    # ============================================
    print("\n📊 [Step 2] 提取特征")
    features = extract_and_save_features(img_rgb, face_locations, user_id="debug_only")

    # ============================================
    # Step 3: 诉求过滤器
    # ============================================
    print(f"\n🧠 [Step 3] 诉求过滤器")
    user_target = parse_user_intent(intent)
    
    # ============================================
    # Step 4: YOLO生成黄色遮罩
    # ============================================
    print(f"\n👁️ [Step 4] YOLO生成黄色遮罩")
    masked_img, mask_coords = yolo_generate_yellow_mask(img.copy(), user_target)

    if not mask_coords:
        return {
            "status": "success",
            "message": "未检测到需要修复的区域",
            "user_intent": user_target,
            "features": features
        }
    
    # ============ 准备结果目录 (新逻辑) ============
    timestamp = int(time.time())
    task_dir = USER_DATA_DIR / f"{user_id}" / "results" / f"{timestamp}_task"
    task_dir.mkdir(parents=True, exist_ok=True)
    print(f"📂 创建任务目录: {task_dir}")
    
    # 保存遮罩图
    mask_path = task_dir / "mask.png"
    cv2.imwrite(str(mask_path), cv2.cvtColor(masked_img, cv2.COLOR_RGB2BGR))
    mask_url = f"/static/users/{user_id}/results/{timestamp}_task/mask.png"
    print(f"🎭 遮罩图已保存: {mask_path}")

    # ============================================
    # Step 5: 豆包API图像处理
    # ============================================
    print(f"\n🎨 [Step 5] 豆包API图像处理")
    processed_image_url_remote, doubao_error = call_doubao_api(masked_img, user_target)
    
    # 默认返回给前端的是远程URL (保持接口兼容性)
    processed_image_url = processed_image_url_remote
    backup_local_url = None

    if not doubao_error and processed_image_url_remote:
        # 默默下载备份 (Shadow Backup)
        try:
            print(f"⬇️ [后台备份] 正在下载修复后的图片...")
            resp = requests.get(processed_image_url_remote, timeout=30)
            if resp.status_code == 200:
                fixed_path = task_dir / "fixed.jpg"
                with open(fixed_path, "wb") as f:
                    f.write(resp.content)
                backup_local_url = f"/static/users/{user_id}/results/{timestamp}_task/fixed.jpg"
                print(f"✅ [后台备份] 图片已落地: {fixed_path}")
            else:
                print(f"⚠️ [后台备份] 下载失败: {resp.status_code}")
        except Exception as e:
            print(f"⚠️ [后台备份] 异常: {e}")

    # ============================================
    # Step 6: DeepSeek API容貌分析 (结合 Profile)
    # ============================================
    print(f"\n🤖 [Step 6] DeepSeek API容貌分析")
    # 合并档案和特征
    analysis_context = {**features, **user_profile} 
    analysis_result, deepseek_error = call_deepseek_api(analysis_context, user_target)

    if deepseek_error:
        analysis_result = f"分析服务暂时不可用，但修复已完成。"

    # ============================================
    # Step 7: 自动存档并返回
    # ============================================
    history_id = None
    if user_id != "anonymous":
        try:
            history_dir = USER_DATA_DIR / f"{user_id}" / "history"
            history_dir.mkdir(parents=True, exist_ok=True)
            
            history_id = f"record_{timestamp}"
            record_file = history_dir / f"{history_id}.json"
            
            record_data = {
                "id": history_id,
                "timestamp": timestamp,
                "user_intent": user_target,
                "analysis": analysis_result,
                "images": {
                    "original": original_url,
                    "processed": backup_local_url if backup_local_url else processed_image_url
                }
            }
            
            with open(record_file, "w", encoding="utf-8") as f:
                json.dump(record_data, f, indent=2, ensure_ascii=False)
            print(f"📚 历史记录已归档: {history_id}")
        except Exception as e:
            print(f"⚠️ 归档失败: {e}")

    print(f"\n📦 [Step 7] 返回结果")
    return {
        "status": "success",
        "data": {
            "processed_image_url": processed_image_url,
            "analysis": analysis_result,
            "user_intent": user_target,
            "mask_coordinates": mask_coords,
            "history_id": history_id
        },
        "metadata": {
            "features": features,
            "doubao_error": doubao_error,
            "deepseek_error": deepseek_error
        }
    }

    final_response = {
        "status": "success",
        "data": {
            "processed_image": processed_image_url,      # 1. 豆包处理后的图像
            "analysis": analysis_result,                 # 2. DeepSeek分析建议
            "user_intent": user_target,                  # 3. 用户意图
            "mask_coordinates": mask_coords              # 4. 遮罩中心点坐标
        },
        "metadata": {
            "features": features,
            "doubao_error": doubao_error,
            "deepseek_error": deepseek_error
        }
    }

    print("="*60)
    print("✅ 工作流执行完成")
    print("="*60 + "\n")

    return final_response


# ============ 健康检查端点 ============
@app.get("/")
async def root():
    """健康检查"""
    return {
        "service": "10K项目完整工作流",
        "status": "running",
        "fr_available": FR_AVAILABLE,
        "yolo_available": YOLO_AVAILABLE and yolo_model is not None,
        "doubao_api_configured": VOLC_API_KEY is not None,
        "deepseek_api_configured": DEEPSEEK_API_KEY is not None
    }


@app.get("/test")
async def test():
    """测试端点"""
    return {
        "message": "API正常运行",
        "models": {
            "YOLO": "已加载" if yolo_model else "未加载",
            "FR": "已加载" if FR_AVAILABLE else "未加载",
            "豆包API": "已配置" if VOLC_API_KEY else "未配置",
            "DeepSeek API": "已配置" if DEEPSEEK_API_KEY else "未配置"
        }
    }


# ============ 主函数 ============
if __name__ == "__main__":
    host = os.getenv("FASTAPI_HOST", "127.0.0.1")
    port = int(os.getenv("FASTAPI_PORT", "8000"))
    print("""
    ====================================
    10K项目 - 完整工作流测试服务
    ====================================
    端点:
    - POST /process : 完整工作流处理
    - GET  /        : 健康检查
    - GET  /test    : 测试端点

    启动服务器: http://127.0.0.1:8000
    ====================================
    """)

    uvicorn.run(app, host=host, port=port, log_level="info")
