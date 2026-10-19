"""Mobile sign-in UI. Credentials are transient and are never logged or persisted."""
import hashlib
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

import signin_core as core

ROOT = Path(__file__).resolve().parent
BEIJING = timezone(timedelta(hours=8))
core.logger = logging.getLogger('signin-private')
core.logger.disabled = True
_request = core.http_request_json


def bounded_request(*args, **kwargs):
    kwargs['timeout'] = 12
    return _request(*args, **kwargs)


core.http_request_json = bounded_request


def beijing_time():
    now = datetime.now(BEIJING)
    return {'date': now.strftime('%Y-%m-%d'), 'time': now.strftime('%H:%M:%S')}


core.get_time = beijing_time
busy = threading.BoundedSemaphore(1)
rate_lock = threading.Lock()
attempts = {}


def run_signin(student_id, password):
    user = core.User(student_Id=int(student_id), password=password)
    step, failures, calls = 0, 0, 0
    deadline = time.monotonic() + 80
    try:
        while 0 <= step < 6 and failures < 4 and calls < 15:
            if time.monotonic() > deadline:
                return False, '学校接口响应较慢，请先在学校系统查看记录，再决定是否重试。'
            previous = step
            result = core.sign_in_by_step(user, step, debug=False)
            calls += 1
            step = result['step']
            if not result['success']:
                failures += 1
                if previous == 0:
                    return False, '登录失败，请检查学号、考勤密码及学校系统是否可访问。'
                if step == -1:
                    return False, '当前无法签到：可能尚未开放签到，或未能获取宿舍信息。请到学校系统核对。'
            if step == 6:
                return True, '学校接口已返回签到成功或今日已完成。请在学校系统核对实际记录。'
            time.sleep(1)
        return False, '学校接口未确认成功，请在学校系统查看详情后再试。'
    finally:
        user.password = ''
        user.token = None


def allowed_attempt(student_id, address):
    now = time.monotonic()
    keys = [('account', hashlib.sha256(student_id.encode()).hexdigest()), ('ip', address)]
    with rate_lock:
        for key in list(attempts):
            if now - attempts[key][0] >= 60:
                del attempts[key]
        if len(attempts) > 4096:
            return False
        if any(attempts.get(key, (now, 0))[1] >= limit for key, limit in zip(keys, [2, 6])):
            return False
        for key in keys:
            start, count = attempts.get(key, (now, 0))
            attempts[key] = (start, count + 1)
    return True


def application(env, start_response):
    headers = [('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
               ('X-Frame-Options', 'DENY'), ('Referrer-Policy', 'no-referrer'),
               ('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")]

    def send(status, body, content_type='application/json; charset=utf-8'):
        if isinstance(body, dict):
            body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        start_response(status, headers + [('Content-Type', content_type), ('Content-Length', str(len(body)))])
        return [body]

    path, method = env.get('PATH_INFO', '/'), env.get('REQUEST_METHOD', 'GET')
    files = {'/': ('index.html', 'text/html; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8'),
             '/app.js': ('app.js', 'text/javascript; charset=utf-8')}
    if method == 'GET' and path in files:
        name, content_type = files[path]
        return send('200 OK', (ROOT / name).read_bytes(), content_type)
    if method == 'GET' and path == '/api/health':
        return send('200 OK', {'ok': True, 'time': datetime.now(BEIJING).strftime('%H:%M'), 'mode': '手动签到'})
    if path != '/api/signin':
        return send('404 Not Found', {'ok': False, 'message': '页面不存在。'})
    if method != 'POST':
        return send('405 Method Not Allowed', {'ok': False, 'message': '请使用页面提交。'})
    expected_origin = (os.environ.get('SITE_ORIGIN') or os.environ.get('RENDER_EXTERNAL_URL') or 'http://127.0.0.1:8765').rstrip('/')
    if env.get('HTTP_ORIGIN') != expected_origin or env.get('HTTP_X_SIGNIN_CLIENT') != '1':
        return send('403 Forbidden', {'ok': False, 'message': '页面来源不匹配，请从正确网址重新打开。'})
    if env.get('CONTENT_TYPE', '').split(';')[0] != 'application/json':
        return send('415 Unsupported Media Type', {'ok': False, 'message': '请求格式不正确。'})
    try:
        length = int(env.get('CONTENT_LENGTH') or '0')
        if not 0 < length <= 2048:
            return send('413 Content Too Large', {'ok': False, 'message': '请求内容过长或为空。'})
        data = json.loads(env['wsgi.input'].read(length))
        if not isinstance(data, dict):
            raise ValueError()
        student_id, password = data.get('student_id'), data.get('password')
        if not isinstance(student_id, str) or not student_id.isascii() or not student_id.isdigit() or not 5 <= len(student_id) <= 20:
            raise ValueError()
        if not isinstance(password, str) or not 1 <= len(password) <= 128 or data.get('consent') is not True:
            raise ValueError()
    except (ValueError, TypeError, UnicodeError):
        return send('400 Bad Request', {'ok': False, 'message': '请填写正确的学号、密码，并确认使用本人账号。'})
    if not allowed_attempt(student_id, env.get('REMOTE_ADDR', 'unknown')):
        return send('429 Too Many Requests', {'ok': False, 'message': '操作较频繁，请一分钟后再试。'})
    if beijing_time()['time'] < '21:20:00':
        return send('409 Conflict', {'ok': False, 'message': '当前早于北京时间 21:20，请在学校开放签到后再试。'})
    if not busy.acquire(blocking=False):
        return send('503 Service Unavailable', {'ok': False, 'message': '当前有人正在签到，请稍后重试。'})
    try:
        ok, message = run_signin(student_id, password)
        return send('200 OK', {'ok': ok, 'message': message})
    except Exception:
        return send('502 Bad Gateway', {'ok': False, 'message': '未能确认签到结果，请到学校系统核对。'})
    finally:
        password = ''
        data.clear()
        busy.release()


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


class LocalServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


if __name__ == '__main__':
    print('Local preview: http://127.0.0.1:8765', flush=True)
    print('Press Ctrl+C to stop. Credentials are not saved.', flush=True)
    with make_server('127.0.0.1', 8765, application, server_class=LocalServer, handler_class=QuietHandler) as server:
        server.serve_forever()
