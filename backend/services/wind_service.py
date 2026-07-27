"""
基金数据服务 - 通过 Wind Py 接口获取数据
"""
import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)

# Wind Python API wrapper
try:
    import wind
    WIND_AVAILABLE = True
except ImportError:
    WIND_AVAILABLE = False
    logger.warning("Wind Python API not available. WindDataService can only run in explicit mock_mode.")


class WindDataService:
    """Wind数据服务类"""

    def __init__(self, mock_mode: bool = None):
        if mock_mode is None:
            mock_mode = not WIND_AVAILABLE
        self.mock_mode = mock_mode
        logger.info(f"WindDataService initialized (mock_mode={mock_mode})")

    def _raise_real_data_error(self, scope: str, error: Exception):
        logger.error("Wind real data error for %s: %s", scope, error)
        raise RuntimeError(f"Wind真实数据读取失败：{scope}；已阻止 mock 回退，不能用模拟数据生成基金研究证据。") from error

    # ==================== 基金基础数据 ====================

    def get_fund_info(self, wind_code: str) -> Dict[str, Any]:
        """获取基金基本信息"""
        if self.mock_mode:
            return self._mock_fund_info(wind_code)

        try:
            # 基金基本信息
            info_map = {
                "sec_name": wind.WSD(wind_code, "sec_name", "2025-04-21", "2025-04-21", "Fill=Previous")[0][0],
                "fund_fullname": wind.WSD(wind_code, "fund_fullname", "2025-04-21", "2025-04-21", "Fill=Previous")[0][0],
                "fund_type": wind.WSD(wind_code, "fund_type", "2025-04-21", "2025-04-21", "Fill=Previous")[0][0],
                "fund_manager": wind.WSD(wind_code, "fund_manager", "2025-04-21", "2025-04-21", "Fill=Previous")[0][0],
                "fund_setupdate": wind.WSD(wind_code, "fund_setupdate", "2025-04-21", "2025-04-21", "Fill=Previous")[0][0],
                "fund管理人": wind.WSD(wind_code, "fund管理人", "2025-04-21", "2025-04-21", "Fill=Previous")[0][0],
            }

            # 规模数据
            asset = wind.WSD(wind_code, "fund_totalasset", "2025-04-21", "2025-04-21", "Fill=Previous")

            return {
                "wind_code": wind_code,
                "name": info_map["sec_name"],
                "full_name": info_map.get("fund_fullname"),
                "type": info_map.get("fund_type", "混合型"),
                "manager": info_map.get("fund_manager"),
                "management_company": info_map.get("fund管理人"),
                "establishment_date": info_map.get("fund_setupdate"),
                "total_asset": asset[0][0] if asset and asset[0] else None,
            }
        except Exception as e:
            return self._raise_real_data_error(f"基金基本信息 {wind_code}", e)

    def get_fund_list(self, fund_type: Optional[str] = None, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        """获取基金列表"""
        if self.mock_mode:
            return self._mock_fund_list(fund_type, page, page_size)

        try:
            # 使用Wind基金分类
            if fund_type:
                result = wind.WIND_FUND_LIST(fund_type)
            else:
                result = wind.WIND_FUND_LIST("ALL")
            return {"total": len(result), "list": result, "page": page, "page_size": page_size}
        except Exception as e:
            return self._raise_real_data_error(f"基金列表 {fund_type or 'ALL'}", e)

    def get_fund_nav(self, wind_code: str, start_date: str, end_date: str) -> List[Dict]:
        """获取基金净值数据"""
        if self.mock_mode:
            return self._mock_nav_series(wind_code, start_date, end_date)

        try:
            data = wind.WSD(wind_code, "NAV", start_date, end_date, "Fill=Previous;period=DAILY")
            result = []
            dates = data.Times if hasattr(data, 'Times') else []
            for i, row in enumerate(data.Data[0] if data.Data else []):
                if row is not None:
                    result.append({"date": dates[i] if i < len(dates) else None, "nav": row})
            return result
        except Exception as e:
            return self._raise_real_data_error(f"基金净值 {wind_code}", e)

    # ==================== 基金经理数据 ====================

    def get_manager_info(self, manager_id: str) -> Dict[str, Any]:
        """获取基金经理个人信息"""
        if self.mock_mode:
            return self._mock_manager_info(manager_id)

        try:
            info = wind.WSD(manager_id, "fund_manager_info", "2025-04-21", "2025-04-21")
            return {
                "manager_id": manager_id,
                "name": info.get("姓名"),
                "gender": info.get("性别"),
                "education": info.get("学历"),
                "company": info.get("任职公司"),
                "experience_years": info.get("从业年限"),
            }
        except Exception as e:
            return self._raise_real_data_error(f"基金经理信息 {manager_id}", e)

    def get_manager_funds(self, manager_id: str) -> List[Dict]:
        """获取经理管理的基金列表"""
        if self.mock_mode:
            return self._mock_manager_funds(manager_id)

        try:
            funds = wind.WSD(manager_id, "fund_managed_list", "2025-04-21", "2025-04-21")
            return funds or []
        except Exception as e:
            return self._raise_real_data_error(f"基金经理任职 {manager_id}", e)

    # ==================== 业绩指标 ====================

    def get_fund_performance(self, wind_code: str) -> Dict[str, Any]:
        """获取基金业绩指标（年化收益、最大回撤、夏普比率等）"""
        if self.mock_mode:
            return self._mock_performance(wind_code)

        try:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_1y = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
            start_3y = (datetime.now() - timedelta(days=1095)).strftime("%Y-%m-%d")

            metrics = {
                "annualized_return_1y": wind.WSD(wind_code, "fund_return_ytd", start_1y, end_date),
                "annualized_return_3y": wind.WSD(wind_code, "fund_return_3y", start_3y, end_date),
                "max_drawdown": wind.WSD(wind_code, "max_drawdown", start_3y, end_date),
                "sharpe_ratio": wind.WSD(wind_code, "fund_sharpe_rr", start_3y, end_date),
                "volatility": wind.WSD(wind_code, "fund_volatility", start_3y, end_date),
                "sortino": wind.WSD(wind_code, "fund_sortino", start_3y, end_date),
            }
            return {k: v[0][0] if v and v[0] else None for k, v in metrics.items()}
        except Exception as e:
            return self._raise_real_data_error(f"基金业绩指标 {wind_code}", e)

    def get_fund_risk_metrics(self, wind_code: str) -> Dict[str, Any]:
        """获取基金风险指标"""
        if self.mock_mode:
            return self._mock_risk_metrics(wind_code)

        try:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_1y = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
            start_2y = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")

            metrics = {
                "annualized_volatility_1y": wind.WSD(wind_code, "fund_volatility_1y", start_1y, end_date),
                "annualized_volatility_2y": wind.WSD(wind_code, "fund_volatility_2y", start_2y, end_date),
                "max_drawdown_1y": wind.WSD(wind_code, "fund_maxdrawdown_1y", start_1y, end_date),
                "max_drawdown_2y": wind.WSD(wind_code, "fund_maxdrawdown_2y", start_2y, end_date),
                "var_95": wind.WSD(wind_code, "fund_var_95", start_1y, end_date),
                "beta": wind.WSD(wind_code, "beta", start_1y, end_date),
                "alpha": wind.WSD(wind_code, "alpha", start_1y, end_date),
                "tracking_error": wind.WSD(wind_code, "tracking_error", start_1y, end_date),
                "information_ratio": wind.WSD(wind_code, "fund_info_ratio", start_1y, end_date),
            }
            return {k: v[0][0] if v and v[0] else None for k, v in metrics.items()}
        except Exception as e:
            return self._raise_real_data_error(f"基金风险指标 {wind_code}", e)

    # ==================== 持仓数据 ====================

    def get_fund_holdings(self, wind_code: str, quarter: str) -> List[Dict]:
        """获取基金持仓（按季度）"""
        if self.mock_mode:
            return self._mock_holdings(wind_code, quarter)

        try:
            holdings = wind.WSD(wind_code, "fund_holding", quarter, quarter)
            return holdings or []
        except Exception as e:
            return self._raise_real_data_error(f"基金持仓 {wind_code} {quarter}", e)

    # ==================== 风格分析 ====================

    def get_fund_style(self, wind_code: str) -> Dict[str, Any]:
        """获取基金风格分析（Barra风格因子暴露）"""
        if self.mock_mode:
            return self._mock_style()

        try:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_1q = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

            factors = ["SIZE", "SIZENL", "BETA", "MOMENTUM", "RESVOL", "SRSIZE",
                       "LIQUIDITY", "BHADGE", "LEVERAGE", "STORIE"]

            style_data = {}
            for factor in factors:
                try:
                    data = wind.WSD(wind_code, f"barra_{factor.lower()}", start_1q, end_date)
                    if not data or not data[0] or data[0][0] is None:
                        raise RuntimeError(f"缺少 Barra 因子 {factor}")
                    style_data[factor] = data[0][0]
                except Exception as factor_error:
                    return self._raise_real_data_error(f"基金风格因子 {wind_code} {factor}", factor_error)

            return style_data
        except Exception as e:
            return self._raise_real_data_error(f"基金风格分析 {wind_code}", e)

    # ==================== Mock 数据生成 ====================

    def _mock_fund_info(self, wind_code: str) -> Dict[str, Any]:
        return {
            "wind_code": wind_code,
            "name": f"基金{wind_code.split('.')[0]}",
            "full_name": f"某某灵活配置混合型证券投资基金",
            "type": "混合型",
            "manager": f"张经理",
            "management_company": "某某基金管理有限公司",
            "establishment_date": "2019-01-15",
            "total_asset": 1500000000.0,
        }

    def _mock_fund_list(self, fund_type: Optional[str], page: int, page_size: int) -> Dict[str, Any]:
        funds = [
            "000001.OF", "000002.OF", "000003.OF", "000004.OF", "000005.OF",
            "000006.OF", "000007.OF", "000008.OF", "000009.OF", "000010.OF",
        ]
        if fund_type:
            funds = [f for f in funds if "混合" in fund_type]
        return {
            "total": len(funds),
            "list": funds[(page - 1) * page_size: page * page_size],
            "page": page,
            "page_size": page_size,
        }

    def _mock_nav_series(self, wind_code: str, start_date: str, end_date: str) -> List[Dict]:
        result = []
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        nav = 1.0
        while start <= end:
            nav *= (1 + (hash(f"{wind_code}{start.date()}") % 100 - 50) / 10000)
            result.append({"date": start.strftime("%Y-%m-%d"), "nav": round(nav, 4)})
            start += timedelta(days=1)
        return result

    def _mock_manager_info(self, manager_id: str) -> Dict[str, Any]:
        return {
            "manager_id": manager_id,
            "name": f"基金经理{manager_id[-4:]}",
            "gender": "男",
            "education": "硕士",
            "company": "某某基金管理有限公司",
            "experience_years": 8,
            "management_years": 5.5,
            "background": "曾任研究员、高级研究员、基金经理助理",
        }

    def _mock_manager_funds(self, manager_id: str) -> List[Dict]:
        return [
            {"wind_code": "000001.OF", "name": "某某灵活配置混合A", "type": "混合型", "since": "2020-01-01"},
            {"wind_code": "000002.OF", "name": "某某价值精选混合", "type": "混合型", "since": "2022-03-15"},
        ]

    def _mock_performance(self, wind_code: str) -> Dict[str, Any]:
        return {
            "annualized_return_1y": round((hash(wind_code + "1y") % 400 - 100) / 100, 4),
            "annualized_return_3y": round((hash(wind_code + "3y") % 500 - 150) / 100, 4),
            "max_drawdown": round((hash(wind_code + "md") % 300 - 50) / 1000, 4),
            "sharpe_ratio": round((hash(wind_code + "sh") % 200 - 50) / 100, 4),
            "volatility": round((hash(wind_code + "vol") % 250 + 50) / 1000, 4),
            "sortino": round((hash(wind_code + "so") % 250 - 50) / 100, 4),
            "calmar_ratio": round((hash(wind_code + "cal") % 150) / 100, 4),
            "win_rate_1y": round((hash(wind_code + "wr") % 40 + 50) / 100, 4),
        }

    def _mock_risk_metrics(self, wind_code: str) -> Dict[str, Any]:
        return {
            "annualized_volatility_1y": round((hash(wind_code + "v1") % 200 + 100) / 1000, 4),
            "annualized_volatility_2y": round((hash(wind_code + "v2") % 200 + 100) / 1000, 4),
            "max_drawdown_1y": round((hash(wind_code + "d1") % 300 - 50) / 1000, 4),
            "max_drawdown_2y": round((hash(wind_code + "d2") % 350 - 50) / 1000, 4),
            "var_95": round((hash(wind_code + "var") % 150) / 1000, 4),
            "beta": round((hash(wind_code + "bt") % 120 - 10) / 100, 4),
            "alpha": round((hash(wind_code + "al") % 200 - 80) / 100, 4),
            "tracking_error": round((hash(wind_code + "te") % 150 + 20) / 1000, 4),
            "information_ratio": round((hash(wind_code + "ir") % 200 - 60) / 100, 4),
        }

    def _mock_holdings(self, wind_code: str, quarter: str) -> List[Dict]:
        stocks = [
            ("600519.SH", "贵州茅台", "食品饮料"),
            ("000858.SZ", "五粮液", "食品饮料"),
            ("300750.SZ", "宁德时代", "电力设备"),
            ("601318.SH", "中国平安", "非银金融"),
            ("600036.SH", "招商银行", "银行"),
            ("002594.SZ", "比亚迪", "汽车"),
            ("600900.SH", "长江电力", "公用事业"),
            ("300059.SZ", "东方财富", "非银金融"),
            ("002415.SZ", "海康威视", "电子"),
            ("601012.SH", "隆基绿能", "电力设备"),
        ]
        return [
            {"stock_code": code, "stock_name": name, "industry": ind,
             "weight": round((hash(f"{wind_code}{code}{quarter}") % 500 + 100) / 10000, 4)}
            for code, name, ind in stocks[:5 + (hash(quarter) % 5)]
        ]

    def _mock_style(self) -> Dict[str, float]:
        return {
            "SIZE": 0.2, "SIZENL": -0.1, "BETA": 0.8, "MOMENTUM": 0.3,
            "RESVOL": -0.2, "SRSIZE": 0.1, "LIQUIDITY": 0.4,
            "BHADGE": -0.3, "LEVERAGE": -0.1, "STORIE": 0.5,
        }
