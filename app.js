const form = document.querySelector('#signin-form');
const password = document.querySelector('#password');
const submit = document.querySelector('#submit');
const label = document.querySelector('#button-label');
const result = document.querySelector('#result');
const toggle = document.querySelector('#toggle-password');
toggle.addEventListener('click', () => {
  const visible = password.type === 'password';
  password.type = visible ? 'text' : 'password';
  toggle.textContent = visible ? '隐藏' : '显示';
  toggle.setAttribute('aria-pressed', String(visible));
});
function updateClock() {
  document.querySelector('#clock').textContent = '北京时间 ' + new Intl.DateTimeFormat('zh-CN', {timeZone:'Asia/Shanghai', hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date());
}
updateClock(); setInterval(updateClock, 30000);
function show(message, state) { result.hidden = false; result.textContent = message; result.dataset.state = state; }
form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (submit.disabled || !form.reportValidity()) return;
  submit.disabled = true; label.textContent = '正在连接学校系统…';
  show('正在处理，请保持页面打开。通常需要十几秒，网络较慢时可能需要约一分钟。', 'pending');
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 110000);
  const body = JSON.stringify({student_id:document.querySelector('#student').value.trim(), password:password.value, consent:document.querySelector('#consent').checked});
  password.value = ''; password.type = 'password'; toggle.textContent = '显示'; toggle.setAttribute('aria-pressed','false');
  try {
    const response = await fetch('/api/signin', {method:'POST',headers:{'Content-Type':'application/json','X-Signin-Client':'1'},body,signal:controller.signal,cache:'no-store',credentials:'omit'});
    const data = await response.json();
    show(data.message || '未收到明确结果，请到学校系统核对。', response.ok && data.ok ? 'success' : 'error');
  } catch (error) {
    show(error.name === 'AbortError' ? '等待超时，后台可能仍在处理。请先到学校系统核对记录，不要连续重复提交。' : '连接中断，无法确认结果。请先到学校系统核对记录。', 'error');
  } finally { clearTimeout(timeout); submit.disabled = false; label.textContent = '开始签到'; }
});
