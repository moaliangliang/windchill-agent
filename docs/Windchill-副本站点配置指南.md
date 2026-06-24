# Windchill 副本站点配置指南

## 1. 副本站点架构

```
主站点 (Main Site)
  ├── MethodServer + Background MS
  ├── Oracle 数据库 (主库)
  └── 主 Vault 存储
          ↓ 异步复制
副本站点 (Replica Site)
  ├── MethodServer（只读）
  ├── Oracle DataGuard (备库)
  └── 复制 Vault 存储
```

## 2. 数据库配置

### 2.1 主库配置
```sql
-- 开启归档模式
SHUTDOWN IMMEDIATE;
STARTUP MOUNT;
ALTER DATABASE ARCHIVELOG;
ALTER DATABASE OPEN;

-- 启用 Force Logging
ALTER DATABASE FORCE LOGGING;

-- 创建 Standby Redo Log
ALTER DATABASE ADD STANDBY LOGFILE GROUP 4 '/u01/oradata/std_redo01.log' SIZE 500M;
```

### 2.2 配置 DataGuard
```bash
# 主库: 生成备库控制文件
ALTER DATABASE CREATE STANDBY CONTROLFILE AS '/tmp/standby.ctl';

# 备库: 配置 listener.ora
echo 'SID_LIST_LISTENER =
  (SID_LIST =
    (SID_DESC = (GLOBAL_DBNAME = orcl) (ORACLE_HOME = /u01/app/oracle) (SID_DESC = orcl))
  )' > $ORACLE_HOME/network/admin/listener.ora
```

## 3. Windchill 副本站点配置

### 3.1 配置站点属性
```bash
xconfmanager -s wt.site.siteType=replica -t codebase/wt.properties
xconfmanager -s wt.site.masterUrl=http://master-server:7380/Windchill -t codebase/wt.properties
xconfmanager -s wt.site.replicaUrl=http://replica-server:7380/Windchill -t codebase/wt.properties
xconfmanager -p
```

### 3.2 配置 vault 复制
```bash
# 主站点推送 vault 到副本站点
xconfmanager -s wt.fv.replicaVaultRoot=\\\\\\\\replica-server\\vaults -t codebase/wt.properties
xconfmanager -s wt.fv.replicaVaultMountPoint=/mnt/replica/vaults -t codebase/wt.properties
xconfmanager -p
```

## 4. 验证副本站点

```bash
# 启动副本站点
cd $WINDCHILL_HOME/bin
./windchill start

# 检查站点状态
windchill com.ptc.windchill.mpadmin.SiteUtils.sh -status

# 检查 vault 复制
windchill com.ptc.windchill.mpadmin.VaultSyncStatus
```

## 5. 常见问题

### 副本站点数据不同步
- 检查 DataGuard 同步状态: `SELECT PROCESS, STATUS FROM V$MANAGED_STANDBY;`
- 检查 vault 复制: `windchill com.ptc.windchill.mpadmin.VaultReplicationStatus`

### 副本站点无法启动
- 确认数据库连接的 SID/服务名正确
- 检查站点首选项是否正确配置
