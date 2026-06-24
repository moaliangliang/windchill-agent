# Windchill BOM 相关问题排查

## 1. BOM 查询失败

### 常见错误

#### "Uses" 导航不返回子件属性
- SPR 15106325
- WTPartUsageLink 子类型上定义的属性不返回
- **解决**: 升级 WRS 到 2.5.1+

#### GetPartsList 返回空
- 检查 DefaultConfigSpecView 首选项
- 设置: 站点 → 首选项 → DefaultConfigSpecView

#### GetPartStructure 空替换件
- SPR 14535333
- `$expand` 时某些组件的替换件为空
- **解决**: 避免在复杂 BOM 结构中使用 $expand

## 2. BOM 变换问题

### PasteAsIs 路径问题
- SPR 14465882
- TargetPath 参数可以是：空字符串 ""、"/" 或 "|"
- 不同的路径值影响粘贴位置

### IBA 值不复制
- SPR 15380532
- NewDownstreamBranch 不复制上游 IBA 值
- **解决**: 手动更新下游分支的 IBA

### 双下游分支结构错误
- SPR 14939788
- GET /Parts 在双下游分支时报错
- **解决**: 简化 BOM 结构或升级 WRS

## 3. BOM 操作

### knowagent 中的 BOM 工具
```bash
# 查询 BOM
windchill_query_bom(part_number="0000000341")

# 添加子件
windchill_add_bom_item(parent_number="0000000341", child_number="0000000349", quantity=1)

# 删除子件
windchill_delete_bom_item(parent_number="0000000341", child_number="0000000348")
```

## 4. OData BOM 相关 Action

| Action | 功能 | 说明 |
|:-------|:------|:------|
| GetPartsList | 获取汇总 BOM | 含合计数量 |
| GetPartStructure | 产品结构树 | 含路径信息 |
| GetBOM | 标准 BOM | 指定导航条件 |
| DetectDiscrepancies | 检测差异 | EBOM→MBOM |
| ResolveDiscrepancies | 解决差异 | 自动修复 |
| PasteAsIs | 按原样粘贴 | 复制结构 |
| NewDownstreamBranch | 新建下游分支 | 创建新分支 |
| SplitAssemble | 拆分装配 | BOM 重构 |
| CreateEquivalenceLinks | 创建等效链接 | 等价零件 |

## 5. BOM 数据完整性

### 检查方法
```sql
-- 检查 BOM 链接完整性
SELECT COUNT(*) FROM wnc12.wtpartusagelink;

-- 检查孤立 BOM 条目
SELECT * FROM wnc12.wtpartusagelink WHERE usea IS NULL;
```

### 常见问题
- BOM 链接断开：检查对应物料是否存在
- 数量异常：检查 quantity 字段
- 循环引用：BOM 中不应出现循环引用
