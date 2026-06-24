# Windchill ERP 集成排查指南

## 1. ERP 集成概述

Windchill ↔ ERP 集成通过 ESI（Enterprise Systems Integration）组件实现。

### 支持的 ERP 系统
- SAP
- Oracle EBS
- 用友 U8+
- 金蝶 K/3

## 2. 常见问题

### 2.1 ESI 配置检查
```bash
# 检查 ESI 状态
windchill status

# 查看 ESI 日志
tail -200 $WINDCHILL_HOME/logs/esi/esi.log
```

### 2.2 物料同步失败

### 现象
物料从 Windchill 发送到 ERP 失败，或 ERP 物料无法导入

### 排查步骤
1. 检查 ESI 队列中是否有积压:
   ```sql
   SELECT COUNT(*) FROM ESI_QUEUE WHERE STATUS = 'PENDING';
   ```
2. 查看具体失败原因:
   ```bash
   grep -i "error\|fail" $WINDCHILL_HOME/logs/esi/esi.log | tail -50
   ```
3. 重试失败的队列任务:
   ```bash
   windchill com.ptc.windchill.esi.ESIRetryFailedTasks
   ```

## 3. 配置验证

```bash
# 测试 ESI 连接
windchill com.ptc.windchill.esi.ESIConnectionTest -host erp-server -port 8080

# 查看 ESI 配置
cat $WINDCHILL_HOME/codebase/esi.properties | grep -v "^#"
```
