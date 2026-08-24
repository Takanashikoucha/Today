#!/usr/bin/env bash
# ============================================================
#  Today 一键部署脚本
#
#  把当前目录(today/)推送到 https://github.com/Takanashikoucha/Today
#  会清掉远端的旧文件(metal.py / todayDate.py 等), 只保留新结构。
#
#  用法:
#    cd today/
#    export GITHUB_TOKEN=ghp_xxx     # GitHub PAT, 勾 repo 权限
#    bash deploy.sh
#
#  token 只存在环境变量, 通过 GIT_ASKPASS 临时进程传递, 不落盘。
# ============================================================
set -euo pipefail

REPO_URL="https://github.com/Takanashikoucha/Today.git"
REPO_HTTPS="https://github.com/Takanashikoucha/Today"
BRANCH="main"
GIT_NAME="${GIT_NAME:-TakanashiKoucha}"
GIT_EMAIL="${GIT_EMAIL:-takanashikoucha@users.noreply.github.com}"

cd "$(cd "$(dirname "$0")" && pwd)"

# 1) token 检查(不回显)
if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "❌ 未提供 GITHUB_TOKEN, 请先: export GITHUB_TOKEN=ghp_xxx"
  exit 1
fi
command -v git >/dev/null 2>&1 || { echo "❌ 未找到 git"; exit 1; }

# 2) 认证: GIT_ASKPASS 临时进程 + 关闭 credential 缓存(不写任何文件)
ASKPASS_FILE="$(mktemp "${TMPDIR:-/tmp}/today-askpass.XXXXXX")"
chmod 700 "$ASKPASS_FILE"
cat > "$ASKPASS_FILE" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  *Username*) printf '%s\n' "x-access-token" ;;
  *Password*) printf '%s\n' "$GITHUB_TOKEN" ;;
  *)          printf '\n' ;;
esac
EOF
export GIT_ASKPASS="$ASKPASS_FILE"
export GIT_TERMINAL_PROMPT=0
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0="credential.helper" GIT_CONFIG_VALUE_0=""
trap 'rm -f "$ASKPASS_FILE"' EXIT INT TERM

# 3) 初始化
git config user.name  "$GIT_NAME"
git config user.email "$GIT_EMAIL"
[[ -d .git ]] || git init -b "$BRANCH"
git remote remove origin 2>/dev/null || true
git remote add origin "$REPO_URL"

# 4) 拉远端, 删掉"远端有但本地没有"的旧文件
echo "→ 拉取远端..."
git fetch origin
if git rev-parse --verify "origin/$BRANCH" >/dev/null 2>&1; then
  # 把 HEAD 指向远端历史(soft: 不动工作区), 让本地=新结构 作为提交基础
  git symbolic-ref HEAD "refs/heads/$BRANCH" 2>/dev/null || git checkout -b "$BRANCH"
  git reset --soft "origin/$BRANCH"
  echo "→ 清理远端独有旧文件..."
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    # 本地没有这个文件 → 是旧文件, 从索引删除
    if [[ ! -e "$f" ]]; then
      git rm --cached --quiet -- "$f" 2>/dev/null || true
      echo "  删除: $f"
    fi
  done < <(git ls-tree -r --name-only "origin/$BRANCH")
else
  git checkout -b "$BRANCH" 2>/dev/null || git checkout "$BRANCH"
  echo "→ 远端为空仓库, 新建 $BRANCH。"
fi

# 5) 全量提交当前目录 (提交信息可用 COMMIT_MSG 覆盖, 默认按时间生成)
COMMIT_MSG="${COMMIT_MSG:-chore: update $(date +%F\ %H:%M) $(git diff --cached --stat | tail -1)}"
git add -A
if git diff --cached --quiet; then
  echo "→ 与远端一致, 无需提交。"
else
  git commit -q -m "$COMMIT_MSG"
  echo "→ 已提交: $COMMIT_MSG"
fi

# 6) 推送
echo "→ 推送到 origin/$BRANCH ..."
git push -u origin "$BRANCH"

echo ""
echo "✅ 完成! $REPO_HTTPS ($BRANCH)"
echo "   下一步: https://render.com 连接该仓库部署。"
