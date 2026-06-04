#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台州学院学工系统 - 自动查寝签到脚本
用法: python login.py              → 执行签到
      python login.py --setup      → 注册定时任务（需要管理员）
      python login.py --remove     → 移除定时任务（需要管理员）

打包后: tzc_checkin.exe / tzc_checkin.exe --setup / tzc_checkin.exe --remove
"""

import json
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

import requests
import urllib3
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

urllib3.disable_warnings()

TASK_NAME = 'TZC_auto_checkin'


# ======================== Config ========================

@dataclass
class Config:
    student_id: str = ''
    password: str = ''
    kqwzxx: str = ''
    jdzb: float = 0.0
    wdzb: float = 0.0
    base_url: str = 'https://xgfw.tzc.edu.cn/xsfw/sys/swmzncqapp/*default/index.do'
    sso_url: str = 'https://sso.tzc.edu.cn'
    info_url: str = 'https://xgfw.tzc.edu.cn/xsfw/sys/swmzncqapp/kqController/getKqInfo.do'
    sign_url: str = 'https://xgfw.tzc.edu.cn/xsfw/sys/swmzncqapp/kqController/addKqInfo.do'
    cookie_file: str = ''
    log_file: str = ''

    @classmethod
    def from_file(cls) -> 'Config':
        app_dir = _app_dir()
        config_path = os.path.join(app_dir, 'config.txt')
        if not os.path.exists(config_path):
            print(f'错误：未找到 {config_path}')
            print('请复制 config.example.txt 为 config.txt 并填入真实信息')
            sys.exit(1)

        cfg = {}
        with open(config_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    cfg[key.strip()] = val.strip()

        return cls(
            student_id=cfg.get('STUDENT_ID', ''),
            password=cfg.get('PASSWORD', ''),
            kqwzxx=cfg.get('KQWZXX', ''),
            jdzb=float(cfg.get('JDZB', 0)),
            wdzb=float(cfg.get('WDZB', 0)),
            cookie_file=os.path.join(app_dir, 'cookies.json'),
            log_file=os.path.join(app_dir, 'checkin.log'),
        )
# ========================================================


# ====================== App Dir ==========================

def _app_dir() -> str:
    """获取 .exe 或脚本所在目录（打包后和开发环境都正确）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))
# ========================================================


# ======================== Admin ==========================

def _is_admin():
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def _elevate():
    """提权重启当前进程（UAC 弹窗确认）"""
    import ctypes
    exe = sys.executable
    args = ' '.join(sys.argv)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args, None, 1)
    sys.exit(0)


def _exe_path():
    """定时任务中要执行的命令"""
    app_dir = _app_dir()
    if getattr(sys, 'frozen', False):
        return f'cmd /c cd /d {app_dir} && {sys.executable}'
    else:
        return f'cmd /c cd /d {app_dir} && python login.py'
# ========================================================


# ==================== Task Manager =======================

def setup_task():
    """注册 Windows 定时任务（需要管理员）"""
    if not _is_admin():
        _elevate()
    import subprocess
    cmd = (
        f'schtasks /create /tn {TASK_NAME} '
        f'/tr "{_exe_path()}" '
        f'/sc daily /st 21:30 /it /f'
    )
    subprocess.run(cmd, shell=True)
    print(f'Task created: {TASK_NAME} (daily 21:30)')


def remove_task():
    """移除 Windows 定时任务（需要管理员）"""
    if not _is_admin():
        _elevate()
    import subprocess
    subprocess.run(f'schtasks /delete /tn {TASK_NAME} /f', shell=True)
    print(f'Task removed: {TASK_NAME}')
# ========================================================


# ======================== Logging ========================

def log(cfg: Config, msg: str) -> None:
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{timestamp}] {msg}'
    print(line)
    with open(cfg.log_file, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
# ========================================================


# ==================== API predicates =====================

def is_api_success(r: dict) -> bool:
    return r.get('code') == '0' or r.get('status') is True


def is_sw_exception(r: dict) -> bool:
    return 'SwException' in str(r)


def parse_response(resp: requests.Response) -> dict:
    try:
        return resp.json()
    except Exception:
        return {'raw': resp.text}
# ========================================================


# ====================== Headers ==========================

def build_headers(cfg: Config) -> dict:
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Referer': cfg.base_url,
        'Origin': 'https://xgfw.tzc.edu.cn',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    }
# ========================================================


# ==================== Cookie store =======================

def load_cookies(cfg: Config) -> list | None:
    if not os.path.exists(cfg.cookie_file):
        return None
    with open(cfg.cookie_file, 'r', encoding='utf-8') as f:
        cookies = json.load(f)
    log(cfg, f'从文件加载了 {len(cookies)} 个 Cookie')
    return cookies


def save_cookies(cfg: Config, cookies: list) -> None:
    with open(cfg.cookie_file, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    log(cfg, f'已保存 {len(cookies)} 个 Cookie 到文件')


def cookies_are_valid(cfg: Config, cookies: list) -> bool:
    cookie_dict = {c['name']: c['value'] for c in cookies}
    headers = build_headers(cfg)
    try:
        resp = requests.post(cfg.info_url, data={}, headers=headers,
                             cookies=cookie_dict, verify=False, timeout=15)
        data = parse_response(resp)
        if is_api_success(data) and data.get('data'):
            log(cfg, 'Cookie 有效，无需重新登录')
            return True
        log(cfg, f'Cookie 无效，服务器返回: {resp.text[:150]}')
    except Exception as e:
        log(cfg, f'Cookie 校验失败: {e}')
    return False
# ========================================================


# ==================== Browser login ======================

def _create_driver(cfg: Config):
    from selenium import webdriver
    from selenium.webdriver.edge.options import Options as EdgeOptions
    opts = EdgeOptions()
    opts.add_argument('--headless')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-gpu')
    opts.add_argument('--disable-dev-shm-usage')
    log(cfg, '使用 Selenium Edge')
    return webdriver.Edge(options=opts)


def _login_headless(cfg: Config) -> list:
    """无头模式自动登录"""
    log(cfg, '启动无头浏览器登录 SSO...')
    driver = _create_driver(cfg)
    try:
        driver.get(f'{cfg.sso_url}/login?service={cfg.base_url}')
        log(cfg, f'已打开 SSO 登录页 ({driver.current_url[:100]})')

        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.NAME, 'username')))

        uname = driver.find_element(By.NAME, 'username')
        for ch in cfg.student_id:
            uname.send_keys(ch)
            time.sleep(random.uniform(0.05, 0.15))

        pwd = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
        for ch in cfg.password:
            pwd.send_keys(ch)
            time.sleep(random.uniform(0.05, 0.15))

        log(cfg, '已填入账号密码')
        driver.find_element(By.XPATH, '//button[@type="submit"]').click()
        log(cfg, '已提交登录...')

        # 等待下一步：短信验证 或 直接跳转
        time.sleep(3)

        # 检查是否是短信验证页面
        sms_input = None
        try:
            sms_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@placeholder='请输入验证码']"))
            )
        except Exception:
            pass

        if sms_input:
            log(cfg, '检测到短信验证页面！')
            try:
                btn = driver.find_element(By.XPATH, "//a[contains(text(),'获取验证码')]")
                btn.click()
                log(cfg, '已点击"获取验证码"，验证码已发送至手机')
            except Exception:
                pass

            code = input('请输入短信验证码: ').strip()
            sms_input.send_keys(code)
            log(cfg, '已填入验证码')

            try:
                driver.find_element(By.XPATH, "//button[@type='submit']").click()
                log(cfg, '已提交验证')
            except Exception:
                sms_input.send_keys('\n')

        # 等待跳转到学工系统
        log(cfg, '等待跳转到学工系统...')
        for i in range(30):
            time.sleep(1)
            if 'xgfw.tzc.edu.cn' in driver.current_url:
                log(cfg, f'已跳转到学工系统 (耗时 {i + 1}s)')
                time.sleep(3)
                break
        else:
            log(cfg, f'无头模式未跳转，URL: {driver.current_url[:100]}')

        return driver.get_cookies()
    finally:
        driver.quit()


def _login_manual(cfg: Config) -> list:
    """打开可见浏览器，用户手动完成登录（含人机验证、短信）"""
    log(cfg, '========== 打开可见浏览器 ==========')
    log(cfg, '请在浏览器中手动完成登录（包括人机验证、短信验证码）')
    log(cfg, '登录成功后脚本会自动检测并继续...')

    from selenium import webdriver as wd
    driver = wd.Edge()
    try:
        driver.get(f'{cfg.sso_url}/login?service={cfg.base_url}')

        # 等待用户手动登录完成
        for i in range(300):  # 最多等 5 分钟
            time.sleep(1)
            url = driver.current_url
            if 'xgfw.tzc.edu.cn' not in url:
                continue

            # 额外等 5 秒让页面 JavaScript 完成初始化
            time.sleep(5)
            cookies = driver.get_cookies()

            # 确认不是 401 错误页
            if len(cookies) >= 2:
                body = driver.find_element(By.TAG_NAME, 'body').text
                if 'Not login' not in body and '401' not in body:
                    log(cfg, f'已登录学工系统 ({len(cookies)} Cookie)')
                    return cookies

            log(cfg, f'xgfw 已加载但未真登录 ({len(cookies)} Cookie)，继续等...')

        log(cfg, '超时：5 分钟内未完成登录')
        return []
    finally:
        driver.quit()


def login_via_browser(cfg: Config) -> list:
    # 先试无头
    cookies = _login_headless(cfg)
    if len(cookies) >= 2:
        log(cfg, f'自动登录成功 ({len(cookies)} 个 Cookie)')
        return cookies

    # 失败 → 手动
    log(cfg, '自动登录未获取足够 Cookie，切换手动模式...')
    return _login_manual(cfg)
# ========================================================


# ==================== Check-in pipeline ==================

def random_offset(val: float) -> float:
    return val + random.uniform(-0.000200, 0.000200)


def build_payload(cfg: Config) -> dict:
    return {
        'KQWZXX': cfg.kqwzxx,
        'JDZB': random_offset(cfg.jdzb),
        'WDZB': random_offset(cfg.wdzb),
    }


def _try_sign_json(cfg: Config, cookies: dict, payload: dict) -> dict:
    headers = build_headers(cfg)
    headers['Content-Type'] = 'application/json; charset=UTF-8'
    resp = requests.post(cfg.sign_url, json=payload, headers=headers,
                         cookies=cookies, verify=False, timeout=15)
    return parse_response(resp)


def _try_sign_form(cfg: Config, cookies: dict, payload: dict) -> dict:
    headers = build_headers(cfg)
    form_data = {k: str(v) for k, v in payload.items()}
    resp = requests.post(cfg.sign_url, data=form_data, headers=headers,
                         cookies=cookies, verify=False, timeout=15)
    return parse_response(resp)


def do_checkin(cfg: Config, cookies: list) -> bool:
    cookie_dict = {c['name']: c['value'] for c in cookies}
    payload = build_payload(cfg)
    jdz, wdz = payload['JDZB'], payload['WDZB']

    log(cfg, f'提交签到(JSON) 坐标={jdz:.6f},{wdz:.6f}...')
    time.sleep(2)
    result = _try_sign_json(cfg, cookie_dict, payload)

    if is_api_success(result):
        log(cfg, '签到成功(JSON)')
        return True

    if is_sw_exception(result):
        log(cfg, 'JSON 被拒，回退表单格式...')
        result2 = _try_sign_form(cfg, cookie_dict, payload)
        if is_api_success(result2):
            log(cfg, '签到成功(表单)')
            return True
        log(cfg, f'签到失败(表单): {result2}')
    else:
        log(cfg, f'签到失败(JSON): {result}')

    return False
# ========================================================


# ==================== Notification =======================

def _notify(title: str, msg: str, icon: int) -> None:
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, title, icon)
    except Exception:
        pass
# ========================================================


# ======================== Main ===========================

def main(cfg: Config | None = None,
         notify: Callable[[str, str, int], None] | None = None) -> bool:

    # CLI 控制命令
    if '--setup' in sys.argv:
        setup_task()
        return True
    if '--remove' in sys.argv:
        remove_task()
        return True

    # 签到流程
    if cfg is None:
        cfg = Config.from_file()
    if notify is None:
        notify = _notify

    log(cfg, '========== 查寝签到开始 ==========')

    cookies = load_cookies(cfg)
    if cookies and cookies_are_valid(cfg, cookies):
        pass
    else:
        log(cfg, '需要重新登录')
        cookies = login_via_browser(cfg)
        if not cookies:
            log(cfg, '登录失败，退出')
            notify('TZC 签到失败',
                   f'登录失败，无法获取 Cookie。\n\n日志文件: {cfg.log_file}',
                   0x30)
            return False
        save_cookies(cfg, cookies)

    success = do_checkin(cfg, cookies)
    if success:
        log(cfg, '========== 签到成功 ==========')
        notify('TZC 签到成功', '自动查寝签到已完成。', 0x40)
    else:
        log(cfg, '========== 签到失败 ==========')
        notify('TZC 签到失败',
               f'自动查寝签到失败，请检查。\n\n'
               f'可能原因：Cookie过期、网络问题、不在考勤时段。\n\n'
               f'日志文件: {cfg.log_file}',
               0x30)
    return success


if __name__ == '__main__':
    ok = main()
    sys.exit(0 if ok else 1)
