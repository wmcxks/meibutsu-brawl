"""SSH 到线上服务器查找 phpMyAdmin/MySQL 真实密码（凭据从 server/.env 读取）"""
import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / "server" / ".env"
load_dotenv(ENV_PATH)

HOST = os.environ["SSH_HOST"]
USER = os.environ["SSH_USER"]
PASSWORD = os.environ["SSH_PASSWORD"]

CMD = r"""
echo "==== 1. 所有运行的 docker 容器 ===="
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}"

echo ""
echo "==== 2. phpMyAdmin 容器环境变量 ===="
PMA_C=$(docker ps --format '{{.Names}}' | grep -i phpmyadmin | head -1)
echo "phpMyAdmin 容器名: $PMA_C"
[ -n "$PMA_C" ] && docker inspect "$PMA_C" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -Ei "PMA|MYSQL|HOST"

echo ""
echo "==== 3. MySQL 容器环境变量 ===="
MY_C=$(docker ps --format '{{.Names}}' | grep -iE 'mysql|mariadb' | head -1)
echo "MySQL 容器名: $MY_C"
[ -n "$MY_C" ] && docker inspect "$MY_C" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -Ei "MYSQL|PASS|ROOT"

echo ""
echo "==== 4. docker-compose.yml 候选位置 ===="
find /root /home /opt -maxdepth 4 -type f \( -name "docker-compose*.yml" -o -name "docker-compose*.yaml" \) 2>/dev/null | head -20

echo ""
echo "==== 5. 服务器上所有 .env 文件（含 MySQL 密码）===="
find /root /home /opt -maxdepth 5 -type f -name ".env" 2>/dev/null | while read f; do
    if grep -qiE "MYSQL|DB_PASS|PMA" "$f"; then
        echo "--- $f ---"
        grep -iE "MYSQL|DB_PASS|PMA|PASSWORD" "$f"
    fi
done

echo ""
echo "==== 6. 直接进 MySQL 容器问 root 密码（看 mysql 系统库 user 表）===="
[ -n "$MY_C" ] && docker exec "$MY_C" sh -c 'env' 2>/dev/null | grep -Ei "PASS|ROOT"
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=15)
print(f"[i] 已连接 {HOST}\n")

stdin, stdout, stderr = c.exec_command(CMD, timeout=60)
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err.strip():
    print("== STDERR ==\n" + err)
c.close()
