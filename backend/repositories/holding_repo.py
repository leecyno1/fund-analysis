"""
基金持仓 Repository
"""
import os
import math
from typing import List, Dict, Any
import logging

try:
    from backend.database import get_database_url
except ModuleNotFoundError:
    from database import get_database_url

logger = logging.getLogger(__name__)

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from sqlalchemy import create_engine
        pg_url = get_database_url()
        _engine = create_engine(pg_url, pool_pre_ping=True, pool_size=20, max_overflow=30, pool_recycle=3600)
    return _engine


def _clean(v):
    """清理 NaN/Inf"""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


class HoldingRepo:
    """基金持仓数据访问层"""

    def __init__(self):
        self._engine = None

    @property
    def engine(self):
        if self._engine is None:
            self._engine = _get_engine()
        return self._engine

    def upsert_holdings(self, wind_code: str, quarter: str, holdings: List[Dict[str, Any]]) -> bool:
        """Upsert 基金持仓"""
        try:
            from sqlalchemy import text

            delete_sql = "DELETE FROM holdings WHERE wind_code = :wind_code AND quarter = :quarter"
            with self.engine.connect() as conn:
                conn.execute(text(delete_sql), {"wind_code": wind_code, "quarter": quarter})

                insert_sql = """
                INSERT INTO holdings (
                    wind_code, quarter, stock_code, stock_name, industry, sub_industry,
                    weight, shares, market_cap, pe_ratio, pb_ratio, roe,
                    revenue_growth, dividend_yield, market_cap_value
                ) VALUES (
                    :wind_code, :quarter, :stock_code, :stock_name, :industry, :sub_industry,
                    :weight, :shares, :market_cap, :pe_ratio, :pb_ratio, :roe,
                    :revenue_growth, :dividend_yield, :market_cap_value
                )
                ON CONFLICT (wind_code, quarter, stock_code) DO UPDATE SET
                    stock_name = EXCLUDED.stock_name,
                    industry = EXCLUDED.industry,
                    weight = EXCLUDED.weight,
                    shares = EXCLUDED.shares
                """

                for h in holdings:
                    params = {
                        "wind_code": wind_code,
                        "quarter": quarter,
                        "stock_code": h.get("stock_code", ""),
                        "stock_name": h.get("stock_name", ""),
                        "industry": h.get("industry", ""),
                        "sub_industry": h.get("sub_industry"),
                        "weight": _clean(h.get("weight")),
                        "shares": h.get("shares"),
                        "market_cap": h.get("market_cap"),
                        "pe_ratio": _clean(h.get("pe_ratio")),
                        "pb_ratio": _clean(h.get("pb_ratio")),
                        "roe": _clean(h.get("roe")),
                        "revenue_growth": _clean(h.get("revenue_growth")),
                        "dividend_yield": _clean(h.get("dividend_yield")),
                        "market_cap_value": _clean(h.get("market_cap_value")),
                    }
                    try:
                        conn.execute(text(insert_sql), params)
                    except Exception as e:
                        logger.warning(f"Insert holding error: {e}")
                        continue
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"upsert_holdings error for {wind_code} {quarter}: {e}")
            return False

    def get_holdings(self, wind_code: str, quarter: str) -> List[Dict[str, Any]]:
        """获取基金持仓"""
        try:
            from sqlalchemy import text
            sql = """
                SELECT * FROM holdings
                WHERE wind_code = :wind_code AND quarter = :quarter
                ORDER BY weight DESC
            """
            with self.engine.connect() as conn:
                result = conn.execute(text(sql), {"wind_code": wind_code, "quarter": quarter})
                return [dict(r._mapping) for r in result.fetchall()]
        except Exception as e:
            logger.error(f"get_holdings error: {e}")
            return []

    def get_holdings_history(self, wind_code: str) -> List[Dict[str, Any]]:
        """获取基金历史持仓"""
        try:
            from sqlalchemy import text
            sql = """
                SELECT * FROM holdings
                WHERE wind_code = :wind_code
                ORDER BY quarter DESC
            """
            with self.engine.connect() as conn:
                result = conn.execute(text(sql), {"wind_code": wind_code})
                return [dict(r._mapping) for r in result.fetchall()]
        except Exception as e:
            logger.error(f"get_holdings_history error: {e}")
            return []
