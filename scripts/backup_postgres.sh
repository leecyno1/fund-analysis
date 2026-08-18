#!/usr/bin/env bash
# scripts/backup_postgres.sh
#
# 每日 PostgreSQL 备份：pg_dump 自定义压缩格式，保留最近 14 份。
# 由 scheduled_update.sh 的 daily bucket 调用，也可单独执行。
#
# 用法：
#   bash scripts/backup_postgres.sh            # 执行备份
#   bash scripts/backup_postgres.sh --prune    # 只清理过期备份，不执行新备份

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups/postgres}"
RETENTION_COUNT="${RETENTION_COUNT:-14}"
DB_NAME="${POSTGRES_DB:-fund_analysis}"

# 优先使用与服务器大版本匹配的 pg_dump；否则回退 PATH 中的 pg_dump
PG_DUMP="${PG_DUMP:-}"
if [[ -z "$PG_DUMP" ]]; then
  SERVER_VERSION="$(psql -d "$DB_NAME" -tAc 'SHOW server_version' 2>/dev/null | cut -d. -f1 || true)"
  for candidate in "/opt/homebrew/opt/postgresql@${SERVER_VERSION}/bin/pg_dump" "/usr/local/opt/postgresql@${SERVER_VERSION}/bin/pg_dump"; do
    if [[ -n "$SERVER_VERSION" && -x "$candidate" ]]; then
      PG_DUMP="$candidate"
      break
    fi
  done
  [[ -z "$PG_DUMP" ]] && PG_DUMP="$(command -v pg_dump)"
fi

mkdir -p "$BACKUP_DIR"

if [[ "${1:-}" != "--prune" ]]; then
  TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
  TARGET="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.dump"

  # -Fc 自定义压缩格式；-d 显式指定库名；连接串走本地 socket，无需密码
  if "$PG_DUMP" -Fc -d "$DB_NAME" -f "$TARGET"; then
    SIZE_BYTES="$(stat -f %z "$TARGET" 2>/dev/null || stat -c %s "$TARGET")"
    echo "backup OK: $TARGET ($(( SIZE_BYTES / 1024 / 1024 )) MB)"
  else
    echo "backup FAILED: pg_dump exit $?" >&2
    rm -f "$TARGET"
    exit 1
  fi
fi

# 保留最近 RETENTION_COUNT 份，删除更早的
ls -1t "$BACKUP_DIR/${DB_NAME}"_*.dump 2>/dev/null | tail -n +"$(( RETENTION_COUNT + 1 ))" | while read -r old; do
  rm -f "$old"
  echo "pruned old backup: $old"
done
