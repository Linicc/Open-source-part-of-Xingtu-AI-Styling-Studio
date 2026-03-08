#工作流（开源净化版）

本目录用于 GitHub 开源发布，已完成一轮敏感信息与私有资产清理，默认不包含任何可直接使用的生产凭据。

## 开源目标

- 保留完整核心流程代码：FR 检测 → 特征提取 → 诉求解析 → YOLO分割 → 图像处理与分析
- 清除所有可识别的密钥、密码、服务器信息、运维日志与私有部署痕迹
- 移除 YOLO 训练过程数据与本地历史业务数据，仅保留部署所需推理权重
- 提供可直接二次开发的配置模板与本地启动方式

## 安全净化清单

### 1) API 密钥与密码

- 已清空 `.env` 中真实密钥，替换为占位符：
  - `VOLC_API_KEY=YOUR_VOLC_API_KEY`
  - `DEEPSEEK_API_KEY=YOUR_DEEPSEEK_API_KEY`
- 新增 `.env.example` 作为安全模板文件
- 代码中硬编码密钥已移除，统一改为环境变量读取

### 2) 服务器地址与端口

- 所有文档中的公网 IP 已替换为本地示例地址 `127.0.0.1`
- 默认启动地址改为读取环境变量，默认 `127.0.0.1:8000`
- 删除了含公网开放端口规则的安全组导出文件

### 3) 运维凭据与日志

以下文件已删除（包含明文口令、服务器地址、运维命令与日志）：

- `winscp_deploy_script.txt`
- `winscp_log.txt`
- `internal_test.txt`
- `list_server_files.txt`
- `check_log.txt`
- `deploy_service.txt`
- `final_check.txt`
- `restart_service.txt`
- `debug_profile_error.txt`
- `emergency_debug.txt`
- `emergency_fix.txt`
- `fix_dependencies.txt`
- `install_fr.txt`
- `install_fr_script.txt`
- `check_fixed_status.txt`
- `check_fr_status.txt`
- `check_service_status.txt`
- `check_status.txt`
- `create_data_structure.txt`
- `verify_structure.txt`
- `ecs_sgRule_sg-2zebtdr0fktq3mgw1zu2_cn-beijing_2026-03-05.json`
- `aliyun_security_rule_8000.json`

### 4) YOLO 训练数据与私有业务数据

以下目录/文件已删除：

- `models/yolo/runs/`（训练批次图、训练参数与结果）
- `data/recommendation_store/`（历史推荐记录与 sqlite 数据）
- `data/mock_recommendation_db.json`
- `project_deploy.tar.gz`

保留用于部署推理的权重：

- `models/yolo/weights/best.pt`
- `models/yolo/weights/last.pt`

## 当前目录结构（净化后）

```text
github_open_source_release/
├── full_workflow_test.py
├── .env.example
├── .gitignore
├── requirements.txt
├── start_service.sh
├── API_DOCUMENTATION.md
├── FRONTEND_INTEGRATION_GUIDE.md
├── data/
│   └── prompt_library.json
└── models/
    └── yolo/
        └── weights/
            ├── best.pt
            └── last.pt
```

## 使用前准备

1. 复制配置模板

```bash
cp .env.example .env
```

2. 在 `.env` 中填写你自己的密钥

```env
VOLC_API_KEY=YOUR_REAL_KEY
DEEPSEEK_API_KEY=YOUR_REAL_KEY
```

3. 安装依赖并启动

```bash
pip install -r requirements.txt
python full_workflow_test.py
```

4. 访问接口

- 健康检查：`GET http://127.0.0.1:8000/`
- 测试端点：`GET http://127.0.0.1:8000/test`
- 核心接口：`POST http://127.0.0.1:8000/process`

## 二次训练与模型接入说明

- 当前仓库已附带可直接部署的 YOLO 推理权重
- 不包含训练过程数据与训练集，请自行准备合法训练数据
- 默认路径：`models/yolo/weights/best.pt`
- 如需替换模型，可将 `YOLO_MODEL_PATH` 指向你的权重文件

## 发布前自查建议

- 检查 `.env` 中是否仍有真实密钥
- 检查文档是否含真实域名/IP/内网地址
- 检查是否误提交数据库、日志、压缩包、模型权重
- 检查 `data/` 下是否存在用户原始图像与个人数据

## 许可证与合规

- 开源前请确认你对模型、数据、第三方服务调用具有合法授权
- 如涉及人脸或医疗美容场景，请补充隐私政策与合规声明
