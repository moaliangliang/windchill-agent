# Windchill 移动端配置指南

## 1. Windchill+ 移动端

Windchill+ 是 PTC 的移动端应用，支持 iOS 和 Android。

### 功能
- 审批任务
- 查看文档
- 搜索零件
- 查看 BOM

## 2. 配置步骤

### 2.1 配置 SSO
```bash
# 配置单点登录
xconfmanager -s wt.sso.enabled=true -t codebase/wt.properties
xconfmanager -s wt.sso.authUrl=https://sso.company.com/auth -t codebase/wt.properties
xconfmanager -p
```

### 2.2 SSL 配置（移动端必须）
```bash
# 生成 SSL 证书（测试用）
keytool -genkey -alias windchill -keyalg RSA -keystore windchill.keystore

# Tomcat 配置 SSL
# 编辑 $WINDCHILL_HOME/codebase/tomcat/conf/server.xml
# 取消注释 <Connector port="8443" ... 并配置 keystoreFile/keystorePass
```

### 2.3 防火墙配置
| 端口 | 用途 | 说明 |
|------|------|------|
| 443/8443 | HTTPS | 移动端必须 |
| 7380 | HTTP | 可选 |
| 22 | SSH | 运维管理 |

## 3. 常见问题

### 移动端无法连接
- 确认 SSL 证书有效
- 确认移动端网络可访问服务器
- 检查防火墙端口

### 审批列表为空
- 确认用户有待办任务
- 检查 OData API 是否正常工作
