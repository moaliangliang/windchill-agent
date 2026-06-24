# Windchill Solr 索引排查指南

## 1. Solr 索引概述

Windchill 使用 Solr 实现全文搜索功能。

### 查看 Solr 状态
```bash
# 检查 Solr 进程
ps -ef | grep solr

# 查看 Solr 管理页面
# http://server:8085/solr/#/
```

## 2. 常见问题

### 2.1 搜索无结果

### 现象
在 Windchill 中搜索零件/文档，返回空

### 排查步骤
```bash
# 1. 检查 Solr 是否运行
curl -s http://localhost:8085/solr/admin/ping | head -5

# 2. 检查索引状态
curl -s http://localhost:8085/solr/wblib/admin/ping

# 3. 查看 Solr 日志
tail -200 $WINDCHILL_HOME/solr/server/logs/solr.log | grep -i error
```

### 2.2 索引不同步

### 解决
```bash
# 手动触发全量索引
windchill com.ptc.windchill.search.SearchAdmin -rebuild

# 或者增量索引
windchill com.ptc.windchill.search.SearchAdmin -incrementalIndex
```

### 2.3 Solr 连接失败

### 现象
MethodServer 日志报: `Solr server refused connection`

### 解决
```bash
# 1. 检查端口占用
netstat -an | grep 8085

# 2. 重启 Solr
cd $WINDCHILL_HOME/solr/server
java -jar start.jar &

# 3. 检查 Solr 配置
cat $WINDCHILL_HOME/codebase/wt.properties | grep solr
```
