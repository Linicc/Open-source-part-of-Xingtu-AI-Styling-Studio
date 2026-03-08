#!/bin/bash
# 10K项目快速启动脚本

echo "======================================"
echo "  10K项目 - 完整工作流启动器"
echo "======================================"
echo ""

# 检查Python环境
if ! command -v python &> /dev/null
then
    echo "❌ Python未安装，请先安装Python 3.8+"
    exit 1
fi

echo "✅ Python已安装: $(python --version)"
echo ""

# 检查是否在虚拟环境中
if [[ "$VIRTUAL_ENV" != "" ]]
then
    echo "✅ 虚拟环境已激活: $VIRTUAL_ENV"
else
    echo "⚠️  未检测到虚拟环境（建议使用虚拟环境）"
fi
echo ""

# 检查依赖
echo "🔍 检查依赖..."
python -c "import fastapi" 2>/dev/null || { echo "❌ fastapi未安装，请运行: pip install -r requirements.txt"; exit 1; }
python -c "import cv2" 2>/dev/null || { echo "❌ opencv-python未安装，请运行: pip install -r requirements.txt"; exit 1; }
python -c "import numpy" 2>/dev/null || { echo "❌ numpy未安装，请运行: pip install -r requirements.txt"; exit 1; }
echo "✅ 核心依赖已安装"
echo ""

# 检查可选依赖
echo "🔍 检查可选依赖..."
python -c "import face_recognition" 2>/dev/null && echo "✅ face_recognition已安装" || echo "⚠️  face_recognition未安装（将使用模拟模式）"
python -c "from ultralytics import YOLO" 2>/dev/null && echo "✅ ultralytics已安装" || echo "⚠️  ultralytics未安装"
echo ""

# 检查.env文件
if [ ! -f ".env" ]; then
    echo "❌ .env文件不存在，请先配置API密钥"
    exit 1
fi
echo "✅ .env配置文件存在"
echo ""

# 检查YOLO模型
if [ -d "models/yolo" ]; then
    echo "✅ YOLO模型目录存在"
else
    echo "⚠️  YOLO模型目录不存在，请确保模型文件已放置"
fi
echo ""

# 启动服务
echo "======================================"
echo "🚀 启动服务..."
echo "======================================"
echo ""
echo "服务地址: http://127.0.0.1:8000"
echo "健康检查: http://127.0.0.1:8000/"
echo "测试端点: http://127.0.0.1:8000/test"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

# 启动
python full_workflow_test.py
