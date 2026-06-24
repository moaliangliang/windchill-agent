# Windchill 系统安装指南

## 1. 环境要求

### 硬件要求
| 规模 | CPU | 内存 | 磁盘 |
|------|-----|------|------|
| 小型（50人以下） | 8核 | 16GB | 200GB |
| 中型（50-200人） | 16核 | 32GB | 500GB |
| 大型（200人以上） | 32核 | 64GB+ | 1TB+ |

### 软件要求
- 操作系统: Windows Server / Linux（RHEL 8+）
- Java: OpenJDK 11 / Oracle JDK 11
- 数据库: Oracle 19c / SQL Server 2019
- Web 服务器: Tomcat 9

## 2. 安装步骤

### 2.1 安装 PTC Solution Installer (PSI)
```bash
# 下载 PSI（需要 PTC 账号）
# 运行安装向导，选择 Windchill 组件
./setup.sh  # Linux
setup.exe   # Windows
```

### 2.2 选择安装组件
1. Windchill PDMLink / ProjectLink 等业务模块
2. WRS (Windchill REST Services)
3. WVS (Windchill Visualization Services，如需 CAD 发布)
4. ESI (Enterprise Systems Integration，如需 ERP 集成)

### 2.3 配置数据库
```bash
# Oracle 需要先创建表空间
CREATE TABLESPACE WINDCHILL_DATA
  DATAFILE '/u01/oradata/WINDCHILL_DATA.dbf' SIZE 10G AUTOEXTEND ON;

CREATE USER WCADMIN IDENTIFIED BY wcadmin
  DEFAULT TABLESPACE WINDCHILL_DATA;

GRANT CONNECT, RESOURCE, DBA TO WCADMIN;
```

## 3. 安装后验证

### 3.1 启动服务
```bash
cd $WINDCHILL_HOME/bin
./windchill start
```

### 3.2 验证 URL
- 主页: http://server:port/Windchill
- OData: http://server:port/Windchill/servlet/odata/v3
- 管理台: http://server:port/Windchill/admin

## 4. 常见问题

### PSI 安装失败
- **原因**: Java 版本不匹配
- **解决**: 使用 PSI 捆绑的 Java，或设置 JAVA_HOME

### 数据库连接失败
- **原因**: 数据库驱动或连接串错误
- **解决**: 
  ```bash
  # 检查 db.properties
  cat $WINDCHILL_HOME/codebase/db.properties | grep -i oracle
  ```
