# TZC 自动查寝签到

台州学院学工系统自动查寝签到脚本。每天 21:30 自动签到，Cookie 过期自动重新登录，签到结果弹窗提醒。

## 工作原理

```
21:30 定时触发
  ↓
读取 cookies.json
  ↓
Cookie 有效？──是──→ 直接签到 → 弹窗（成功/失败）
  ↓ 否
开无头 Edge 浏览器登录 SSO
  ↓
保存新 Cookie
  ↓
签到 → 弹窗（成功/失败）
```

程序不做的事：
- 不把密码发到任何远程服务器
- 不依赖第三方服务
- 全部在你自己的电脑上完成

## 环境要求

- Windows 10/11 台式机（**不休眠、不关机**，否则 21:30 不会执行）
- Python 3.9+
- Edge 浏览器（Windows 自带，无需安装）
- 校园网（签到接口要求内网访问）

## 安装步骤

### 1. 安装 Python 依赖

```bash
pip install selenium requests urllib3
```

可选（能提升反检测能力，但不装也能运行）：

```bash
pip install undetected-chromedriver
```

### 2. 配置账号信息

```bash
copy config.example.py config.py
```

用记事本打开 `config.py`，把示例值改成你的真实信息：

```python
STUDENT_ID = '你的学号'
PASSWORD = '你的密码'
KQWZXX = '浙江省台州市临海市大洋街道霞飞路台州学院'
JDZB = 121.173050
WDZB = 28.883380
```

| 参数 | 说明 | 获取方式 |
|---|---|---|
| `STUDENT_ID` | 学号 | 学生证 |
| `PASSWORD` | 学工系统密码 | 你知道的 |
| `KQWZXX` | 签到地址描述 | 随便写，合理就行 |
| `JDZB` | 经度 | 手机地图上长按你的宿舍位置 |
| `WDZB` | 纬度 | 同上 |

> `config.py` 不会被 git 提交（已加入 .gitignore），密码只有你自己能看到。

### 3. 手动测试

双击 `run.bat`，或在终端执行：

```bash
python login.py
```

**第一次运行：** 会在后台打开无头 Edge 浏览器（看不见窗口），自动填入账号密码登录 SSO，保存 Cookie。

**后续运行：** 直接复用 Cookie 签到，不开浏览器，几秒完成。

如果输出 `当前时间不在考勤时段内`，说明脚本已成功连接到学工系统，只是现在不是签到时间。等到 21:30 就能签上。

## 部署定时任务

右键 `setup_task.bat` → **以管理员身份运行**。

会在 Windows 任务计划程序中创建 `TZC_auto_checkin` 任务，每天 21:30 自动执行。

查看任务：`Win + R` → 输入 `taskschd.msc` → 任务计划程序库。

## 移除定时任务

右键 `remove_task.bat` → 以管理员身份运行。

## 日志与排查

运行记录写入 `checkin.log`，每次签到都会记录时间戳和结果。

### 常见问题

| 现象 | 原因 | 解决 |
|---|---|---|
| `未找到 username 输入框` | SSO 登录页改了结构 | 联系维护者 |
| `Cookie 无效` | Cookie 过期，但会自动重新登录 | 不用管 |
| `当前时间不在考勤时段内` | 正常，不在签到时间段 | 到 21:30 就能签 |
| 21:30 没有弹窗 | 电脑休眠/关机了 | 检查电源设置，关闭自动休眠 |
| 弹窗显示签到失败 | 网络问题或不在校园网 | 检查网络，确认连接了校园网 |

## 文件结构

```
TZC-Login/
  login.py            ← 主脚本
  config.example.py   ← 配置模板（可提交 git）
  config.py           ← 你的真实配置（已 gitignore）
  run.bat             ← 手动运行
  setup_task.bat      ← 注册定时任务（管理员）
  remove_task.bat     ← 移除定时任务（管理员）
  README.md           ← 本文件
  cookies.json        ← 登录缓存（已 gitignore）
  checkin.log         ← 运行日志（已 gitignore）
```

## Cookie 自动刷新

`cookies.json` 过期后，脚本会自动开无头浏览器重新登录，不需要你做任何操作。

触发条件：Cookie 失效（服务器返回错误）或文件不存在。

全程自动闭环。
