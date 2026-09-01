"""修复：手动在 game.yunque.co 的 443 server 块中添加 /hustle/ location"""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('8.140.194.184', 22, 'root', '7aK_H2yvokVuZ5HtL5Qrwl19m7L', timeout=20)

NGINX_FILE = '/etc/nginx/sites-enabled/game.yunque.co'

# 读当前内容
sftp = c.open_sftp()
with sftp.open(NGINX_FILE, 'r') as f:
    current = f.read().decode()

print('=== 当前配置 ===')
print(current)
print('================')

if '/hustle/' in current:
    print('[i] 已有 /hustle/，跳过')
else:
    # 手工解析：找 443 server 块，然后找该块内第一个 `location /` 并在其前插入
    import re
    # 找所有 server { ... } 块
    blocks = []
    depth = 0
    start = None
    for i, ch in enumerate(current):
        if ch == '{':
            if depth == 0 and i >= 6 and current[max(0, i-10):i].rstrip().endswith('server'):
                start = current.rfind('server', 0, i)
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                blocks.append((start, i+1))
                start = None

    target = None
    for s, e in blocks:
        blk = current[s:e]
        if 'listen 443' in blk:
            target = (s, e, blk)
            break
    if not target:
        print('[x] 未找到 443 server 块')
        raise SystemExit(1)
    s, e, blk = target
    # 在该块里找第一个 "location /"（精确单斜杠）
    m = re.search(r'\n(\s*)location\s+/\s*\{', blk)
    if not m:
        print('[x] 443 块内没有 location /')
        raise SystemExit(1)
    indent = m.group(1)
    hustle_loc = f"""
{indent}location /hustle/ {{
{indent}    proxy_pass http://127.0.0.1:8089/;
{indent}    proxy_set_header Host $host;
{indent}    proxy_set_header X-Real-IP $remote_addr;
{indent}    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
{indent}    proxy_set_header X-Forwarded-Proto $scheme;
{indent}}}
"""
    insert_at = s + m.start()
    new_text = current[:insert_at] + hustle_loc + current[insert_at:]

    # 备份
    import time
    bak = NGINX_FILE + f'.bak.{int(time.time())}'
    with sftp.open(bak, 'w') as f:
        f.write(current)
    # 写入
    with sftp.open(NGINX_FILE, 'w') as f:
        f.write(new_text)
    print(f'[OK] 已写入，备份在 {bak}')

sftp.close()

# 验证 + reload
print('\n=== nginx -t ===')
_, o, e = c.exec_command('nginx -t 2>&1', timeout=10)
print(o.read().decode())
_, o, e = c.exec_command('nginx -s reload 2>&1; echo "reload exit=$?"', timeout=10)
print(o.read().decode())

print('\n=== 新配置内容 ===')
_, o, _ = c.exec_command(f'cat {NGINX_FILE}', timeout=10)
print(o.read().decode())

print('\n=== 测试 /hustle/health ===')
_, o, _ = c.exec_command("curl -sSk https://127.0.0.1/hustle/health -H 'Host: game.yunque.co'", timeout=10)
print(o.read().decode())

c.close()
