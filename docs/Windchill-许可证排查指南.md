# Windchill 许可证排查指南

## 1. 许可证管理

### 检查许可证状态
```bash
# Windchill shell 中执行
windchill com.ptc.windchill.mpadmin.LicenseManager -status

# 查看许可证文件位置
cat $WINDCHILL_HOME/codebase/license.dat | head -20
```

## 2. 常见问题

### 2.1 许可证过期

### 现象
登录 Windchill 时提示: `License has expired`

### 解决
1. 从 PTC 官网获取新许可证文件
2. 替换 `$WINDCHILL_HOME/codebase/license.dat`
3. 重启 Windchill:
   ```bash
   windchill stop
   windchill start
   ```

### 2.2 并发用户数超限

### 现象
部分用户无法登录: `No more licenses available`

### 解决
```bash
# 1. 查看当前活跃会话
windchill com.ptc.windchill.mpadmin.SessionMonitor -active

# 2. 强制释放空闲会话
windchill com.ptc.windchill.mpadmin.SessionMonitor -releaseIdle -timeout 30
```

## 3. 浮动许可证配置

### 配置 FlexLM
```bash
# 设置许可证服务器
xconfmanager -s wt.license.server.host=license-server.company.com -t codebase/wt.properties
xconfmanager -s wt.license.server.port=27000 -t codebase/wt.properties
xconfmanager -p
```
