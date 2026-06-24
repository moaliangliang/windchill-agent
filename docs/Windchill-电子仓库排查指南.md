# Windchill 电子仓库排查指南

## 1. 电子仓库概念

Windchill 电子仓库（Vault）用于存储文档和 CAD 文件的物理文件。

### 类型
| 类型 | 说明 |
|------|------|
| **主 Vault** | 默认存储位置，所有文件首先存入 |
| **副本 Vault** | 主 Vault 的复制，用于灾备 |
| **站点 Vault** | 副本站点的本地存储 |

## 2. 常见问题

### 2.1 文件上传失败

### 现象
上传文档/图纸时提示：`Vault is full` 或 `Cannot write to vault`

### 排查步骤
```bash
# 1. 查看 vault 配置
xconfmanager -d wt.fv.basedir

# 2. 检查磁盘空间
df -h $WINDCHILL_HOME/vaults

# 3. 检查 vault 目录权限
ls -la $WINDCHILL_HOME/vaults
```

### 解决
```bash
# 添加新的存储卷
xconfmanager -s wt.fv.additionalVaultRoots=D:/ptc/vaults2 -t codebase/wt.properties
xconfmanager -p
```

### 2.2 文件下载失败

### 现象
下载文档附件时提示：`Content Not Found`

### 排查
```bash
# 1. 查看 vault 中文件是否存在
ls $WINDCHILL_HOME/vaults/<vault_id>/<content_id>

# 2. 检查文件引用是否完整
SELECT * FROM WTVault WHERE ID = '<vault_id>';
```

### 解决
- 文件物理存在但引用丢失: `windchill com.ptc.windchill.mpadmin.VaultMaintenance -repair`
- 文件物理丢失: 从备份恢复 vault 目录

### 2.3 Vault 复制失败

### 现象
副本站点的 vault 复制不同步

### 检查复制状态
```bash
# 主站点推送 vault 列表
windchill com.ptc.windchill.mpadmin.VaultReplicationStatus

# 手动触发复制
windchill com.ptc.windchill.mpadmin.VaultSync.sh
```

## 3. 维护操作

### 定期清理
```bash
# 清理孤立文件
windchill com.ptc.windchill.mpadmin.VaultMaintenance -cleanup

# 检查 vault 完整性
windchill com.ptc.windchill.mpadmin.VaultIntegrityCheck -all
```

### Vault 迁移
```bash
# 1. 停止服务
# 2. 复制 vault 目录到新位置
rsync -avz $WINDCHILL_HOME/vaults/ /new/location/vaults/

# 3. 更新 vault 路径
xconfmanager -s wt.fv.basedir=/new/location/vaults -t codebase/wt.properties
xconfmanager -p
# 4. 重启服务
./windchill stop && ./windchill start
```
