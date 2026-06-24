# Windchill 升级迁移指南

## 1. 升级前准备

### 1.1 环境检查
```bash
# 确认当前版本
windchill version

# 检查磁盘空间
df -h $WINDCHILL_HOME

# 备份数据库（必须先做！）
expdp wcadmin/wcadmin DIRECTORY=DUMP_DIR DUMPFILE=preupgrade.dmp FULL=Y
```

### 1.2 检查兼容性
- 确认源版本 → 目标版本的升级路径
- 确认所有定制化的兼容性
- 确认第三方集成的兼容性

## 2. 升级步骤

### 2.1 停止服务
```bash
cd $WINDCHILL_HOME/bin
./windchill stop
```

### 2.2 运行升级脚本
```bash
# 进入 PSI 目录
cd /ptc/PSI

# 运行升级向导
./setup.sh
# 选择: 升级现有 Windchill 安装
# 选择: 目标版本安装包
```

### 2.3 执行数据库升级
```bash
# Windchill shell 中执行
windchill com.ptc.windchill.upgrade.UpgradeManager -upgrade
```

### 2.4 启动验证
```bash
cd $WINDCHILL_HOME/bin
./windchill start

# 检查启动日志
tail -100 $WINDCHILL_HOME/logs/MethodServer-*-log4j.log | grep -i "error\|exception"
```

## 3. 迁移到新服务器

### 3.1 数据库迁移
```bash
# 源库导出
expdp wcadmin/wcadmin DIRECTORY=DUMP_DIR DUMPFILE=full.dmp FULL=Y

# 目标库导入
impdp wcadmin/wcadmin DIRECTORY=DUMP_DIR DUMPFILE=full.dmp FULL=Y
```

### 3.2 文件迁移
```bash
# 复制 Windchill 目录
rsync -avz $WINDCHILL_HOME/ user@new-server:/opt/Windchill/

# 复制 vault 目录
rsync -avz $WINDCHILL_HOME/vaults/ user@new-server:/opt/Windchill/vaults/
```

## 4. 回滚方案

```bash
# 如果升级失败：
# 1. 恢复数据库
impdp wcadmin/wcadmin DIRECTORY=DUMP_DIR DUMPFILE=preupgrade.dmp FULL=Y

# 2. 恢复原版本文件
# 从备份恢复 $WINDCHILL_HOME

# 3. 启动原版本
cd $WINDCHILL_HOME/bin
./windchill start
```

## 5. 常见问题

### 升级后 OData 不可用
- **解决**: 重新部署 WRS 或升级 WRS 版本

### MethodServer 启动报类找不到
- **原因**: 定制化 jar 未正确迁移
- **解决**: 检查 codebase/WEB-INF/lib 下的定制 jar 是否完整
