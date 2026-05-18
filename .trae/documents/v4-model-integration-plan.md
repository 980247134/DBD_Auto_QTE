# V4 模型集成与项目优化计划

## 背景
用户提供了 Manuteaa dbd_autoSkillCheck V4.2.1 的压缩包（`dbd-asc-v4.2.1-standard.zip`，409.75MB），但由于 SendUp 下载链接有 Cloudflare R2 签名保护，无法通过 curl 直接下载。

**需要用户操作**：请将下载好的 `dbd-asc-v4.2.1-standard.zip` 文件直接复制/拖拽到 `/workspace` 目录下。

## 前置条件
- [ ] 用户将 `dbd-asc-v4.2.1-standard.zip` 放到 `/workspace` 目录

## 实施步骤

### 第一步：解压并分析 V4 代码
1. 解压 `dbd-asc-v4.2.1-standard.zip` 到 `/workspace/dbd_v4/`
2. 分析 V4 目录结构，对比 V3（GitHub main 分支）找出差异
3. 重点关注：
   - 新的 AI 模型文件（ONNX / 量化模型）
   - `AI_model.py` 的变化（新分类、新预处理逻辑）
   - `app.py` 的变化（新 UI、新参数）
   - 新增的工具/模块（SkillCheckFinder 等）
   - 模型量化相关代码

### 第二步：提取可学习的优秀内容
基于 V4 README 已知信息，预期新特性：
- **INT8 量化模型**（1.5MB vs 6MB）：CPU 推理速度翻倍
- **新 AI 模型**：支持 Decisive Strike / Oppression / Brand New Part 等新分类
- **SkillCheckFinder**：模板匹配定位 + AI 识别两阶段流水线
- **新 UI 设计**：更简洁的 GPU 启用方式
- **自定义 AI 设置**：针对老旧硬件的优化选项

### 第三步：集成 V4 模型到项目
1. 将 V4 的 ONNX 模型文件复制到 `/workspace/models/`
2. 更新 `ai_detector.py`：
   - 支持 V4 新的分类体系（可能从 11 类扩展到更多）
   - 支持 INT8 量化模型自动检测
   - 适配新的预处理参数（如有变化）
3. 更新 `engine.py`：
   - 适配新模型的推理接口
4. 更新 `main.py`：
   - AI 配置面板适配新模型选项
   - 模型版本显示

### 第四步：验证可行性
1. 语法检查：`python -c "import ast; ast.parse(...)"`
2. 模块导入测试：验证 `ai_detector.py` 能正确加载 V4 模型
3. 推理测试：用随机帧测试 V4 模型的 predict 方法
4. 集成测试：验证传统 CV / AI 模式切换正常

### 第五步：创建 PR
1. 初始化 git 仓库（如未初始化）
2. 创建特性分支 `feature/v4-model-integration`
3. 提交所有改动
4. 创建 PR 到主分支

## 关键风险
- V4 模型分类数量可能变化，需要适配 `PRED_DICT`
- V4 预处理参数（MEAN/STD）可能变化
- 量化模型需要 `onnxruntime` 的 INT8 执行提供者支持
