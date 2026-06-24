# Windchill REST Services (WRS) 安装说明

## 为什么需要安装 WRS

KnowAgent 需要通过 WRS（Windchill REST Services）提供的标准 REST API 来查询和操作 Windchill 系统中的数据。

## 安装方式

WRS 组件必须通过 **PTC Solution Installer (PSI)** 来安装。安装包（MED-61403-CD-121）本身没有 setup.exe，它是在 PSI 中作为组件添加的。

### 步骤 1：确认已安装 PTC Solution Installer

在 Windchill 服务器上检查：

```bash
# 检查 PSI 是否已安装
ls /opt/ptc/installer/
# 或
which psi
```

如果还没有 PSI，需要先下载安装（从 PTC 官网获取）。

### 步骤 2：将 WRS 安装包放到指定目录

将下载的 `MED-61403-CD-121_12-1-2-0_Windchill-REST-Services` 文件夹放到 PSI 能访问的位置，如：

```bash
# 建议路径
/opt/ptc/installer/packages/MED-61403-CD-121/
```

### 步骤 3：运行 PTC Solution Installer

```bash
# 启动 PSI
cd /opt/ptc/installer
./psi.sh
```

在 PSI 界面中：

| 步骤 | 操作 |
|------|------|
| 1 | 选择 **Install Products** |
| 2 | 点击 **Add** → 选择 WRS 安装包路径 |
| 3 | 勾选 **Windchill REST Services** 组件 |
| 4 | 选择现有的 Windchill 实例 |
| 5 | 确认安装 → 点击 **Install** |

### 步骤 4：重启 Windchill

```bash
windchill stop
windchill start
```

### 步骤 5：验证安装

```
http://plm.pisx.com:7380/Windchill/odata/$metadata
```

正常应返回 XML 数据，而非 404 错误。也可以用命令验证：

```bash
curl -u "wcadmin:wcadmin" \
  "http://plm.pisx.com:7380/Windchill/odata/ProdMgmt/Parts?\$top=3"
```

## 如果安装过程中遇到问题

1. **没有 PTC Solution Installer** → 从 PTC 官网下载并安装 PSI
2. **PSI 提示许可证不足** → 联系 PTC 确认授权包含 WRS
3. **安装后 404** → 检查 Tomcat 日志：`$WINDCHILL_HOME/logs/catalina.out`

---

**安装完成后告诉我，我在 KnowAgent 中配置 API 集成。**
