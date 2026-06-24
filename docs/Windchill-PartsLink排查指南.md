# Windchill PartsLink 排查指南

## 1. PartsLink 功能

PartsLink 用于管理标准件库和分类结构。

### 常见用途
- 标准件库管理（螺栓、螺母、垫圈等）
- 分类属性管理
- 参数化搜索

## 2. 问题排查

### 2.1 分类树不显示

### 原因
分类 XML 文件未正确加载或权限不足

### 解决
```bash
# 1. 重新生成分类 XML
windchill com.ptc.windchill.classification.ClassificationAdmin -generate

# 2. 清除分类缓存
windchill com.ptc.windchill.classification.ClassificationAdmin -clearCache

# 3. 重启 MethodServer
windchill stop
windchill start
```

### 2.2 分类属性不显示

### 原因
分类节点属性配置错误

### 解决
1. 检查分类定义 XML 文件格式
2. 确认属性名称与数据库字段匹配
3. 重新生成分类索引

### 2.3 标准件搜索慢

### 解决
```sql
-- 重建分类表索引
ALTER INDEX CLF_NODE_ATTR_IDX REBUILD ONLINE;
-- 更新统计信息
EXEC DBMS_STATS.GATHER_TABLE_STATS('WCADMIN', 'CLF_NODE_ATTR');
```
