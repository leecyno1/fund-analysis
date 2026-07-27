/**
 * Wind数据连接器 - 连接Wind Py数据接口
 * 支持基金、经理、持仓、净值等数据拉取
 */

import Python from "node-python-bridge";

let python: Awaited<ReturnType<typeof Python.create>> | null = null;

export async function getPython(): Promise<Awaited<ReturnType<typeof Python.create>>> {
  if (!python) {
    python = await Python.create("/opt/homebrew/bin/python3");
    // 初始化Wind模块
    await python.exec(`
import sys
sys.path.insert(0, '/opt/homebrew/lib/python3.11/site-packages')
try:
    import WindPy as w
    w.start()
    print("Wind connected")
except ImportError:
    print("Wind not installed")
except Exception as e:
    print(f"Wind error: {e}")
    `);
  }
  return python;
}

/** 拉取基金基本信息 */
export async function getFundInfo(windCode: string) {
  const py = await getPython();
  const result = await py.exec(`
import WindPy as w
data = w.wsd("${windCode}",
    "sec_name,fund_type,nav,nav_date,total_asset,establish_date,benchmark",
    "2024-01-01", "2024-04-20", "period=D")
print(data)
  `);
  return result;
}

/** 批量拉取基金列表 */
export async function getFundList(fundType?: string) {
  const py = await getPython();
  const result = await py.exec(`
import WindPy as w
df, err = w.wset("sectorconstituent", f"date=2024-04-20;sectorid=0001")
print(df.to_json() if df is not None else err)
  `);
  return result;
}

/** 拉取基金经理列表 */
export async function getManagerList() {
  const py = await getPython();
  const result = await py.exec(`
import WindPy as w
df, err = w.wset("fundmanagerinfo", "date=2024-04-20")
print(df.to_json() if df is not None else err)
  `);
  return result;
}

/** 拉取基金净值序列 */
export async function getFundNAV(windCode: string, start: string, end: string) {
  const py = await getPython();
  const result = await py.exec(`
import WindPy as w
data = w.wsd("${windCode}", "NAV,NAV_adj,daily_return",
    "${start}", "${end}", "period=D;priceType=1")
print(data.to_json() if data is not None else str(data))
  `);
  return result;
}

/** 拉取持仓数据（十大重仓股） */
export async function getFundHoldings(windCode: string, period: string) {
  const py = await getPython();
  const result = await py.exec(`
import WindPy as w
# period: 季度末日期，如 "2024-03-31"
df, err = w.wst("${windCode}", "fund_holdstocks_ex", "${period}")
print(df.to_json() if df is not None else err)
  `);
  return result;
}

/** 拉取基金经理持仓偏好 */
export async function getManagerStyle(managerWindCode: string) {
  const py = await getPython();
  const result = await py.exec(`
import WindPy as w
df, err = w.wss("${managerWindCode}",
    "fund_manager_style_style,fund_manager_style_industry,fund_manager_style_cap")
print(df.to_json() if df is not None else err)
  `);
  return result;
}

/** 拉取基金业绩归因数据 */
export async function getFundAttribution(windCode: string, benchmarkId: string, start: string, end: string) {
  const py = await getPython();
  const result = await py.exec(`
import WindPy as w
# 基金归因接口（需Wind权限）
data, err = w.wss("${windCode}",
    "fund_brinson_allocation,fund_brinson_selection,fund_brinson_interaction",
    f"startDate=${start};endDate=${end};benchmark={benchmarkId}")
print(data.to_json() if data is not None else err)
  `);
  return result;
}

/** 拉取基金因子暴露度（Barra风格） */
export async function getFundFactorExposure(windCode: string, date: string) {
  const py = await getPython();
  const result = await py.exec(`
import WindPy as w
# Barra风格因子暴露
data, err = w.wss("${windCode}",
    "style_mkt,style_size,style_value,style_growth,style_momentum,style_quality,style_volatility",
    f"tradeDate={date}")
print(data.to_json() if data is not None else err)
  `);
  return result;
}

/** 拉取基金财务指标（估值） */
export async function getFundMetrics(windCode: string) {
  const py = await getPython();
  const result = await py.exec(`
import WindPy as w
data, err = w.wss("${windCode}",
    "fund_avgNav_y1,fund_avgNav_y3,fund_maxDrawdown_y1,fund_volatility_y1,fund_sharpe_y1",
    "period=2024Q1")
print(data.to_json() if data is not None else err)
  `);
  return result;
}