# -*- coding: utf-8 -*-
"""
===================================
TushareFetcher - 备用数据源 1 (Priority 2)
===================================

数据来源：Tushare Pro API（挖地兔）
特点：需要 Token、有请求配额限制
优点：数据质量高、接口稳定

流控策略：
1. 实现"每分钟调用计数器"
2. 超过免费配额（80次/分）时，强制休眠到下一分钟
3. 使用 tenacity 实现指数退避重试
"""

import logging
import time
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

import pandas as pd
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .base import BaseFetcher, DataFetchError, RateLimitError, STANDARD_COLUMNS
from config import get_config

logger = logging.getLogger(__name__)


class TushareFetcher(BaseFetcher):
    """
    Tushare Pro 数据源实现

    优先级：2
    数据来源：Tushare Pro API

    关键策略：
    - 每分钟调用计数器，防止超出配额
    - 超过 80 次/分钟时强制等待
    - 失败后指数退避重试

    配额说明（Tushare 免费用户）：
    - 每分钟最多 80 次请求
    - 每天最多 500 次请求
    """

    name = "TushareFetcher"
    priority = 2

    def __init__(self, rate_limit_per_minute: int = 80):
        """
        初始化 TushareFetcher

        Args:
            rate_limit_per_minute: 每分钟最大请求数（默认80，Tushare免费配额）
        """
        self.rate_limit_per_minute = rate_limit_per_minute
        self._call_count = 0  # 当前分钟内的调用次数
        self._minute_start: Optional[float] = None  # 当前计数周期开始时间
        self._api: Optional[object] = None  # Tushare API 实例

        # 尝试初始化 API
        self._init_api()

    def _init_api(self) -> None:
        """
        初始化 Tushare API

        如果 Token 未配置，此数据源将不可用
        """
        config = get_config()

        if not config.tushare_token:
            logger.warning("Tushare Token 未配置，此数据源不可用")
            return

        try:
            import tushare as ts

            # 设置 Token
            ts.set_token(config.tushare_token)

            # 获取 API 实例
            self._api = ts.pro_api()

            logger.info("Tushare API 初始化成功")

        except Exception as e:
            logger.error(f"Tushare API 初始化失败: {e}")
            self._api = None

    def _check_rate_limit(self) -> None:
        """
        检查并执行速率限制

        流控策略：
        1. 检查是否进入新的一分钟
        2. 如果是，重置计数器
        3. 如果当前分钟调用次数超过限制，强制休眠
        """
        current_time = time.time()

        # 检查是否需要重置计数器（新的一分钟）
        if self._minute_start is None:
            self._minute_start = current_time
            self._call_count = 0
        elif current_time - self._minute_start >= 60:
            # 已经过了一分钟，重置计数器
            self._minute_start = current_time
            self._call_count = 0
            logger.debug("速率限制计数器已重置")

        # 检查是否超过配额
        if self._call_count >= self.rate_limit_per_minute:
            # 计算需要等待的时间（到下一分钟）
            elapsed = current_time - self._minute_start
            sleep_time = max(0, 60 - elapsed) + 1  # +1 秒缓冲

            logger.warning(
                f"Tushare 达到速率限制 ({self._call_count}/{self.rate_limit_per_minute} 次/分钟)，"
                f"等待 {sleep_time:.1f} 秒..."
            )

            time.sleep(sleep_time)

            # 重置计数器
            self._minute_start = time.time()
            self._call_count = 0

        # 增加调用计数
        self._call_count += 1
        logger.debug(f"Tushare 当前分钟调用次数: {self._call_count}/{self.rate_limit_per_minute}")

    def _convert_stock_code(self, stock_code: str) -> str:
        """
        转换股票代码为 Tushare 格式

        Tushare 要求的格式：
        - 沪市：600519.SH
        - 深市：000001.SZ

        Args:
            stock_code: 原始代码，如 '600519', '000001'

        Returns:
            Tushare 格式代码，如 '600519.SH', '000001.SZ'
        """
        code = stock_code.strip()

        # 已经包含后缀的情况
        if '.' in code:
            return code.upper()

        # 根据代码前缀判断市场
        # 沪市：600xxx, 601xxx, 603xxx, 688xxx (科创板)
        # 深市：000xxx, 002xxx, 300xxx (创业板)
        if code.startswith(('600', '601', '603', '688')):
            return f"{code}.SH"
        elif code.startswith(('000', '002', '300')):
            return f"{code}.SZ"
        else:
            # 默认尝试深市
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
        从 Tushare 获取原始数据

        使用 daily() 接口获取日线数据

        流程：
        1. 检查 API 是否可用
        2. 执行速率限制检查
        3. 转换股票代码格式
        4. 调用 API 获取数据
        """
        if self._api is None:
            raise DataFetchError("Tushare API 未初始化，请检查 Token 配置")

        # 速率限制检查
        self._check_rate_limit()

        # 转换代码格式
        ts_code = self._convert_stock_code(stock_code)

        # 转换日期格式（Tushare 要求 YYYYMMDD）
        ts_start = start_date.replace('-', '')
        ts_end = end_date.replace('-', '')

        logger.debug(f"调用 Tushare daily({ts_code}, {ts_start}, {ts_end})")

        try:
            # 调用 daily 接口获取日线数据
            df = self._api.daily(
                ts_code=ts_code,
                start_date=ts_start,
                end_date=ts_end,
            )

            return df

        except Exception as e:
            error_msg = str(e).lower()

            # 检测配额超限
            if any(keyword in error_msg for keyword in ['quota', '配额', 'limit', '权限']):
                logger.warning(f"Tushare 配额可能超限: {e}")
                raise RateLimitError(f"Tushare 配额超限: {e}") from e

            raise DataFetchError(f"Tushare 获取数据失败: {e}") from e

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        标准化 Tushare 数据

        Tushare daily 返回的列名：
        ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount

        需要映射到标准列名：
        date, open, high, low, close, volume, amount, pct_chg
        """
        df = df.copy()

        # 列名映射
        column_mapping = {
            'trade_date': 'date',
            'vol': 'volume',
            # open, high, low, close, amount, pct_chg 列名相同
        }

        df = df.rename(columns=column_mapping)

        # 转换日期格式（YYYYMMDD -> YYYY-MM-DD）
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')

        # 成交量单位转换（Tushare 的 vol 单位是手，需要转换为股）
        if 'volume' in df.columns:
            df['volume'] = df['volume'] * 100

        # 成交额单位转换（Tushare 的 amount 单位是千元，转换为元）
        if 'amount' in df.columns:
            df['amount'] = df['amount'] * 1000

        # 添加股票代码列
        df['code'] = stock_code

        # 只保留需要的列
        keep_cols = ['code'] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]

        return df

    def get_realtime_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        获取实时行情数据（Tushare Pro）

        使用 daily_basic 接口获取最新的基本面数据
        注意：Tushare 的实时数据可能有延迟

        Args:
            stock_code: 股票代码

        Returns:
            实时行情数据字典，获取失败返回 None
        """
        if self._api is None:
            logger.warning("Tushare API 未初始化，无法获取实时行情")
            return None

        try:
            # 速率限制检查
            self._check_rate_limit()

            # 转换代码格式
            ts_code = self._convert_stock_code(stock_code)

            # 获取最新交易日的基本面数据
            today = datetime.now().strftime('%Y%m%d')

            logger.info(f"[API调用] Tushare daily_basic({ts_code}) 获取实时行情...")

            # 获取基本面数据（包含PE、PB等）
            basic_df = self._api.daily_basic(
                ts_code=ts_code,
                trade_date=today,
                fields='ts_code,trade_date,close,turnover_rate,volume_ratio,pe,pb,total_mv,circ_mv',
            )

            if basic_df.empty:
                # 如果今天没有数据，尝试获取最近的数据
                basic_df = self._api.daily_basic(
                    ts_code=ts_code, fields='ts_code,trade_date,close,turnover_rate,volume_ratio,pe,pb,total_mv,circ_mv'
                )
                if not basic_df.empty:
                    basic_df = basic_df.head(1)  # 取最新一条

            if basic_df.empty:
                logger.warning(f"[API返回] Tushare 未找到股票 {stock_code} 的基本面数据")
                return None

            row = basic_df.iloc[0]

            # 构造实时行情数据
            quote_data = {
                'code': stock_code,
                'name': f'股票{stock_code}',  # Tushare basic接口不返回名称
                'price': float(row.get('close', 0)),
                'change_pct': 0.0,  # basic接口不提供涨跌幅
                'change_amount': 0.0,
                'volume_ratio': float(row.get('volume_ratio', 0)),
                'turnover_rate': float(row.get('turnover_rate', 0)),
                'amplitude': 0.0,  # basic接口不提供振幅
                'pe_ratio': float(row.get('pe', 0)),
                'pb_ratio': float(row.get('pb', 0)),
                'total_mv': float(row.get('total_mv', 0)) * 10000,  # 转换为元（Tushare单位是万元）
                'circulation_mv': float(row.get('circ_mv', 0)) * 10000,  # 转换为元
            }

            logger.info(f"[实时行情] {stock_code}: 价格={quote_data['price']}, PE={quote_data['pe_ratio']}")
            return quote_data

        except Exception as e:
            logger.error(f"[API错误] 获取 {stock_code} Tushare实时行情失败: {e}")
            return None

    def get_fundamental_data(self, stock_code: str) -> Dict[str, Any]:
        """
        获取基本面数据（Tushare Pro）

        使用 daily_basic 和 fina_indicator 接口获取基本面数据

        Args:
            stock_code: 股票代码

        Returns:
            包含基本面指标的字典
        """
        if self._api is None:
            logger.warning("Tushare API 未初始化，无法获取基本面数据")
            return {}

        try:
            # 速率限制检查
            self._check_rate_limit()

            # 转换代码格式
            ts_code = self._convert_stock_code(stock_code)

            logger.info(f"[API调用] Tushare 获取 {stock_code} 基本面数据...")

            # 获取最新的基本面数据
            basic_df = self._api.daily_basic(ts_code=ts_code, fields='ts_code,trade_date,pe,pb,total_mv,circ_mv')

            fundamental_data = {
                'pe_ratio': 0.0,
                'pb_ratio': 0.0,
                'total_mv': 0.0,
                'circ_mv': 0.0,
                'roe': 0.0,
                'revenue_growth': 0.0,
            }

            if not basic_df.empty:
                latest = basic_df.iloc[0]
                fundamental_data.update(
                    {
                        'pe_ratio': float(latest.get('pe', 0)),
                        'pb_ratio': float(latest.get('pb', 0)),
                        'total_mv': float(latest.get('total_mv', 0)) * 10000,  # 万元转元
                        'circ_mv': float(latest.get('circ_mv', 0)) * 10000,
                    }
                )

            # 尝试获取财务指标（ROE等）
            try:
                # 速率限制检查
                self._check_rate_limit()

                # 获取最新年报的财务指标
                current_year = datetime.now().year
                fina_df = self._api.fina_indicator(
                    ts_code=ts_code,
                    period=f'{current_year}1231',  # 最新年报
                    fields='ts_code,end_date,roe,or_yoy',  # ROE和营收增长率
                )

                if not fina_df.empty:
                    fina_row = fina_df.iloc[0]
                    fundamental_data.update(
                        {
                            'roe': float(fina_row.get('roe', 0)),
                            'revenue_growth': float(fina_row.get('or_yoy', 0)),
                        }
                    )

            except Exception as e:
                logger.debug(f"获取 {stock_code} 财务指标失败: {e}")

            return fundamental_data

        except Exception as e:
            logger.error(f"[API错误] 获取股票 {stock_code} Tushare基本面数据失败: {e}")
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
            logger.error(f"获取 {stock_code} Tushare日线数据失败: {e}")

        # 获取实时行情
        result['realtime_quote'] = self.get_realtime_quote(stock_code)

        # 获取基本面数据
        result['fundamental_data'] = self.get_fundamental_data(stock_code)

        return result


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)

    fetcher = TushareFetcher()

    try:
        df = fetcher.get_daily_data('600519')  # 茅台
        print(f"获取成功，共 {len(df)} 条数据")
        print(df.tail())
    except Exception as e:
        print(f"获取失败: {e}")
