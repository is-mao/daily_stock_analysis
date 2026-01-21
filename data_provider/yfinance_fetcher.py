# -*- coding: utf-8 -*-
"""
===================================
YfinanceFetcher - 兜底数据源 (Priority 4)
===================================

数据来源：Yahoo Finance（通过 yfinance 库）
特点：国际数据源、可能有延迟或缺失
定位：当所有国内数据源都失败时的最后保障

关键策略：
1. 自动将 A 股代码转换为 yfinance 格式（.SS / .SZ）
2. 处理 Yahoo Finance 的数据格式差异
3. 失败后指数退避重试
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any

import pandas as pd
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .base import BaseFetcher, DataFetchError, STANDARD_COLUMNS

logger = logging.getLogger(__name__)


class YfinanceFetcher(BaseFetcher):
    """
    Yahoo Finance 数据源实现

    优先级：4（最低，作为兜底）
    数据来源：Yahoo Finance

    关键策略：
    - 自动转换股票代码格式
    - 处理时区和数据格式差异
    - 失败后指数退避重试

    注意事项：
    - A 股数据可能有延迟
    - 某些股票可能无数据
    - 数据精度可能与国内源略有差异
    """

    name = "YfinanceFetcher"
    priority = 4

    def __init__(self):
        """初始化 YfinanceFetcher"""
        pass

    def _convert_stock_code(self, stock_code: str) -> str:
        """
        转换股票代码为 Yahoo Finance 格式

        Yahoo Finance A 股代码格式：
        - 沪市：600519.SS (Shanghai Stock Exchange)
        - 深市：000001.SZ (Shenzhen Stock Exchange)

        Args:
            stock_code: 原始代码，如 '600519', '000001'

        Returns:
            Yahoo Finance 格式代码，如 '600519.SS', '000001.SZ'
        """
        code = stock_code.strip()

        # 已经包含后缀的情况
        if '.SS' in code.upper() or '.SZ' in code.upper():
            return code.upper()

        # 去除可能的后缀
        code = code.replace('.SH', '').replace('.sh', '')

        # 根据代码前缀判断市场
        if code.startswith(('600', '601', '603', '688')):
            return f"{code}.SS"
        elif code.startswith(('000', '002', '300')):
            return f"{code}.SZ"
        else:
            logger.warning(f"无法确定股票 {code} 的市场，默认使用深市")
            return f"{code}.SZ"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        从 Yahoo Finance 获取原始数据

        使用 yfinance.download() 获取历史数据

        流程：
        1. 转换股票代码格式
        2. 调用 yfinance API
        3. 处理返回数据
        """
        import yfinance as yf

        # 转换代码格式
        yf_code = self._convert_stock_code(stock_code)

        logger.debug(f"调用 yfinance.download({yf_code}, {start_date}, {end_date})")

        try:
            # 使用 yfinance 下载数据
            df = yf.download(
                tickers=yf_code,
                start=start_date,
                end=end_date,
                progress=False,  # 禁止进度条
                auto_adjust=True,  # 自动调整价格（复权）
            )

            if df.empty:
                raise DataFetchError(f"Yahoo Finance 未查询到 {stock_code} 的数据")

            return df

        except Exception as e:
            if isinstance(e, DataFetchError):
                raise
            raise DataFetchError(f"Yahoo Finance 获取数据失败: {e}") from e

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        标准化 Yahoo Finance 数据

        yfinance 返回的列名：
        Open, High, Low, Close, Volume（索引是日期）

        需要映射到标准列名：
        date, open, high, low, close, volume, amount, pct_chg
        """
        df = df.copy()

        # 重置索引，将日期从索引变为列
        df = df.reset_index()

        # 列名映射（yfinance 使用首字母大写）
        column_mapping = {
            'Date': 'date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume',
        }

        df = df.rename(columns=column_mapping)

        # 计算涨跌幅（因为 yfinance 不直接提供）
        if 'close' in df.columns:
            df['pct_chg'] = df['close'].pct_change() * 100
            df['pct_chg'] = df['pct_chg'].fillna(0).round(2)

        # 计算成交额（yfinance 不提供，使用估算值）
        # 成交额 ≈ 成交量 * 平均价格
        if 'volume' in df.columns and 'close' in df.columns:
            df['amount'] = df['volume'] * df['close']
        else:
            df['amount'] = 0

        # 添加股票代码列
        df['code'] = stock_code

        # 只保留需要的列
        keep_cols = ['code'] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]

        return df

    def get_realtime_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        获取实时行情数据（Yahoo Finance）

        使用 yfinance.Ticker.info 获取实时数据

        Args:
            stock_code: 股票代码

        Returns:
            实时行情数据字典，获取失败返回 None
        """
        try:
            import yfinance as yf

            # 转换代码格式
            yf_code = self._convert_stock_code(stock_code)

            logger.info(f"[API调用] Yahoo Finance 获取 {stock_code} 实时行情...")

            # 创建 Ticker 对象
            ticker = yf.Ticker(yf_code)

            # 获取股票信息
            info = ticker.info

            if not info or 'regularMarketPrice' not in info:
                logger.warning(f"[API返回] Yahoo Finance 未找到 {stock_code} 的实时数据")
                return None

            # 构造实时行情数据
            quote_data = {
                'code': stock_code,
                'name': info.get('longName', info.get('shortName', f'股票{stock_code}')),
                'price': float(info.get('regularMarketPrice', 0)),
                'change_pct': float(info.get('regularMarketChangePercent', 0)) * 100,  # 转换为百分比
                'change_amount': float(info.get('regularMarketChange', 0)),
                'volume_ratio': 0.0,  # Yahoo Finance不直接提供量比
                'turnover_rate': 0.0,  # Yahoo Finance不直接提供换手率
                'amplitude': 0.0,  # 可以计算
                'pe_ratio': float(info.get('trailingPE', 0)),
                'pb_ratio': float(info.get('priceToBook', 0)),
                'total_mv': float(info.get('marketCap', 0)),
                'circulation_mv': float(info.get('floatShares', 0)) * float(info.get('regularMarketPrice', 0)),
            }

            # 计算振幅
            day_high = float(info.get('regularMarketDayHigh', 0))
            day_low = float(info.get('regularMarketDayLow', 0))
            prev_close = float(info.get('regularMarketPreviousClose', 0))
            if prev_close > 0:
                quote_data['amplitude'] = (day_high - day_low) / prev_close * 100

            logger.info(
                f"[实时行情] {stock_code} {quote_data['name']}: 价格={quote_data['price']}, 涨跌幅={quote_data['change_pct']:.2f}%"
            )
            return quote_data

        except Exception as e:
            logger.error(f"[API错误] 获取 {stock_code} Yahoo Finance实时行情失败: {e}")
            return None

    def get_fundamental_data(self, stock_code: str) -> Dict[str, Any]:
        """
        获取基本面数据（Yahoo Finance）

        使用 yfinance.Ticker.info 获取基本面数据

        Args:
            stock_code: 股票代码

        Returns:
            包含基本面指标的字典
        """
        try:
            import yfinance as yf

            # 转换代码格式
            yf_code = self._convert_stock_code(stock_code)

            logger.info(f"[API调用] Yahoo Finance 获取 {stock_code} 基本面数据...")

            # 创建 Ticker 对象
            ticker = yf.Ticker(yf_code)

            # 获取股票信息
            info = ticker.info

            if not info:
                logger.warning(f"[API返回] Yahoo Finance 未找到 {stock_code} 的基本面数据")
                return {}

            # 构建基本面数据字典
            fundamental_data = {
                'pe_ratio': float(info.get('trailingPE', 0)),
                'pb_ratio': float(info.get('priceToBook', 0)),
                'total_mv': float(info.get('marketCap', 0)),
                'circ_mv': float(info.get('floatShares', 0)) * float(info.get('regularMarketPrice', 0)),
                'roe': float(info.get('returnOnEquity', 0)) * 100,  # 转换为百分比
                'revenue_growth': float(info.get('revenueGrowth', 0)) * 100,  # 转换为百分比
            }

            return fundamental_data

        except Exception as e:
            logger.error(f"[API错误] 获取股票 {stock_code} Yahoo Finance基本面数据失败: {e}")
            return {}

    def get_enhanced_data(self, stock_code: str, days: int = 60) -> Dict[str, Any]:
        """
        获取增强数据（历史K线 + 实时行情 + 基本面数据）

        Args:
            stock_code: 股票代码
            days: 历史数据天数

        Returns:
            包含所有数据的字典
        """
        result = {
            'code': stock_code,
            'daily_data': None,
            'realtime_quote': None,
            'fundamental_data': None,
        }

        # 获取日线数据
        try:
            df = self.get_daily_data(stock_code, days=days)
            result['daily_data'] = df
        except Exception as e:
            logger.error(f"获取 {stock_code} Yahoo Finance日线数据失败: {e}")

        # 获取实时行情
        result['realtime_quote'] = self.get_realtime_quote(stock_code)

        # 获取基本面数据
        result['fundamental_data'] = self.get_fundamental_data(stock_code)

        return result


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)

    fetcher = YfinanceFetcher()

    try:
        df = fetcher.get_daily_data('600519')  # 茅台
        print(f"获取成功，共 {len(df)} 条数据")
        print(df.tail())
    except Exception as e:
        print(f"获取失败: {e}")
