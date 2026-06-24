# Windchill 可视化失败处理指南

## 1. 可视化服务无法启动

### 现象
- **Visualization Service** 无法启动
- 日志报错: `Worker Agent not running`

### 原因
Worker Agent（工作器代理）未正确配置或未启动

### 解决步骤
```bash
# 1. 检查 Worker Agent 状态
windchill status

# 2. 如果未运行，查看 WVS 日志
tail -100 $WINDCHILL_HOME/logs/wvs/wvs.log

# 3. 重启 Worker Agent
windchill stop
windchill start
```

## 2. CAD 发布失败

### 现象
将 Creo/SolidWorks 图纸发布到 Windchill 时失败

### 常见原因及解决
| 原因 | 解决 |
|------|------|
| Worker Agent 未匹配 | 检查 agent.ini 中 worker 类型与 CAD 版本匹配 |
| 路径包含中文 | 确保 CAD 文件路径不含中文或特殊字符 |
| 权限不足 | 确认 Worker Agent 运行账户有 CAD 安装目录的读取权限 |

### 查看 Worker 日志
```bash
# MethodServer 日志
tail -200 $WINDCHILL_HOME/logs/MethodServer-*-log4j.log

# WVS 日志（Worker 相关）
ls -lt $WINDCHILL_HOME/logs/wvs/ | head -5
```

## 3. WVS 页面无法访问

### 现象
http://server:port/Windchill/wvs/admincad.jsp 打不开

### 排查步骤
1. 检查 Tomcat 是否正常运行
2. 检查 WRS 是否已部署
3. 查看 Tomcat 日志:
   ```bash
   tail -100 $WINDCHILL_HOME/logs/catalina.out | grep -i wvs
   ```

## 4. 发布队列堆积

### 现象
CAD 文档在"发布队列"中堆积，不处理

### 解决
1. 重启 Worker Agent:
   ```bash
   windchill stop
   windchill start
   ```
2. 清空队列（需要 DBA 权限）:
   ```sql
   TRUNCATE TABLE WVS_SCHEDULE;
   ```
3. 确认 Worker 数量不超过许可证限制

## 5. 预览图不显示

### 现象
文档详情页的缩略图/预览图显示为空白

### 解决
1. 检查 WVS 是否启用缩略图生成
2. 确认文件格式是否被 WVS 支持
3. 手动触发重新生成: 文档右键 → 更新缩略图
