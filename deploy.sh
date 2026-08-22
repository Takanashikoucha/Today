#!/usr/bin/env bash
# ============================================================
#  Today 项目一键部署脚本
#
#  作用: 把本目录(today/)的所有文件推送到
#        https://github.com/Takanashikoucha/Today (main 分支)
#        覆盖仓库中的旧文件, 保留 git 历史。
#
#  用法:
#    1. 获取 Token:
#       GitHub → Settings → Developer settings → Personal access tokens
#       → Tokens (classic) → 勾选 "repo" 权限 → Generate
#    2. 进入 today/ 目录, 运行:
#       export GITHUB_TOKEN=ghp_xxxxxxxxxxxx
#       bash deploy.sh
#
#  安全说明(不泄露 token):
#    - token 只存在于当前 shell 的 GITHUB_TOKEN 环境变量
#    - 通过 git 的 per-process 配置(GIT_CONFIG_*)与 GIT_ASKPASS
#      临时进程传递凭据, 绝不写入 .git/config 或任何文件
#    - 脚本退出 / Ctrl+C / 崩溃时, 临时 askpass 文件被 trap 删除
#    - 全程不在终端回显 token
# ============================================================
set -euo pipefail

# ---------- 配置(按需修改) ----------
REPO_URL="https://github.com/Takanashikoucha/Today.git"
REPO_HTTPS="https://github.com/Takanashikoucha/Today"   # 展示用, 不带 .git
BRANCH="main"
GIT_NAME="${GIT_NAME:-TakanashiKoucha}"
GIT_EMAIL="${GIT_EMAIL:-takanashikoucha@users.noreply.github.com}"
# ------------------------------------

# 必须从 today/ 目录(脚本所在目录)运行
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 1) 检查 token (不打印 token 本身)
if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "❌ 未提供 GITHUB_TOKEN。"
  echo "   请先运行: export GITHUB_TOKEN=ghp_xxxx"
  echo "   生成: GitHub → Settings → Developer settings → PAT (classic) → 勾选 repo"
  exit 1
fi
command -v git >/dev/null 2>&1 || { echo "❌ 未找到 git, 请先安装。"; exit 1; }

# 2) 确保本目录是 git 仓库(没有就初始化)
if [[ ! -d .git ]]; then
  echo "→ 当前目录尚无 .git, 初始化 (分支: $BRANCH)..."
  git init -b "$BRANCH"
fi

# 3) git 身份
git config user.name  "$GIT_NAME"
git config user.email "$GIT_EMAIL"

# 4) 安全认证: GIT_ASKPASS 临时进程 + per-process 配置
#    - 凭据只活在当前进程环境变量里, 不落地任何文件
#    - 关闭 git 的 credential 缓存/存储与交互式提示
ASKPASS_FILE="$(mktemp "${TMPDIR:-/tmp}/today-askpass.XXXXXX")"
chmod 700 "$ASKPASS_FILE"
cat > "$ASKPASS_FILE" <<'ASKEOF'
#!/usr/bin/env bash
case "$1" in
  *Username*) printf '%s\n' "x-access-token" ;;
  *Password*) printf '%s\n' "$GITHUB_TOKEN" ;;
  *)          printf '\n' ;;
esac
ASKEOF

export GIT_ASKPASS="$ASKPASS_FILE"
export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS_REQUIRED=1
# 关闭任何 credential helper(防止写入 ~/.git-credentials 等)
export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0="credential.helper"
export GIT_CONFIG_VALUE_0=""

cleanup() { rm -f "$ASKPASS_FILE"; }
trap cleanup EXIT INT TERM

# 5) 配置 remote
git remote remove origin 2>/dev/null || true
git remote add origin "$REPO_URL"

# 6) 拉取远端历史
echo "→ 检查远端仓库 $REPO_HTTPS ..."
if git ls-remote --exit-code "$REPO_URL" >/dev/null 2>&1; then
  git fetch origin
  if git rev-parse --verify "origin/$BRANCH" >/dev/null 2>&1; then
    git checkout -f "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH" "origin/$BRANCH"
    git reset --hard "origin/$BRANCH"
    echo "→ 已对齐远端 $BRANCH。"
  else
    git checkout -b "$BRANCH" 2>/dev/null || git checkout "$BRANCH"
  fi
else
  echo "→ 远端为空仓库。"
  git checkout -b "$BRANCH" 2>/dev/null || git checkout "$BRANCH"
fi

# 7) 确保 .gitignore(防止 .venv / data / __pycache__ 被推上去)
if [[ ! -f .gitignore ]]; then
  echo "→ 生成 .gitignore ..."
  cat > .gitignore <<'EOF'
__pycache__/
*.pyc
.venv/
data/
.npm-cache/
node_modules/
*.tmp
.env
EOF
fi

# 8) 提交(覆盖式)
git add -A
if git diff --cached --quiet; then
  echo "→ 与远端无差异, 无需提交。"
else
  git commit -m "feat: redesign Today - 月历+SGE金价+折线图+倒计时

- 月历: 农历/公历生日强调, 每日金价红涨绿跌
- 金价: 上海黄金交易所 Au99.99, 3个月历史, 每10秒自动刷新
- 近3个月金价折线图(SVG), 家人生日倒计时
- 跟随系统亮/暗色, 全面响应式
- members.json 配置化, 新增家人无需改代码"
fi

# 9) 推送
echo "→ 推送到 origin/$BRANCH ..."
git push -u origin "$BRANCH"

echo ""
echo "✅ 部署完成!"
echo "   仓库: $REPO_HTTPS"
echo "   分支: $BRANCH"
echo "   下一步: 到 https://render.com 连接该仓库即可上线。"
