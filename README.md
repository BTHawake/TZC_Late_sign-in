# TZC 自动查寝签到

台州学院学工系统自动查寝签到脚本。每天 21:30 自动签到，Cookie 过期自动重新登录，签到结果弹窗提醒。

## 工作原理

```
21:30 定时触发
  ↓
读取 cookies.json
  ↓
Cookie 还有效？──是──→ 直接签到 → 弹窗结果
  ↓ 否
开无头浏览器登录 SSO
  ↓
保存新 Cookie
  ↓
签到 → 弹窗结果
```

## 环境要求

- Windows 系统（台式机，不关机/不休眠）
- Python 3.9+
- Edge 浏览器（Windows 自带）

## 安装

```bash
# 1. 安装依赖
pip install selenium requests urllib3

# 2. 把整个项目文件夹放到任意位置（路径不要删，后续定时任务会记住这个位置）
```

## 手动测试

双击 `run.bat`，或：

```bash
python login.py
```

首次运行会弹出控制台窗口，无头浏览器在后台登录（看不到窗口）。登录成功后下次直接复用 Cookie，不再开浏览器。

如果提示 `当前时间不在考勤时段内`，说明脚本能正常连接到学工系统，等到 21:30 就能签上。

## 配置

所有配置通过环境变量传入，不设默认值就报错——防止敏感信息泄露。

| 环境变量 | 说明 | 示例 |
|---|---|---|
| `STUDENT_ID` | 学号 | `2462120045` |
| `PASSWORD` | 密码 | `your_password` |
| `KQWZXX` | 签到地址描述 | `浙江省台州市临海市大洋街道霞飞路台州学院` |
| `JDZB` | 经度 | `121.173050` |
| `WDZB` | 纬度 | `28.883380` |

**本地使用建议设置系统环境变量，或者直接在 `login.py` 的 `Config.from_env()` 里改默认值。**

## 部署定时任务

右键 `setup_task.bat` → **以管理员身份运行**。

会在 Windows 任务计划程序中创建 `TZC_auto_checkin` 任务，每天 21:30 自动执行。

**查看/修改：** 按 `Win+R`，输入 `taskschd.msc`，在任务计划程序库中找。

## 移除定时任务

右键 `remove_task.bat` → 以管理员身份运行。

## 日志

运行记录写入 `checkin.log`（不会被 git 追踪）。每次签到成功或失败都会打印时间戳和详细信息。

## Cookie 自动刷新

脚本会自动判断 `cookies.json` 是否有效：

- **有效** → 直接用，无需任何操作
- **过期** → 自动开无头 Edge 浏览器重新登录 SSO，保存新 Cookie

一切全自动，除非：
- 网络断了
- Edge 浏览器被卸载
- 学工系统改了登录页面结构

## 文件结构

```
TZC-Login/
  login.py          ← 主脚本
  run.bat           ← 手动运行
  setup_task.bat    ← 注册定时任务（管理员）
  remove_task.bat   ← 移除定时任务（管理员）
  README.md         ← 你正在看
  cookies.json      ← 登录缓存（不提交 git）
  checkin.log       ← 运行日志（不提交 git）
```

## 依赖

```
selenium
requests
urllib3
```
