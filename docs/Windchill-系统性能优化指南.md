# Windchill 系统性能优化指南

## 1. JVM 调优

### 推荐 JVM 参数
```bash
# 设置 MethodServer JVM 参数
CATALINA_OPTS="-Xms4g -Xmx8g -XX:+UseG1GC -XX:MaxGCPauseMillis=200"

# 在 setenv.bat/sh 中设置
# Windows: %WINDCHILL_HOME%/bin/setenv.bat
# Linux: $WINDCHILL_HOME/bin/setenv.sh
```

### 根据用户数调整
| 用户数 | 堆内存 | GC 算法 |
|--------|--------|---------|
| < 50 | 2-4G | G1GC |
| 50-200 | 4-8G | G1GC |
| > 200 | 8-16G | G1GC + 并行 GC |

## 2. 数据库优化

### 索引维护
```sql
-- 检查碎片率
SELECT TABLE_NAME, ROUND((DELETED_BLOCKS/TOTAL_BLOCKS)*100,2) FRAG_PCT
FROM USER_TABLES WHERE TOTAL_BLOCKS > 0;

-- 重建索引
ALTER INDEX WTUSER.WTPART_INDEX REBUILD ONLINE;
```

### SQL 慢查询排查
```bash
# 查看 Windchill 慢查询日志
grep -i "slow query" $WINDCHILL_HOME/logs/MethodServer-*-log4j.log
```

## 3. 缓存调优

### 首选项设置
```bash
# 增加缓存大小
xconfmanager -s wt.cache.maxSize=20000 -t codebase/wt.properties
xconfmanager -p
```

### 常用缓存首选项
| 首选项 | 默认值 | 推荐值 |
|--------|--------|--------|
| wt.cache.maxSize | 5000 | 20000 |
| wt.pom.search.maxResults | 200 | 500 |
| wt.session.maxActiveSessions | 100 | 500 |

## 4. 定期维护

### 每周执行
```bash
# 清理临时文件
find $WINDCHILL_HOME/temp -mtime +7 -delete

# 归档日志
find $WINDCHILL_HOME/logs -name "*.log.*" -mtime +30 -exec gzip {} \;
```

### 每月执行
```sql
-- 更新统计信息
EXEC DBMS_STATS.GATHER_SCHEMA_STATS('WCADMIN');
```

## 5. 监控指标

关键监控项:
- MethodServer 堆内存使用率（< 80%）
- 活跃会话数（< 200）
- 数据库连接池使用率
- Average Response Time（< 2秒）
