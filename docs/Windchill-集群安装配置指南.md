# Windchill 集群安装配置指南

## 1. 集群架构

```
负载均衡器 (Load Balancer) — Session Affinity
       │
       ├── 主缓存节点 (Main Cache)
       │   ├── MethodServer + Background MS
       │   ├── 队列处理
       │   └── 数据库连接
       │
       ├── 缓存客户端 (Cache Client)
       │   └── MethodServer（无 Background）
       │
       └── 共享 Vault 存储 (NAS/SAN)
```

### 两种集群类型
| 类型 | 说明 |
|:-----|:------|
| **相同节点集群** | 所有节点可协商为主缓存 |
| **专用主节点集群** | 指定特定节点为主缓存（wt.cache.main.hostname）|

## 2. 核心配置参数

```properties
# 负载均衡器地址，所有节点使用同一地址
wt.rmi.server.hostname=集群统一主机名（负载均衡器地址）

# 主缓存节点配置
wt.cache.main.hostname=主节点FQDN
wt.cache.main.secondaryHosts=从节点1FQDN,从节点2FQDN

# 集群缓存类型（none/master/slave/slave_unified）
wt.cache.cluster.type=master

# 共享保险库路径
wt.fv.basedir=共享保险库路径（NAS/SAN挂载点）
```

## 3. 集群配置步骤

### 3.1 前期准备
1. 所有节点时间同步（NTP）
2. 共享存储（NAS/SAN）挂载到所有节点相同的路径
3. 数据库所有节点均可访问
4. 负载均衡器已配置 Session Affinity

### 3.2 配置集群属性
```bash
# 在每个节点上执行

# 设置统一主机名（负载均衡器地址）
xconfmanager -s wt.rmi.server.hostname=集群统一地址 -t codebase/wt.properties

# 主缓存节点
xconfmanager -s wt.cache.main.hostname=主节点FQDN -t codebase/wt.properties

# 从节点列表
xconfmanager -s wt.cache.main.secondaryHosts=从节点1FQDN,从节点2FQDN -t codebase/wt.properties

# 设置缓存类型
xconfmanager -s wt.cache.cluster.type=master -t codebase/wt.properties

# 应用配置
xconfmanager -p
```

### 3.3 主节点完整配置
```bash
xconfmanager -s wt.cache.cluster.type=master -t codebase/wt.properties
xconfmanager -s wt.cache.main.hostname=主节点FQDN -t codebase/wt.properties
xconfmanager -s wt.cache.cluster.multicastEnabled=false -t codebase/wt.properties
xconfmanager -p
```

### 3.4 从节点配置
```bash
xconfmanager -s wt.cache.cluster.type=slave -t codebase/wt.properties
xconfmanager -s wt.cache.main.hostname=主节点FQDN -t codebase/wt.properties
xconfmanager -p
```

### 3.5 验证集群
```bash
# 启动所有节点后，查看缓存状态
tail -f $WINDCHILL_HOME/logs/MethodServer-*-log4j.log | grep -i "cache\|cluster"
```

## 4. 集群 Rehost

### 主节点 Rehost 配置
```bash
# 创建主节点 rehost 配置文件
echo 'cluster.master.gateway=主节点FQDN
cluster.slave.hostnames=从节点1FQDN,从节点2FQDN
cluster.slave.count=2' > conf/rehost_clustermaster.properties

# 执行 rehost
rehost.bat conf/rehost_clustermaster.properties
```

### 从节点 Rehost 配置
```bash
echo 'cluster.master.gateway=主节点FQDN' > conf/rehost_clusterslave.properties
rehost.bat conf/rehost_clusterslave.properties
```

## 5. 注意事项

### 缓存目录配置
```bash
# 如果使用专用主节点，主节点配置:
xconfmanager -s wt.cache.cluster.type=master -t codebase/wt.properties

# 缓存客户端配置:
xconfmanager -s wt.cache.cluster.type=slave -t codebase/wt.properties
```

### Session 复制
确保负载均衡器启用了 **Session Affinity（粘性会话）**，否则需要额外配置 Session 复制。

### 常见问题
| 问题 | 原因 | 解决 |
|------|------|------|
| 节点间缓存不同步 | 端口未开放 | 检查防火墙: 4001-4005/TCP, 45566/TCP |
| 启动报 ClassNotFoundException | 环境不一致 | 确保所有节点 JDK/Windchill 版本一致 |
| 事务超时 | 网络延迟高 | 增加事务超时: `wt.txn.timeout=300` |
