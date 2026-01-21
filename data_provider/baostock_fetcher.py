# -*- coding: utf-8 -*-
"""
===================================
BaostockFetcher - 备用数据源 2 (Priority 3)
===================================

数据来源：证券宝（Baostock）
特点：免费、无需 Token、需要登录管理
优点：稳定、无配额限制

关键策略：
1. 管理 bs.login() 和 bs.logout() 生命周期
2. 使用上下文管理器防止连接泄露
3. 失败后指数退避重试
"""

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Generator, Dict, Any

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


class BaostockFetcher(BaseFetcher):
    """
    Baostock 数据源实现

    优先级：3
    数据来源：证券宝 Baostock API

    关键策略：
    - 使用上下文管理器管理连接生命周期
    - 每次请求都重新登录/登出，防止连接泄露
    - 失败后指数退避重试

    Baostock 特点：
    - 免费、无需注册
    - 需要显式登录/登出
    - 数据更新略有延迟（T+1）
    """

    name = "BaostockFetcher"
    priority = 3

    def __init__(self):
        """初始化 BaostockFetcher"""
        self._bs_module = None

    def _get_baostock(self):
        """
        延迟加载 baostock 模块

        只在首次使用时导入，避免未安装时报错
        """
        if self._bs_module is None:
            import baostock as bs

            self._bs_module = bs
        return self._bs_module

    @contextmanager
    def _baostock_session(self) -> Generator:
        """
        Baostock 连接上下文管理器

        确保：
        1. 进入上下文时自动登录
        2. 退出上下文时自动登出
        3. 异常时也能正确登出

        使用示例：
            with self._baostock_session():
                # 在这里执行数据查询
        """
        bs = self._get_baostock()
        login_result = None

        try:
            # 登录 Baostock
            login_result = bs.login()

            if login_result.error_code != '0':
                raise DataFetchError(f"Baostock 登录失败: {login_result.error_msg}")

            logger.debug("Baostock 登录成功")

            yield bs

        finally:
            # 确保登出，防止连接泄露
            try:
                logout_result = bs.logout()
                if logout_result.error_code == '0':
                    logger.debug("Baostock 登出成功")
                else:
                    logger.warning(f"Baostock 登出异常: {logout_result.error_msg}")
            except Exception as e:
                logger.warning(f"Baostock 登出时发生错误: {e}")

    def _convert_stock_code(self, stock_code: str) -> str:
        """
        转换股票代码为 Baostock 格式

        Baostock 要求的格式：
        - 沪市：sh.600519
        - 深市：sz.000001

        Args:
            stock_code: 原始代码，如 '600519', '000001'

        Returns:
            Baostock 格式代码，如 'sh.600519', 'sz.000001'
        """
        code = stock_code.strip()

        # 已经包含前缀的情况
        if code.startswith(('sh.', 'sz.')):
            return code.lower()

        # 去除可能的后缀
        code = code.replace('.SH', '').replace('.SZ', '').replace('.sh', '').replace('.sz', '')

        # 根据代码前缀判断市场
        if code.startswith(('600', '601', '603', '688')):
            return f"sh.{code}"
        elif code.startswith(('000', '002', '300')):
            return f"sz.{code}"
        else:
            logger.warning(f"无法确定股票 {code} 的市场，默认使用深市")
            return f"sz.{code}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        从 Baostock 获取原始数据

        使用 query_history_k_data_plus() 获取日线数据

        流程：
        1. 使用上下文管理器管理连接
        2. 转换股票代码格式
        3. 调用 API 查询数据
        4. 将结果转换为 DataFrame
        """
        # 转换代码格式
        bs_code = self._convert_stock_code(stock_code)

        logger.debug(f"调用 Baostock query_history_k_data_plus({bs_code}, {start_date}, {end_date})")

        with self._baostock_session() as bs:
            try:
                # 查询日线数据
                # adjustflag: 1-后复权，2-前复权，3-不复权
                rs = bs.query_history_k_data_plus(
                    code=bs_code,
                    fields="date,open,high,low,close,volume,amount,pctChg",
                    start_date=start_date,
                    end_date=end_date,
                    frequency="d",  # 日线
                    adjustflag="2",  # 前复权
                )

                if rs.error_code != '0':
                    raise DataFetchError(f"Baostock 查询失败: {rs.error_msg}")

                # 转换为 DataFrame
                data_list = []
                while rs.next():
                    data_list.append(rs.get_row_data())

                if not data_list:
                    raise DataFetchError(f"Baostock 未查询到 {stock_code} 的数据")

                df = pd.DataFrame(data_list, columns=rs.fields)

                return df

            except Exception as e:
                if isinstance(e, DataFetchError):
                    raise
                raise DataFetchError(f"Baostock 获取数据失败: {e}") from e

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        标准化 Baostock 数据

        Baostock 返回的列名：
        date, open, high, low, close, volume, amount, pctChg

        需要映射到标准列名：
        date, open, high, low, close, volume, amount, pct_chg
        """
        df = df.copy()

        # 列名映射（只需要处理 pctChg）
        column_mapping = {
            'pctChg': 'pct_chg',
        }

        df = df.rename(columns=column_mapping)

        # 数值类型转换（Baostock 返回的都是字符串）
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 添加股票代码列
        df['code'] = stock_code

        # 只保留需要的列
        keep_cols = ['code'] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]

        return df

    def get_realtime_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        获取实时行情数据（Baostock）

        注意：Baostock 主要提供历史数据，实时数据通过最新日线数据模拟

        Args:
            stock_code: 股票代码

        Returns:
            实时行情数据字典，获取失败返回 None
        """
        try:
            # 转换代码格式
            bs_code = self._convert_stock_code(stock_code)

            logger.info(f"[API调用] Baostock 获取 {stock_code} 最新行情...")

            with self._baostock_session() as bs:
                # 获取最近3天的数据（确保能获取到最新交易日）
                from datetime import datetime, timedelta

                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')

                rs = bs.query_history_k_data_plus(
                    code=bs_code,
                    fields="date,open,high,low,close,volume,amount,pctChg",
                    start_date=start_date,
                    end_date=end_date,
                    frequency="d",
                    adjustflag="2",
                )

                if rs.error_code != '0':
                    logger.warning(f"[API返回] Baostock 查询最新行情失败: {rs.error_msg}")
                    return None

                # 转换为 DataFrame 并取最新一条
                data_list = []
                while rs.next():
                    data_list.append(rs.get_row_data())

                if not data_list:
                    logger.warning(f"[API返回] Baostock 未找到 {stock_code} 的最新数据")
                    return None

                df = pd.DataFrame(data_list, columns=rs.fields)

                # 数值转换
                numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'pctChg']
                for col in numeric_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')

                # 取最新一条数据
                latest = df.iloc[-1]

                # 构造实时行情数据
                quote_data = {
                    'code': stock_code,
                    'name': f'股票{stock_code}',  # Baostock不提供股票名称
                    'price': float(latest.get('close', 0)),
                    'change_pct': float(latest.get('pctChg', 0)),
                    'change_amount': 0.0,  # 需要计算
                    'volume_ratio': 0.0,  # Baostock不提供量比
                    'turnover_rate': 0.0,  # Baostock不提供换手率
                    'amplitude': 0.0,  # 可以计算
                    'pe_ratio': 0.0,  # Baostock不提供PE
                    'pb_ratio': 0.0,  # Baostock不提供PB
                    'total_mv': 0.0,  # Baostock不提供市值
                    'circulation_mv': 0.0,
                }

                # 计算振幅
                high = float(latest.get('high', 0))
                low = float(latest.get('low', 0))
                pre_close = quote_data['price'] / (1 + quote_data['change_pct'] / 100)
                if pre_close > 0:
                    quote_data['amplitude'] = (high - low) / pre_close * 100
                    quote_data['change_amount'] = quote_data['price'] - pre_close

                logger.info(f"[实时行情] {stock_code}: 价格={quote_data['price']}, 涨跌幅={quote_data['change_pct']}%")
                return quote_data

        except Exception as e:
            logger.error(f"[API错误] 获取 {stock_code} Baostock实时行情失败: {e}")
            return None

    def get_fundamental_data(self, stock_code: str) -> Dict[str, Any]:
        """
        获取基本面数据（Baostock）

        注意：Baostock 不提供详细的基本面数据，返回默认值

        Args:
            stock_code: 股票代码

        Returns:
            包含基本面指标的字典（大部分为默认值）
        """
        logger.debug(f"Baostock 不提供详细基本面数据，返回默认值")

        # Baostock 主要提供历史价格数据，基本面数据有限
        fundamental_data = {
            'pe_ratio': 0.0,  # Baostock不提供
            'pb_ratio': 0.0,  # Baostock不提供
            'total_mv': 0.0,  # Baostock不提供
            'circ_mv': 0.0,  # Baostock不提供
            'roe': 0.0,  # Baostock不提供
            'revenue_growth': 0.0,  # Baostock不提供
        }

        return fundamental_data

    def get_enhanced_data(self, stock_code: str, days: int = 60) -> Dict[str, Any]:
        """
        获取增强数据（历史K线 + 实时行情）

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
            logger.error(f"获取 {stock_code} Baostock日线数据失败: {e}")

        # 获取实时行情
        result['realtime_quote'] = self.get_realtime_quote(stock_code)

        # 获取基本面数据
        result['fundamental_data'] = self.get_fundamental_data(stock_code)

        return result


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)

    fetcher = BaostockFetcher()

    try:
        df = fetcher.get_daily_data('600519')  # 茅台
        print(f"获取成功，共 {len(df)} 条数据")
        print(df.tail())
    except Exception as e:
        print(f"获取失败: {e}")
