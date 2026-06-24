# Windchill Workgroup Manager 排查指南

## 1. WGM 概述

Workgroup Manager 用于 CAD 工具与 Windchill 的集成。

### 支持的 CAD 工具
- Creo Parametric
- SolidWorks
- AutoCAD
- CATIA V5
- Inventor

## 2. 常见问题

### 2.1 WGM 无法连接到 Windchill

### 现象
WGM 启动时报错: `Cannot connect to server`

### 排查
1. 检查服务器 URL 是否正确
2. 测试网络连通性: `ping server -t`
3. 检查防火墙端口（默认 7380）
4. 确认 WRS 已正确部署

### 2.2 CAD 文件检入失败

### 现象
从 WGM 检入 CAD 文件到 Windchill 失败

### 排查
```bash
# 检查 Worker Agent 状态
windchill status

# 查看 CAD 发布日志
tail -100 $WINDCHILL_HOME/logs/wvs/cad_worker.log
```

### 2.3 WGM 配置建议

| 配置项 | 推荐值 | 说明 |
|--------|--------|------|
| 缓存大小 | 2GB | 避免频繁从服务器加载 |
| 自动检入 | 启用 | 避免本地修改丢失 |
| 同步周期 | 30分钟 | 平衡性能和实时性 |
