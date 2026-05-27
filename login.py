#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台州学院学工系统 - 自动查寝签到脚本
Cookie 复用 + 无头浏览器登录回退
"""

import json
import os
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import requests
import urllib3
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

urllib3.disable_warnings()


# ======================== Config ========================

@dataclass
class Config:
    """所有配置聚合一处。模块不再散落全局变量。"""
    student_id: str = ''
    password: str = ''
    kqwzxx: str = ''          # 签到位置
    jdzb: float = 0.0         # 经度
    wdzb: float = 0.0         # 纬度
    base_url: str = 'https://xgfw.tzc.edu.cn/xsfw/sys/swmzncqapp/*default/index.do'
    sso_url: str = 'https://sso.tzc.edu.cn'
    info_url: str = 'https://xgfw.tzc.edu.cn/xsfw/sys/swmzncqapp/kqController/getKqInfo.do'
    sign_url: str = 'https://xgfw.tzc.edu.cn/xsfw/sys/swmzncqapp/kqController/addKqInfo.do'
    cookie_file: str = ''
    log_file: str = ''

    @classmethod
    def from_config(cls) -> 'Config':
        """从 config.py 文件加载配置（本地开发）"""
        try:
            import config
        except ImportError:
            print('错误：未找到 config.py')
            print('请复制 config.example.py 为 config.py 并填入真实信息')
            sys.exit(1)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        return cls(
            student_id=config.STUDENT_ID,
            password=config.PASSWORD,
            kqwzxx=config.KQWZXX,
            jdzb=float(config.JDZB),
            wdzb=float(config.WDZB),
            cookie_file=os.path.join(script_dir, 'cookies.json'),
            log_file=os.path.join(script_dir, 'checkin.log'),
        )

    @classmethod
    def from_env(cls) -> 'Config':
        """从环境变量加载配置（CI/CD 云端）"""
        def _get(key: str) -> str:
            val = os.environ.get(key, '')
            if not val:
                raise ValueError(f'环境变量 {key} 未设置')
            return val

        script_dir = os.path.dirname(os.path.abspath(__file__))
        return cls(
            student_id=_get('STUDENT_ID'),
            password=_get('PASSWORD'),
            kqwzxx=_get('KQWZXX'),
            jdzb=float(_get('JDZB')),
            wdzb=float(_get('WDZB')),
            cookie_file=os.path.join(script_dir, 'cookies.json'),
            log_file=os.path.join(script_dir, 'checkin.log'),
        )
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
    """统一成功判定：code='0' 或 status=True"""
    return r.get('code') == '0' or r.get('status') is True


def is_sw_exception(r: dict) -> bool:
    return 'SwException' in str(r)


def is_auth_failure(r: dict) -> bool:
    """401 页面 = 认证已失效"""
    raw = r.get('raw', '')
    return isinstance(raw, str) and '401' in raw


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
    """驱动工厂——自动适配 Windows/Linux"""
    # 1. undetected-chromedriver（反检测，Win/Linux 通用）
    try:
        import undetected_chromedriver as uc
        opts = uc.ChromeOptions()
        opts.add_argument('--headless=new')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-gpu')
        opts.add_argument('--disable-dev-shm-usage')
        log(cfg, '使用 undetected-chromedriver')
        return uc.Chrome(options=opts)
    except Exception as e:
        log(cfg, f'undetected-chromedriver 不可用({e})')

    # 2. Selenium Chrome（Linux CI/CD）
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.chrome.service import Service as ChromeService
        opts = ChromeOptions()
        opts.add_argument('--headless=new')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-gpu')
        opts.add_argument('--disable-dev-shm-usage')
        opts.binary_location = '/usr/bin/google-chrome'
        svc = ChromeService('/usr/bin/chromedriver')
        log(cfg, '使用 Selenium Chrome (Linux)')
        return webdriver.Chrome(service=svc, options=opts)
    except Exception as e:
        log(cfg, f'Chrome 不可用({e})')

    # 3. Selenium Edge（Windows 回退）
    from selenium import webdriver
    from selenium.webdriver.edge.options import Options as EdgeOptions
    opts = EdgeOptions()
    opts.add_argument('--headless')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-gpu')
    opts.add_argument('--disable-dev-shm-usage')
    log(cfg, '使用 Selenium Edge (Windows)')
    return webdriver.Edge(options=opts)


def login_via_browser(cfg: Config) -> list:
    log(cfg, '启动无头浏览器登录 SSO...')

    driver = _create_driver(cfg)
    try:
        driver.get(f'{cfg.sso_url}/login?service={cfg.base_url}')
        log(cfg, f'已打开 SSO 登录页 ({driver.current_url[:100]})')

        wait = WebDriverWait(driver, 15)
        try:
            wait.until(EC.presence_of_element_located((By.NAME, 'username')))
        except Exception:
            log(cfg, f'未找到 username 输入框，URL: {driver.current_url[:100]}')
            log(cfg, f'页面片段: {driver.page_source[:600]}')
            raise

        # 逐字键入，模拟真人
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
        log(cfg, '已提交登录，等待跳转到学工系统...')

        for i in range(30):
            time.sleep(1)
            if 'xgfw.tzc.edu.cn' in driver.current_url:
                log(cfg, f'已跳转到学工系统 (耗时 {i + 1}s)')
                time.sleep(3)
                break
        else:
            log(cfg, f'警告：30s 内未跳转，URL: {driver.current_url[:100]}')

        cookies = driver.get_cookies()
        log(cfg, f'登录完成，获得 {len(cookies)} 个 Cookie')
        return cookies
    finally:
        driver.quit()
# ========================================================


# ==================== Check-in pipeline ==================

def random_offset(val: float) -> float:
    """坐标 ±0.0002° 随机漂移（约 10-20 米）"""
    return val + random.uniform(-0.000200, 0.000200)


def build_payload(cfg: Config) -> dict:
    """组装签到请求体——数据组装与 HTTP 无关"""
    return {
        'KQWZXX': cfg.kqwzxx,
        'JDZB': random_offset(cfg.jdzb),
        'WDZB': random_offset(cfg.wdzb),
    }


def _try_sign_json(cfg: Config, cookies: dict, payload: dict) -> dict:
    """单次 JSON 格式签到尝试"""
    headers = build_headers(cfg)
    headers['Content-Type'] = 'application/json; charset=UTF-8'
    resp = requests.post(cfg.sign_url, json=payload, headers=headers,
                         cookies=cookies, verify=False, timeout=15)
    return parse_response(resp)


def _try_sign_form(cfg: Config, cookies: dict, payload: dict) -> dict:
    """单次表单格式签到尝试"""
    headers = build_headers(cfg)
    form_data = {k: str(v) for k, v in payload.items()}
    resp = requests.post(cfg.sign_url, data=form_data, headers=headers,
                         cookies=cookies, verify=False, timeout=15)
    return parse_response(resp)


def do_checkin(cfg: Config, cookies: list) -> bool:
    """执行签到：JSON 优先，SwException 回退表单"""
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
    """Windows 弹窗。无桌面会话时静默。"""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, title, icon)
    except Exception:
        pass
# ========================================================


# ======================== Main ===========================

def main(cfg: Config | None = None,
         notify: Callable[[str, str, int], None] | None = None) -> bool:
    """
    签到主流程。返回 bool 而非 sys.exit，测试友好。
    cfg: 配置实例，None 时从环境变量加载
    notify: 通知回调，None 时用默认 Windows 弹窗
    """
    if cfg is None:
        try:
            cfg = Config.from_config()
        except SystemExit:
            cfg = Config.from_env()
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
