#!/bin/bash
# ============================================================
# 服务器环境巡检脚本
# 用法：scp 到服务器后执行  bash server_check.sh
# ============================================================

echo "========================================"
echo "  服务器环境巡检报告"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"

echo ""
echo "== 1. 系统信息 =="
uname -a
cat /etc/os-release 2>/dev/null | grep -E "^(NAME|VERSION)="

echo ""
echo "== 2. /home/web/ 目录结构 =="
ls -la /home/web/ 2>/dev/null || echo "[!] /home/web/ 不存在"

echo ""
echo "== 3. ai-jinmao-server 项目结构（2层）=="
if [ -d /home/web/ai-jinmao-server ]; then
  find /home/web/ai-jinmao-server -maxdepth 2 -not -path '*/node_modules/*' -not -path '*/.git/*' -not -path '*/__pycache__/*' -not -path '*/.venv/*' | sort
else
  echo "[!] /home/web/ai-jinmao-server 不存在"
fi

echo ""
echo "== 4. ai-jinmao-server Git 信息 =="
if [ -d /home/web/ai-jinmao-server/.git ]; then
  cd /home/web/ai-jinmao-server
  echo "当前分支: $(git branch --show-current)"
  echo "最近5次提交:"
  git log --oneline -5
  echo "远程仓库:"
  git remote -v
else
  echo "[!] 不是 git 仓库"
fi

echo ""
echo "== 5. 配置文件检测 =="
for f in .env .env.example docker-compose.yml docker-compose.yaml Dockerfile requirements.txt pyproject.toml package.json; do
  path="/home/web/ai-jinmao-server/$f"
  if [ -f "$path" ]; then
    echo "[✓] $f ($(wc -l < "$path") 行)"
  fi
done

echo ""
echo "== 6. .env 内容（隐藏密码）=="
if [ -f /home/web/ai-jinmao-server/.env ]; then
  sed 's/=.*/=***/' /home/web/ai-jinmao-server/.env
else
  echo "[!] 无 .env 文件"
fi

echo ""
echo "== 7. 端口占用情况 =="
ss -tlnp 2>/dev/null | grep -E 'LISTEN' | head -20

echo ""
echo "== 8. 已安装的关键服务 =="
echo -n "Python: "; python3 --version 2>/dev/null || echo "未安装"
echo -n "uv: "; uv --version 2>/dev/null || echo "未安装"
echo -n "Node: "; node --version 2>/dev/null || echo "未安装"
echo -n "MySQL: "; mysql --version 2>/dev/null || echo "未安装"
echo -n "Nginx: "; nginx -v 2>&1 || echo "未安装"
echo -n "Docker: "; docker --version 2>/dev/null || echo "未安装"
echo -n "Git: "; git --version 2>/dev/null || echo "未安装"

echo ""
echo "== 9. Nginx 配置 =="
if [ -d /etc/nginx/sites-enabled ]; then
  echo "sites-enabled:"
  ls -la /etc/nginx/sites-enabled/
  echo "--- 内容 ---"
  cat /etc/nginx/sites-enabled/* 2>/dev/null
elif [ -d /etc/nginx/conf.d ]; then
  echo "conf.d:"
  ls -la /etc/nginx/conf.d/
  echo "--- 内容 ---"
  cat /etc/nginx/conf.d/*.conf 2>/dev/null
else
  echo "[!] 未找到 Nginx 配置目录"
fi

echo ""
echo "== 10. systemd 自定义服务 =="
ls /etc/systemd/system/*.service 2>/dev/null | grep -v wants | head -10 || echo "无自定义服务"

echo ""
echo "== 11. Docker 容器（如果有）=="
docker ps -a 2>/dev/null || echo "Docker 未运行或未安装"

echo ""
echo "== 12. 磁盘与内存 =="
df -h / | tail -1
free -h | head -2

echo ""
echo "========================================"
echo "  巡检完毕"
echo "========================================"
