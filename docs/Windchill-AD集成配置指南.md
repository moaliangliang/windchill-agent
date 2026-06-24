# Windchill AD 集成配置指南

## 1. 配置 LDAP 认证

### 1.1 设置 LDAP 属性
```bash
xconfmanager -s wt.servers.LDAPDirectory.serverHost=ad.company.com -t codebase/wt.properties
xconfmanager -s wt.servers.LDAPDirectory.serverPort=389 -t codebase/wt.properties
xconfmanager -s wt.servers.LDAPDirectory.principal=CN=admin,CN=Users,DC=company,DC=com -t codebase/wt.properties
xconfmanager -s wt.servers.LDAPDirectory.credentials=password -t codebase/wt.properties
xconfmanager -s wt.servers.LDAPDirectory.baseDn=DC=company,DC=com -t codebase/wt.properties
xconfmanager -s wt.servers.LDAPDirectory.contextFactory=com.sun.jndi.ldap.LdapCtxFactory
xconfmanager -p
```

### 1.2 配置用户 DN 模式
```bash
xconfmanager -s wt.servers.LDAPDirectory.userDnPattern=CN=%s,CN=Users,DC=company,DC=com -t codebase/wt.properties
xconfmanager -p
```

## 2. AD 用户同步

### 手动同步
```bash
# Windchill shell 中执行
windchill com.ptc.windchill.mpadmin.LDAPSync.sh -d LDAP_DN
```

### 配置自动同步（cron）
```bash
# Linux: 每天凌晨 2 点同步
0 2 * * * $WINDCHILL_HOME/bin/windchill com.ptc.windchill.mpadmin.LDAPSync.sh
```

## 3. AD 组映射

### 设置组映射文件
创建 `$WINDCHILL_HOME/codebase/WT_LDAP_GROUP_MAPPING.properties`:
```properties
# AD组 → Windchill组
CN=WindchillAdmins,CN=Users,DC=company,DC=com = Administrators
CN=WindchillUsers,CN=Users,DC=company,DC=com = Windchill Users
CN=Designers,CN=Users,DC=company,DC=com = CAD Users
```

## 4. 验证配置

### 4.1 测试 LDAP 连接
```bash
windchill com.ptc.windchill.mpadmin.LDAPSync.sh -t
```

### 4.2 检查同步日志
```bash
grep -i "ldap\|ad sync" $WINDCHILL_HOME/logs/MethodServer-*-log4j.log | tail -50
```

## 5. 常见问题

### AD 用户无法登录
- **原因**: DN 模式配置错误
- **解决**: 确认 `userDnPattern` 与 AD 结构匹配

### 同步后用户信息不完整
- **原因**: LDAP 属性映射未配置
- **解决**: 检查 LDAP 属性映射首选项

### SSL 连接失败
- **原因**: AD 证书未导入信任库
- **解决**:
  ```bash
  keytool -import -trustcacerts -alias ad-server -file ad-cert.cer -keystore $JAVA_HOME/lib/security/cacerts
  ```
