# 后端更新档案（主程序）

## 1. 更新目标

- 在不改变前端既有接口的前提下，提升推荐模块查询性能
- 将推荐能力正式纳入主程序 `full_workflow_test.py`
- 完成本地与服务器同步发布

---

## 2. 主程序更新内容

主程序文件：

- `full_workflow_test.py`

核心更新：

- 新增推荐模块 SQLite 持久化（`data/recommendation_store/recommendation.db`）
- 新增推荐目录数据建表与索引初始化逻辑
- 新增模拟库到 SQLite 的全量同步机制
- 保持原有接口不变：
  - `POST /recommendations`
  - `GET /recommendations/result`
- 新增快速读取接口：
  - `GET /recommendations/latest`
- 新增手动同步接口：
  - `POST /recommendations/sync-mock-db`

---

## 3. 部署与同步更新

部署脚本更新：

- `remote_setup.sh`

已实现：

- 部署前备份服务器旧 `recommendation.db`
- 部署后恢复 `recommendation.db`
- 部署后自动执行 `initialize_recommendation_sqlite(sync_catalog=True)`
- 自动将最新 `mock_recommendation_db.json` 同步到服务器 SQLite 目录表

---

## 4. 验证结果（线上）

部署地址：

- `http://127.0.0.1:8000`

验证结论：

- `openapi.json` 已包含 `/recommendations`
- `openapi.json` 已包含 `/recommendations/latest`
- `POST /recommendations` 返回 `200`
- 推荐结果可正常返回 `result_id` 与 `categories`

---

## 5. 前端影响说明

- 现有前端接口调用方式无需修改
- 原 `/recommendations` 与 `/recommendations/result` 的响应结构保持兼容
- 前端可按需使用新增 `/recommendations/latest` 提升“最近结果回显”体验

---

## 6. DeepSeek 提示词更新（中文恢复）

更新原因：

- 英文提示词会导致 DeepSeek 返回英文结果，不符合当前业务输出要求

更新内容：

- 将 `call_deepseek_api` 的用户提示词模板从英文恢复为中文
- 将 `system` 角色提示词改为中文并明确“始终使用中文回答”

上线状态：

- 已重新打包并发布到服务器实例
- 推荐相关路由在线可用，服务重启成功

---

## 7. 豆包 Prompt 传递链路修复

问题定位：

- 图像生成阶段未按用户诉求选择 Prompt 模板，长期固定走 `eye_bag`
- 强制追加英文前缀会对编辑结果施加强约束，导致修复强度不稳定
- Prompt 库路径单一路径读取，环境目录差异时可能无法命中配置

修复内容：

- `call_doubao_api` 增加 `user_target` 入参，并在主流程中透传
- 新增诉求到模板键映射：`eye_bag` / `nasolabial_fold` / `all`
- Prompt 库改为双路径兜底读取：`data/prompt_library.json` 与 `data/system/prompt_library.json`
- 前缀改为可配置项 `prompt_prefix`，默认不再强制追加
- `size` 参数仅在合法整数宽高时下发

上线状态：

- 已完成本地语法校验与链路自检
- 已重新打包并发布到服务器实例

---

## 8. 豆包 Prompt 前缀策略调整

变更内容：

- 豆包 Prompt 前缀统一改为固定英文：`Keep the face size ratio unchanged. `
- 在最终发送给豆包前自动拼接该前缀
- 避免重复拼接：若 Prompt 已以前缀开头则不重复添加

验证结果：

- 本地模拟发送已确认最终 payload 的 `prompt` 以该前缀开头
- 已完成重新打包与服务器部署
