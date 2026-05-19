# 计划：删除传统 CV 检测方式，完全切换为 AI 模型检测

## 概述

将项目从"双检测模式可选"改为"纯 AI 模型检测"，删除所有传统 CV 相关代码和 UI。

## 影响分析

### engine.py — 需要删除的 CV 专用代码

**删除的属性（`__init__` 中）：**
- `self.white_v_low`, `self.white_s_max` — 白色区域检测阈值
- `self.red_min_r`, `self.red_min_delta`, `self.red_max_avg`, `self.red_saturation` — 红色指针检测阈值
- `self.predict_ms` — CV 预判补偿
- `self.delay_degree` — CV 角度延迟补偿
- `self.outer_mask_percent`, `self.center_mask_percent` — 遮罩设置
- `self.qte_stabilize_ms`, `self.qte_stabilize_frames` — QTE 稳定帧数
- `self._measured_speed`, `self._speed_samples`, `self._pointer_angle_samples`, `self._detected_mode_label` — 速度检测状态
- `self._geom_radii`, `self._geom_angles_float`, `self._geom_angles_int`, `self._geom_xs`, `self._geom_ys`, `self._roi_mask` — 几何预计算
- `self.detection_method` — 不再需要模式选择

**删除的方法：**
- `_prepare_geometry()` — 几何预计算
- `_rebuild_roi_mask()` — ROI 遮罩重建
- `set_mask_settings()` — 遮罩设置
- `_classify_speed()` — 速度分类标签
- `_update_speed_measurement()` — 速度测量
- `_apply_roi_mask()` — ROI 遮罩应用
- `detect()` — CV 检测主方法
- `_angle_from_center()`, `_angle_distance()`, `_smooth_circular()`, `_angle_segments()` — 角度工具
- `_estimate_ring_radius()` — 圆环半径估计
- `find_pointer()`, `_find_pointer_red_pixel()`, `_smooth_pointer_angle()`, `_find_pointer_angle()`, `_fit_pointer_centerline_angle()` — 指针检测
- `_find_judgement_arcs()`, `_white_ring_has_all_sectors()`, `_check_arc_hit()` — 判定弧检测
- `run_loop()` — CV 主循环
- `_draw_preview()` — CV 预览绘制
- `capture()` — CV 截屏（MSS）
- `capture_obs()` — CV 截屏（OBS）
- `_enhance_obs_frame()` — OBS 图像增强
- `test_camera()`, `scan_cameras()` — 摄像头测试/扫描
- `detected_mode_label`, `measured_speed` 属性

**保留的方法：**
- `set_region()` — AI 也需要区域设置
- `trigger()` — 通用触发方法
- `_load_ai_model()`, `_unload_ai_model()` — AI 模型管理
- `_capture_ai()`, `_capture_ai_obs()` — AI 截屏
- `run_loop_ai()` — AI 主循环（改名为 `run_loop`）
- `_draw_preview_ai()` — AI 预览（改名为 `_draw_preview`）
- `start()`, `stop()`, `toggle_pause()` — 引擎控制
- `get_stats()` — 统计信息
- `latest_preview`, `latency_log` 属性

**重命名：**
- `run_loop_ai` → `run_loop`
- `_draw_preview_ai` → `_draw_preview`
- `_capture_ai` → `_capture_frame`
- `_capture_ai_obs` → `_capture_frame_obs`
- 删除 `detection_method` 属性，`start()` 不再需要分支判断

### main.py — 需要删除的 CV 专用 UI

**删除的 UI 区域：**
- `_build_detection_section` 中的检测方式选择（RadioButton CV/AI）和状态标签 → 改为纯 AI 状态显示
- `cv_param_frame` — CV 专用参数（预判补偿/白色亮度/色差容忍）
- `cv_feature_frame` — CV 专用高级设置（红色检测参数/延迟补偿/遮罩设置）
- `_build_mask_slider()` — 遮罩滑块构建方法
- `_build_color_debug_section()` — 颜色调试区域
- `_update_detection_method()` — 模式切换方法
- `_update_delay()` — 延迟补偿更新
- `_update_outer_mask()`, `_update_center_mask()` — 遮罩更新

**删除的变量：**
- `detection_method_var` — 模式选择
- `cv_param_frame`, `cv_feature_frame` — CV 参数容器
- `delay_degree_var`, `delay_display` — 延迟补偿
- `outer_mask_var`, `center_mask_var` — 遮罩变量
- `red_param_vars`, `red_param_displays` — 红色参数

**简化的 UI 区域：**
- `_build_param_section` — 只保留共享参数（检测频率、触发冷却）
- `_build_feature_section` — 只保留 AI 配置 + 保存按钮
- `_build_detection_section` — 改为 AI 模型配置（不再需要模式选择）
- 统计面板 — 删除 `auto_mode`, `speed` 等 CV 统计项

**保留的 UI 区域：**
- `_build_region_section` — 区域选择
- `_build_capture_section` — 截屏方式（MSS/OBS）
- `_build_input_section` — 输入方式
- `_build_control_section` — 启动/停止
- `_build_stats_section` — 统计（简化）
- `_build_log_section` — 日志
- `_build_preview_section` — 预览
- `_build_status_section` — 状态

### 配置文件 — 简化

- `_save_config` / `_load_config` — 删除 CV 专用参数（red_params, mask, delay_degree, white_v_low 等），删除 detection.method 字段

## 实施步骤

### Step 1: 重构 engine.py
1. 删除所有 CV 专用属性
2. 删除所有 CV 专用方法
3. 将 `run_loop_ai` 重命名为 `run_loop`
4. 将 `_draw_preview_ai` 重命名为 `_draw_preview`
5. 将 `_capture_ai` / `_capture_ai_obs` 重命名为 `_capture_frame` / `_capture_frame_obs`
6. 简化 `start()` 方法（不再需要分支判断）
7. 简化 `get_stats()` 方法（删除 CV 统计项）
8. 简化 `__init__`（删除 `detection_method` 属性）
9. 更新版本号为 v3.0

### Step 2: 重构 main.py
1. 删除 `_build_detection_section` 中的模式选择 UI，改为纯 AI 配置面板
2. 删除 `cv_param_frame` 和 `cv_feature_frame`
3. 删除 `_build_mask_slider` 方法
4. 删除 `_build_color_debug_section` 方法
5. 简化 `_build_param_section`（只保留检测频率和触发冷却）
6. 简化 `_build_feature_section`（只保留 AI 配置 + 保存按钮）
7. 简化 `_build_stats_section`（删除 CV 统计项）
8. 删除 `_update_detection_method`、`_update_delay`、`_update_outer_mask`、`_update_center_mask` 等方法
9. 简化 `_start` 方法（不再需要模式判断）
10. 简化 `_save_config` / `_load_config`
11. 更新版本号为 v3.0

### Step 3: 验证
1. 语法检查
2. AI 检测器模块导入测试
3. 预处理管道测试

### Step 4: 提交并更新 PR
1. 提交变更
2. 推送到远程分支
3. PR 自动更新

## 风险评估

- **低风险**：删除的 CV 代码与 AI 代码完全独立，无交叉依赖
- **注意**：`capture()` 和 `capture_obs()` 是 CV 专用的，AI 有自己的 `_capture_ai()` 和 `_capture_ai_obs()`，不冲突
- **注意**：`set_region()` 和 `_prepare_geometry()` 中，`_prepare_geometry` 是 CV 专用的（几何预计算），但 `set_region` 仍需保留（AI 也用 region）
