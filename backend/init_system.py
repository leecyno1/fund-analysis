#!/usr/bin/env python3
"""
系统初始化与数据同步工具 (Tushare 版)

前置条件:
    pip install -r requirements.txt
    # 确保 PostgreSQL 运行中
    # 设置环境变量 TUSHARE_TOKEN (已在 .env 中配置)

用法:
    python init_system.py --check           # 前置条件检查
    python init_system.py --init-db        # 初始化数据库表
    python init_system.py --sync-funds     # 同步基金数据 (默认 200 个)
    python init_system.py --sync-managers  # 同步基金经理数据
    python init_system.py --warm-cache     # 预热 Redis 缓存
    python init_system.py --full           # 完整初始化（推荐）
    python init_system.py --status          # 检查系统状态
"""
import sys
import os
import argparse
import logging
from pathlib import Path

# 加载 .env
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_file)

# 基础路径
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("init")


# ==================== 前置条件检查 ====================

def check_prerequisites() -> bool:
    """检查前置条件"""
    logger.info("=== 前置条件检查 ===")
    issues = []
    warnings = []

    # 1. Python 版本
    py_req = (3, 10)
    if sys.version_info < py_req:
        issues.append(f"Python 版本过低: {sys.version_info.major}.{sys.version_info.minor} (需要 3.10+)")
    else:
        logger.info(f"  ✓ Python {sys.version_info.major}.{sys.version_info.minor}")

    # 2. 依赖包
    required_packages = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("tushare", "tushare"),
        ("sqlalchemy", "sqlalchemy"),
        ("psycopg2", "psycopg2"),
        ("anthropic", "anthropic"),
    ]
    for display_name, package in required_packages:
        try:
            __import__(package)
            logger.info(f"  ✓ {display_name}")
        except ImportError:
            issues.append(f"缺少依赖: {display_name} (pip install {package})")

    # 3. 可选依赖
    optional_packages = [
        ("redis", "redis"),
        ("httpx", "httpx"),
    ]
    for display_name, package in optional_packages:
        try:
            __import__(package)
            logger.info(f"  ✓ {display_name} (可选)")
        except ImportError:
            warnings.append(f"缺少可选依赖: {display_name} (pip install {package})")

    # 4. Tushare Token
    token = os.environ.get("TUSHARE_TOKEN")
    if token:
        logger.info("  ✓ Tushare Token: 已配置")
        # 验证 token 有效性
        try:
            import tushare as ts
            ts.set_token(token)
            pro = ts.pro_api(token)
            # 简单测试调用
            df = pro.trade_cal(exchange="SSE", start_date="20260101", end_date="20260102")
            if df is not None and len(df) > 0:
                logger.info("  ✓ Tushare Token 验证成功 (API 调用正常)")
            else:
                warnings.append("Tushare Token 验证结果为空 (可能积分不足)")
        except Exception as e:
            warnings.append(f"Tushare Token 验证失败: {e}")
    else:
        issues.append("未设置 TUSHARE_TOKEN 环境变量 (在 .env 中设置)")

    # 5. PostgreSQL 连接
    try:
        from sqlalchemy import create_engine, text
        pg_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/fund_analysis")
        engine = create_engine(pg_url, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info(f"  ✓ PostgreSQL: {pg_url.split('@')[1] if '@' in pg_url else 'ok'}")
    except Exception as e:
        issues.append(f"PostgreSQL 不可用: {e} (确保数据库服务运行中)")

    # 6. Redis 连接 (可选)
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        import redis
        r = redis.from_url(redis_url, socket_connect_timeout=3)
        r.ping()
        info = r.info("server")
        logger.info(f"  ✓ Redis: {info.get('redis_version')} (缓存已启用)")
    except ImportError:
        warnings.append("redis-py 未安装 (pip install redis) — 将使用无缓存模式")
    except Exception as e:
        warnings.append(f"Redis 不可用: {e} — 将使用无缓存模式")

    # 7. Anthropic API Key (可选)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        logger.info("  ✓ Anthropic API Key: 已配置")
    else:
        warnings.append("未设置 ANTHROPIC_API_KEY — AI 报告生成将使用 mock 模式")

    # 输出总结
    print()
    for w in warnings:
        logger.warning(f"  ⚠ {w}")

    if issues:
        logger.error("  ✗ 前置条件检查失败:")
        for issue in issues:
            logger.error(f"    - {issue}")
        return False

    logger.info("  ✓ 所有前置条件检查通过")
    return True


# ==================== 数据库初始化 ====================

def init_database() -> bool:
    """初始化数据库表"""
    logger.info("=== 初始化数据库表 ===")
    try:
        from database import init_database as db_init
        from sqlalchemy import create_engine, text
        import os

        pg_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/fund_analysis")
        engine = create_engine(pg_url, pool_pre_ping=True, pool_size=3)

        # 测试连接
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("  ✓ PostgreSQL 连接成功")

        # 初始化表
        success = db_init()
        if success:
            logger.info("  ✓ 数据库表初始化完成 (CREATE TABLE IF NOT EXISTS)")

            # 验证表是否存在
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """))
                tables = [row[0] for row in result.fetchall()]
                logger.info(f"  ✓ 已创建表: {', '.join(tables)}")
        return success
    except Exception as e:
        logger.error(f"  ✗ 数据库初始化失败: {e}")
        return False


# ==================== 数据同步 ====================

def sync_funds(batch_size: int = 50, max_funds: int = 200) -> bool:
    """
    从 Tushare 同步基金数据到 PostgreSQL

    数据流程:
    1. 获取基金列表 (fund_basic)
    2. 逐个获取基金详情 (fund_info, nav, performance, risk)
    3. 持久化到 funds 表
    """
    logger.info(f"=== 同步基金数据 (max={max_funds}) ===")
    try:
        from services.tushare_service import TushareDataService
        from repositories import get_fund_repo

        data_svc = TushareDataService()
        fund_repo = get_fund_repo()

        if data_svc.mock_mode:
            logger.warning("  ⚠ Tushare 运行在 MOCK 模式 — 不会同步真实数据!")
            logger.warning("  ⚠ 请检查 TUSHARE_TOKEN 是否正确配置")

        total_synced = 0
        total_failed = 0
        page = 1

        while total_synced < max_funds:
            result = data_svc.get_fund_list(page=page, page_size=batch_size)
            codes = result.get("list", [])

            if not codes:
                logger.info(f"  基金列表为空 (page={page}), 停止同步")
                break

            for code in codes:
                if total_synced >= max_funds:
                    break

                try:
                    # 获取基金完整数据
                    info = data_svc.get_fund_info(code)
                    perf = data_svc.get_fund_performance(code)
                    risk = data_svc.get_fund_risk_metrics(code)

                    # 持久化
                    fund_repo.upsert_fund(code, {
                        "name": info.get("name", code),
                        "type": info.get("type", ""),
                        "nav": info.get("nav"),
                        "nav_date": info.get("nav_date"),
                        "total_asset": info.get("total_asset"),
                        "establishment_date": info.get("establishment_date"),
                        "management_company": info.get("management_company", ""),
                        "performance_data": perf,
                        "risk_metrics": risk,
                        "raw_data": {"info": info, "perf": perf, "risk": risk},
                    })
                    total_synced += 1

                    if total_synced % 20 == 0:
                        logger.info(f"  进度: {total_synced}/{max_funds} 个基金已同步")

                except Exception as e:
                    total_failed += 1
                    logger.warning(f"  同步基金 {code} 失败: {e}")

            if len(codes) < batch_size:
                break
            page += 1

        logger.info(f"  ✓ 同步完成: {total_synced} 成功, {total_failed} 失败")
        return total_synced > 0
    except Exception as e:
        logger.error(f"  ✗ 基金数据同步失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def sync_managers(max_managers: int = 50) -> bool:
    """
    从 Tushare 同步基金经理数据

    数据流程:
    1. 从已同步的基金中提取基金经理信息
    2. 从 Tushare 获取基金经理详情
    3. 持久化到 managers 表
    """
    logger.info(f"=== 同步基金经理数据 (max={max_managers}) ===")
    try:
        from services.tushare_service import TushareDataService
        from repositories import get_fund_repo, get_manager_repo
        import pandas as pd

        data_svc = TushareDataService()
        fund_repo = get_fund_repo()
        manager_repo = get_manager_repo()

        if data_svc.mock_mode:
            logger.warning("  ⚠ Tushare 运行在 MOCK 模式")
            return False

        # 从数据库中已同步的基金中提取基金经理
        # Tushare 的 fund_basic 有 management (基金经理) 字段
        # 但更准确的方式是通过持仓表 fund_holdings 关联

        # 方式1: 直接从 Tushare 获取所有基金经理基本信息
        try:
            df_managers = data_svc.pro.fund_manager()
            if df_managers is not None and len(df_managers) > 0:
                logger.info(f"  发现 {len(df_managers)} 个基金经理记录")

                # 取前 max_managers 个
                df_sample = df_managers.head(max_managers)
                total_synced = 0

                for _, row in df_sample.iterrows():
                    try:
                        manager_id = str(row.get("manager_id", ""))
                        name = row.get("name", "")
                        company = row.get("company", "")
                        gender = row.get("gender", "")
                        birth_year = row.get("birth_year", 0)
                        education = row.get("edu", "")
                        appointment_date = str(row.get("appointment_date", ""))

                        manager_repo.upsert_manager(manager_id, {
                            "name": name,
                            "company": company,
                            "gender": gender,
                            "birth_year": birth_year,
                            "education": education,
                            "appointment_date": appointment_date,
                            "raw_data": dict(row),
                        })
                        total_synced += 1

                        if total_synced % 20 == 0:
                            logger.info(f"  进度: {total_synced}/{max_managers} 个经理已同步")
                    except Exception as e:
                        logger.warning(f"  同步经理 {row.get('manager_id')} 失败: {e}")

                logger.info(f"  ✓ 同步完成: {total_synced} 个基金经理")
                return total_synced > 0
        except Exception as e:
            logger.warning(f"  fund_manager 接口不可用: {e}")

        # 方式2: 从基金列表提取基金经理 (备选方案)
        logger.info("  使用备选方案: 从基金信息提取基金经理")
        try:
            # 获取所有基金的基金经理
            df_funds = data_svc.pro.fund_basic(status="L", fields="ts_code,name,management")
            if df_funds is None or len(df_funds) == 0:
                logger.warning("  无法获取基金列表")
                return False

            # 提取唯一的基金经理
            managers = {}
            for _, row in df_funds.iterrows():
                mgr = row.get("management", "")
                if mgr and mgr not in managers:
                    managers[mgr] = {
                        "name": mgr,
                        "company": "",
                        "raw_data": {},
                    }
                if len(managers) >= max_managers:
                    break

            total_synced = 0
            for name, data in list(managers.items())[:max_managers]:
                # 使用姓名的 hash 作为 ID
                import hashlib
                manager_id = hashlib.md5(name.encode()).hexdigest()[:12].upper()

                try:
                    manager_repo.upsert_manager(manager_id, {
                        "name": name,
                        "company": data.get("company", ""),
                        "raw_data": data.get("raw_data", {}),
                    })
                    total_synced += 1
                except Exception as e:
                    logger.warning(f"  同步经理 {name} 失败: {e}")

            logger.info(f"  ✓ 备选方案同步完成: {total_synced} 个基金经理")
            return total_synced > 0
        except Exception as e:
            logger.warning(f"  备选方案失败: {e}")
            return False

    except Exception as e:
        logger.error(f"  ✗ 基金经理数据同步失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def warm_cache(top_n: int = 100) -> bool:
    """预热 Redis 缓存"""
    logger.info(f"=== 预热缓存 (top={top_n}) ===")
    try:
        from services.cache_service import get_cache_service
        from services.tushare_service import TushareDataService
        from repositories import get_fund_repo

        cache = get_cache_service()
        data_svc = TushareDataService()
        fund_repo = get_fund_repo()

        if not cache.is_available():
            logger.warning("  缓存不可用，跳过缓存预热")
            return False

        # 从数据库获取 top N 基金
        try:
            db_result = fund_repo.list_funds(page=1, page_size=top_n)
            codes = [f["wind_code"] for f in db_result.get("funds", [])]
        except Exception:
            # 数据库没有数据，从 Tushare 获取
            result = data_svc.get_fund_list(page=1, page_size=top_n)
            codes = result.get("list", [])[:top_n]

        if not codes:
            logger.warning("  没有基金数据可预热")
            return False

        cached = 0
        for code in codes:
            try:
                perf = data_svc.get_fund_performance(code)
                risk = data_svc.get_fund_risk_metrics(code)
                info = data_svc.get_fund_info(code)

                cache.set_fund_performance(code, perf)
                cache.set_fund_risk(code, risk)
                cache.set_fund_info(code, info)

                cached += 1
                if cached % 20 == 0:
                    logger.info(f"  进度: {cached}/{len(codes)}")
            except Exception:
                pass

        logger.info(f"  ✓ 预热完成: {cached}/{len(codes)} 个基金")
        return True
    except Exception as e:
        logger.error(f"  ✗ 缓存预热失败: {e}")
        return False


# ==================== 系统状态检查 ====================

def check_status() -> bool:
    """检查系统状态"""
    logger.info("=== 系统状态检查 ===")

    all_ok = True

    # Backend API 健康检查
    try:
        import httpx
        r = httpx.get("http://127.0.0.1:8005/api/health", timeout=5)
        if r.status_code == 200:
            data = r.json()
            ds = data.get("data_source", "unknown")
            mock = data.get("mock_mode", None)
            logger.info(f"  ✓ Backend API: ok | 数据源: {ds} | Mock: {mock}")
        else:
            logger.error(f"  ✗ Backend API: HTTP {r.status_code}")
            all_ok = False
    except ImportError:
        logger.warning("  ⚠ httpx 未安装，跳过 Backend API 检查")
    except Exception as e:
        logger.error(f"  ✗ Backend API 不可用: {e}")
        all_ok = False

    # Frontend 健康检查
    try:
        import httpx
        r = httpx.get("http://localhost:3000", timeout=5)
        if r.status_code in (200, 304, 307, 308):  # 307/308 是重定向，对前端是正常的
            logger.info("  ✓ Frontend: 运行正常")
        else:
            logger.warning(f"  ⚠ Frontend: HTTP {r.status_code}")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"  ⚠ Frontend 不可用: {e} (前端可能未启动)")

    # PostgreSQL 表统计
    try:
        from sqlalchemy import create_engine, text
        import os
        pg_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/fund_analysis")
        engine = create_engine(pg_url, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    (SELECT COUNT(*) FROM funds) as fund_count,
                    (SELECT COUNT(*) FROM managers) as manager_count,
                    (SELECT COUNT(*) FROM fund_nav) as nav_count,
                    (SELECT COUNT(*) FROM scores) as score_count
            """))
            row = result.fetchone()
            logger.info(f"  ✓ PostgreSQL: {row[0]} 基金, {row[1]} 经理, {row[2]} 净值记录, {row[3]} 评分")
    except Exception as e:
        logger.warning(f"  ⚠ PostgreSQL 统计失败: {e}")

    # Redis 缓存统计
    try:
        import redis
        from services.cache_service import get_cache_service
        cache = get_cache_service()
        stats = cache.get_stats()
        mode = stats.get("mode", "unknown")
        hits = stats.get("hits", 0)
        misses = stats.get("misses", 0)
        hit_rate = stats.get("hit_rate", 0)
        logger.info(f"  ✓ Redis 缓存: {mode} | 命中 {hits} | 未命中 {misses} | 命中率 {hit_rate}%")
    except Exception as e:
        logger.warning(f"  ⚠ Redis: {e}")

    print()
    if all_ok:
        logger.info("  ✓ 系统状态正常")
    else:
        logger.warning("  ⚠ 部分组件不可用")

    return all_ok


# ==================== 主入口 ====================

def main():
    parser = argparse.ArgumentParser(
        description="基金筛选系统初始化工具 (Tushare 版)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python init_system.py --check              # 检查前置条件
  python init_system.py --full               # 完整初始化 (推荐首次运行)
  python init_system.py --sync-funds --max-funds 500  # 同步 500 个基金
  python init_system.py --status             # 查看系统状态
        """
    )
    parser.add_argument("--check", action="store_true", help="前置条件检查")
    parser.add_argument("--init-db", action="store_true", help="初始化数据库表")
    parser.add_argument("--sync-funds", action="store_true", help="同步基金数据")
    parser.add_argument("--sync-managers", action="store_true", help="同步基金经理数据")
    parser.add_argument("--warm-cache", action="store_true", help="预热缓存")
    parser.add_argument("--status", action="store_true", help="检查系统状态")
    parser.add_argument("--full", action="store_true", help="完整初始化（所有步骤）")
    parser.add_argument("--batch-size", type=int, default=50, help="批量大小 (默认 50)")
    parser.add_argument("--max-funds", type=int, default=200, help="最大同步基金数 (默认 200)")
    args = parser.parse_args()

    # 无参数时显示帮助
    if not any([args.check, args.init_db, args.sync_funds, args.sync_managers,
                 args.warm_cache, args.status, args.full]):
        parser.print_help()
        return

    print("=" * 50)
    print("  基金筛选分析系统 - 初始化工具")
    print("=" * 50)
    print()

    # 先检查前置条件
    if args.full or args.check:
        check_prerequisites()
        print()

    if args.full:
        init_database()
        print()

    if args.full or args.init_db:
        # --full 已经包含 --init-db，这里防止重复执行
        pass

    if args.full or args.sync_funds:
        if args.init_db or args.full:
            pass  # 已执行
        else:
            init_database()
        sync_funds(batch_size=args.batch_size, max_funds=args.max_funds)
        print()

    if args.full or args.sync_managers:
        sync_managers()
        print()

    if args.full or args.warm_cache:
        warm_cache()
        print()

    if args.full:
        logger.info("=== 完整初始化完成 ===")
        check_status()


if __name__ == "__main__":
    main()
