from WindPy import w
import pandas as pd
from typing import List, Dict, Optional, Any
from datetime import datetime

class WindClient:
    """Wind API 客户端封装"""

    def __init__(self):
        """初始化 Wind 连接"""
        self.connected = False
        try:
            w.start()
            self.connected = True
            print("Wind API 连接成功")
        except Exception as e:
            print(f"Wind API 连接失败: {e}")

    def __del__(self):
        """关闭 Wind 连接"""
        if self.connected:
            w.stop()

    def get_fund_info(self, fund_code: str) -> Dict[str, Any]:
        """
        获取基金基本信息

        Args:
            fund_code: 基金代码

        Returns:
            基金信息字典
        """
        if not self.connected:
            raise Exception("Wind API 未连接")

        fields = "fund_name,fund_setupdate,fund_maturitydate,fund_mgrcomp,fund_fundmanager,fund_investtype"
        data = w.wss(fund_code, fields)

        if data.ErrorCode != 0:
            raise Exception(f"获取基金信息失败: {data.Data}")

        return self._parse_wss_data(data, fund_code)

    def get_fund_nav(self, fund_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取基金净值数据

        Args:
            fund_code: 基金代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            净值数据 DataFrame
        """
        if not self.connected:
            raise Exception("Wind API 未连接")

        data = w.wsd(fund_code, "nav,NAV_adj", start_date, end_date)

        if data.ErrorCode != 0:
            raise Exception(f"获取净值数据失败: {data.Data}")

        return self._parse_wsd_data(data)

    def get_fund_performance(self, fund_code: str) -> Dict[str, Any]:
        """
        获取基金业绩指标

        Args:
            fund_code: 基金代码

        Returns:
            业绩指标字典
        """
        if not self.connected:
            raise Exception("Wind API 未连接")

        # 收益率指标
        fields = "return_1m,return_3m,return_6m,return_1y,return_3y,return_5y"
        fields += ",sharpe_1y,sharpe_3y,maxdd_1y,volatility_1y"

        data = w.wss(fund_code, fields)

        if data.ErrorCode != 0:
            raise Exception(f"获取业绩数据失败: {data.Data}")

        return self._parse_wss_data(data, fund_code)

    def get_manager_info(self, manager_name: str) -> Dict[str, Any]:
        """
        获取基金经理信息

        Args:
            manager_name: 基金经理姓名

        Returns:
            基金经理信息字典
        """
        # TODO: 实现基金经理信息查询
        # Wind API 的基金经理查询相对复杂，需要通过基金反查
        return {
            "name": manager_name,
            "company": None,
            "education": None,
            "work_years": None,
            "funds": []
        }

    def _parse_wss_data(self, data, code: str) -> Dict[str, Any]:
        """解析 WSS 数据"""
        result = {"wind_code": code}

        if data.Fields and data.Data:
            for i, field in enumerate(data.Fields):
                value = data.Data[i][0] if data.Data[i] else None
                result[field.lower()] = value

        return result

    def _parse_wsd_data(self, data) -> pd.DataFrame:
        """解析 WSD 数据为 DataFrame"""
        if not data.Times or not data.Data:
            return pd.DataFrame()

        df = pd.DataFrame(
            data.Data,
            index=data.Fields,
            columns=data.Times
        ).T

        return df

# 全局 Wind 客户端实例
wind_client = None

def get_wind_client() -> WindClient:
    """获取 Wind 客户端单例"""
    global wind_client
    if wind_client is None:
        wind_client = WindClient()
    return wind_client
