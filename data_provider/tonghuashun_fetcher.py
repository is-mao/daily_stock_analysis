# -*- coding: utf-8 -*-
"""
===================================
TonghuashunFetcher - 同花顺数据源 (Priority 0.5)
===================================

数据来源：同花顺 API (d.10jqka.com.cn)
特点：速度快、数据全面、同花顺官方接口
定位：专门用于快速股票精选模式，与腾讯数据源并列

接口说明：
- 实时行情：http://d.10jqka.com.cn/v6/line/hs_{code}/01/last.js
- 基本信息：http://basic.10jqka.com.cn/{code}/
- 资金流向：http://d.10jqka.com.cn/v2/fkline/hs_{code}/last.js

防封禁策略：
1. 每次请求前随机休眠 0.2-0.6 秒
2. 随机轮换 User-Agent
3. 使用 tenacity 实现指数退避重试
"""

import logging
import time
import random
import json
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import requests
import pandas as pd
from dataclasses import dataclass
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .base import BaseFetcher, DataFetchError, RateLimitError, STANDARD_COLUMNS

logger = logging.getLogger(__name__)


@dataclass
class TonghuashunRealtimeQuote:
    """
    同花顺实时行情数据

    包含当日实时交易数据和估值指标
    """

    code: str
    name: str = ""
    price: float = 0.0  # 最新价
    change_pct: float = 0.0  # 涨跌幅(%)
    change_amount: float = 0.0  # 涨跌额

    # 量价指标
    volume: int = 0  # 成交量
    amount: float = 0.0  # 成交额
    volume_ratio: float = 0.0  # 量比（同花顺API不直接提供，设为默认值）
    turnover_rate: float = 0.0  # 换手率(%)
    amplitude: float = 0.0  # 振幅(%)

    # 价格区间
    high: float = 0.0  # 最高价
    low: float = 0.0  # 最低价
    open_price: float = 0.0  # 开盘价
    pre_close: float = 0.0  # 昨收价

    # 估值指标
    pe_ratio: float = 0.0  # 市盈率
    pb_ratio: float = 0.0  # 市净率
    total_mv: float = 0.0  # 总市值
    circulation_mv: float = 0.0  # 流通市值

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'code': self.code,
            'name': self.name,
            'price': self.price,
            'change_pct': self.change_pct,
            'change_amount': self.change_amount,
            'volume': self.volume,
            'amount': self.amount,
            'volume_ratio': self.volume_ratio,
            'turnover_rate': self.turnover_rate,
            'amplitude': self.amplitude,
            'high': self.high,
            'low': self.low,
            'open_price': self.open_price,  # 修正：使用正确的字段名
            'pre_close': self.pre_close,
            'pe_ratio': self.pe_ratio,
            'pb_ratio': self.pb_ratio,
            'total_mv': self.total_mv,
            'circulation_mv': self.circulation_mv,
        }


# User-Agent 池，用于随机轮换
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]


# 缓存实时行情数据（避免重复请求）
_realtime_cache: Dict[str, Any] = {'data': {}, 'timestamp': 0, 'ttl': 45}  # 45秒缓存有效期


class TonghuashunFetcher(BaseFetcher):
    """
    同花顺数据源实现

    优先级：0.5（高优先级，与腾讯数据源并列）
    数据来源：同花顺 API (d.10jqka.com.cn)

    主要 API：
    - 实时行情：http://d.10jqka.com.cn/v6/line/hs_{code}/01/last.js
    - 基本信息：http://basic.10jqka.com.cn/{code}/
    - 资金流向：http://d.10jqka.com.cn/v2/fkline/hs_{code}/last.js

    关键策略：
    - 每次请求前随机休眠 0.2-0.6 秒
    - 随机 User-Agent 轮换
    - 失败后指数退避重试（最多3次）
    """

    name = "TonghuashunFetcher"
    priority = 0.5  # 高优先级，与腾讯数据源并列

    def __init__(self, sleep_min: float = 0.2, sleep_max: float = 0.6):
        """
        初始化 TonghuashunFetcher

        Args:
            sleep_min: 最小休眠时间（秒）
            sleep_max: 最大休眠时间（秒）
        """
        self.sleep_min = sleep_min
        self.sleep_max = sleep_max
        self._last_request_time: Optional[float] = None
        self.session = requests.Session()

    def _set_random_user_agent(self) -> None:
        """
        设置随机 User-Agent

        通过修改 requests Session 的 headers 实现
        这是关键的反爬策略之一
        """
        try:
            random_ua = random.choice(USER_AGENTS)
            self.session.headers.update(
                {
                    'User-Agent': random_ua,
                    'Referer': 'http://10jqka.com.cn/',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                }
            )
            logger.debug(f"设置 User-Agent: {random_ua[:50]}...")
        except Exception as e:
            logger.debug(f"设置 User-Agent 失败: {e}")

    def _enforce_rate_limit(self) -> None:
        """
        强制执行速率限制

        策略：
        1. 检查距离上次请求的时间间隔
        2. 如果间隔不足，补充休眠时间
        3. 然后再执行随机 jitter 休眠
        """
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            min_interval = self.sleep_min
            if elapsed < min_interval:
                additional_sleep = min_interval - elapsed
                logger.debug(f"补充休眠 {additional_sleep:.2f} 秒")
                time.sleep(additional_sleep)

        # 执行随机 jitter 休眠
        self.random_sleep(self.sleep_min, self.sleep_max)
        self._last_request_time = time.time()

    def _convert_stock_code(self, stock_code: str) -> str:
        """
        转换股票代码为同花顺格式

        同花顺要求的格式：
        - 沪市：hs_600519
        - 深市：hs_000001

        Args:
            stock_code: 原始代码，如 '600519', '000001'

        Returns:
            同花顺格式代码，如 'hs_600519', 'hs_000001'
        """
        code = stock_code.strip()

        # 已经包含前缀的情况
        if code.startswith('hs_'):
            return code.lower()

        # 去除可能的后缀
        code = code.replace('.SH', '').replace('.SZ', '').replace('.sh', '').replace('.sz', '')
        code = code.replace('sh', '').replace('sz', '')

        # 同花顺统一使用 hs_ 前缀
        return f"hs_{code}"

    @retry(
        stop=stop_after_attempt(3),  # 最多重试3次
        wait=wait_exponential(multiplier=0.5, min=1, max=15),  # 指数退避：0.5, 1, 2... 最大15秒
        retry=retry_if_exception_type((ConnectionError, TimeoutError, requests.RequestException)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        从同花顺获取原始数据

        注意：同花顺API主要提供实时数据，历史数据需要通过实时数据模拟
        这里我们获取实时数据并构造简单的历史数据格式

        流程：
        1. 设置随机 User-Agent
        2. 执行速率限制（随机休眠）
        3. 调用同花顺实时行情API
        4. 处理返回数据
        """
        # 防封禁策略 1: 随机 User-Agent
        self._set_random_user_agent()

        # 防封禁策略 2: 强制休眠
        self._enforce_rate_limit()

        # 转换代码格式
        ths_code = self._convert_stock_code(stock_code)

        logger.info(f"[API调用] 同花顺实时行情: {ths_code}")

        try:
            import time as _time

            api_start = _time.time()

            # 调用同花顺实时行情API
            url = f"http://d.10jqka.com.cn/v6/line/{ths_code}/01/last.js"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            api_elapsed = _time.time() - api_start

            # 解析返回数据
            content = response.text.strip()
            if not content or 'null' in content or len(content) < 10:
                raise DataFetchError(f"同花顺API未找到股票 {stock_code} 的数据")

            # 同花顺返回格式：quotebridge_v6_line_hs_600519_01_last({"data":"2024-01-20,1850.00,1860.00,..."})
            # 提取JSON数据部分
            json_match = re.search(r'\(({.*})\)', content)
            if not json_match:
                raise DataFetchError(f"同花顺API返回数据格式异常: {content[:100]}")

            json_data = json.loads(json_match.group(1))
            data_str = json_data.get('data', '')

            if not data_str:
                raise DataFetchError(f"同花顺API返回空数据")

            # 解析数据字符串
            # 格式：日期,开盘,收盘,最高,最低,成交量,成交额,涨跌幅
            fields = data_str.split(',')
            if len(fields) < 8:
                raise DataFetchError(f"同花顺API返回字段不足: {len(fields)} < 8")

            # 解析字段
            date_str = fields[0]
            open_price = float(fields[1]) if fields[1] else 0.0
            current_price = float(fields[2]) if fields[2] else 0.0
            high = float(fields[3]) if fields[3] else current_price
            low = float(fields[4]) if fields[4] else current_price
            volume = int(float(fields[5]) * 100) if fields[5] else 0  # 手转股
            amount = float(fields[6]) * 10000 if fields[6] else 0.0  # 万元转元
            change_pct = float(fields[7]) if fields[7] else 0.0

            # 构造DataFrame（模拟历史数据格式）
            if not date_str or date_str == '0':
                date_str = datetime.now().strftime('%Y-%m-%d')
            else:
                # 转换日期格式
                try:
                    date_obj = datetime.strptime(date_str, '%Y%m%d')
                    date_str = date_obj.strftime('%Y-%m-%d')
                except:
                    date_str = datetime.now().strftime('%Y-%m-%d')

            df_data = {
                'date': [date_str],
                'open': [open_price],
                'high': [high],
                'low': [low],
                'close': [current_price],
                'volume': [volume],
                'amount': [amount],
                'pct_chg': [change_pct],
            }

            df = pd.DataFrame(df_data)

            logger.info(f"[API返回] 同花顺 成功: {stock_code} 价格={current_price}, 耗时 {api_elapsed:.2f}s")
            return df

        except Exception as e:
            error_msg = str(e).lower()

            # 检测反爬封禁
            if any(keyword in error_msg for keyword in ['banned', 'blocked', '频率', 'rate', '限制', '403', '429']):
                logger.warning(f"检测到可能被封禁: {e}")
                raise RateLimitError(f"同花顺API可能被限流: {e}") from e

            raise DataFetchError(f"同花顺API获取数据失败: {e}") from e

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        标准化同花顺数据

        同花顺返回的数据已经是标准格式，只需要添加股票代码
        """
        df = df.copy()

        # 添加股票代码列
        df['code'] = stock_code

        # 只保留需要的列
        keep_cols = ['code'] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]

        return df

    def get_realtime_quote(self, stock_code: str) -> Optional[TonghuashunRealtimeQuote]:
        """
        获取实时行情数据

        Args:
            stock_code: 股票代码

        Returns:
            TonghuashunRealtimeQuote 对象，获取失败返回 None
        """
        try:
            # 检查缓存
            current_time = time.time()
            cache_key = stock_code

            if (
                cache_key in _realtime_cache['data']
                and current_time - _realtime_cache['timestamp'] < _realtime_cache['ttl']
            ):
                quote_data = _realtime_cache['data'][cache_key]
                logger.debug(f"[缓存命中] 使用缓存的 {stock_code} 实时行情数据")
                return TonghuashunRealtimeQuote(**quote_data)

            # 防封禁策略
            self._set_random_user_agent()
            self._enforce_rate_limit()

            # 转换代码格式
            ths_code = self._convert_stock_code(stock_code)

            logger.info(f"[API调用] 同花顺实时行情: {ths_code}")
            import time as _time

            api_start = _time.time()

            # 调用同花顺实时行情API
            url = f"http://d.10jqka.com.cn/v6/line/{ths_code}/01/last.js"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            api_elapsed = _time.time() - api_start

            # 解析返回数据
            content = response.text.strip()
            if not content or 'null' in content or len(content) < 10:
                logger.warning(f"[API返回] 未找到股票 {stock_code} 的实时行情")
                return None

            # 提取JSON数据部分
            json_match = re.search(r'\(({.*})\)', content)
            if not json_match:
                logger.warning(f"[API返回] 同花顺API返回数据格式异常")
                return None

            json_data = json.loads(json_match.group(1))
            data_str = json_data.get('data', '')

            if not data_str:
                logger.warning(f"[API返回] 同花顺API返回空数据")
                return None

            # 解析数据字符串
            fields = data_str.split(',')
            if len(fields) < 8:
                logger.warning(f"[API返回] 同花顺API返回字段不足: {len(fields)} < 8")
                return None

            # 安全获取字段值
            def safe_float(idx, default=0.0):
                try:
                    if idx < len(fields) and fields[idx]:
                        return float(fields[idx])
                    return default
                except:
                    return default

            def safe_int(idx, default=0):
                try:
                    if idx < len(fields) and fields[idx]:
                        return int(float(fields[idx]))
                    return default
                except:
                    return default

            # 解析关键字段
            open_price = safe_float(1)
            current_price = safe_float(2)
            high = safe_float(3, current_price)
            low = safe_float(4, current_price)
            volume = safe_int(5) * 100  # 手转股
            amount = safe_float(6) * 10000  # 万元转元
            change_pct = safe_float(7)

            # 计算其他字段
            pre_close = current_price / (1 + change_pct / 100) if change_pct != 0 else current_price
            change_amount = current_price - pre_close
            amplitude = 0.0
            if pre_close > 0:
                amplitude = ((high - low) / pre_close) * 100

            # 尝试获取股票名称（从另一个API）
            name = self._get_stock_name(stock_code)

            quote = TonghuashunRealtimeQuote(
                code=stock_code,
                name=name,
                price=current_price,
                change_pct=change_pct,
                change_amount=change_amount,
                volume=volume,
                amount=amount,
                turnover_rate=0.0,  # 同花顺此API不直接提供
                amplitude=amplitude,
                high=high,
                low=low,
                open_price=open_price,
                pre_close=pre_close,
                pe_ratio=0.0,  # 需要额外获取
                pb_ratio=0.0,  # 需要额外获取
                total_mv=0.0,  # 需要额外计算
                circulation_mv=0.0,  # 需要额外计算
            )

            # 更新缓存
            _realtime_cache['data'][cache_key] = quote.to_dict()
            _realtime_cache['timestamp'] = current_time

            logger.info(
                f"[实时行情] {stock_code} {quote.name}: 价格={quote.price}, 涨跌={quote.change_pct}%, "
                f"耗时 {api_elapsed:.2f}s"
            )
            return quote

        except Exception as e:
            logger.error(f"[API错误] 获取 {stock_code} 实时行情失败: {e}")
            return None

    def _get_stock_name(self, stock_code: str) -> str:
        """
        获取股票名称

        Args:
            stock_code: 股票代码

        Returns:
            股票名称
        """
        try:
            # 使用同花顺基本信息API获取股票名称
            url = f"http://basic.10jqka.com.cn/{stock_code}/"
            response = self.session.get(url, timeout=5)
            response.raise_for_status()

            content = response.text
            # 简单的正则提取股票名称
            name_match = re.search(r'<title>([^(]+)', content)
            if name_match:
                name = name_match.group(1).strip()
                return name

        except Exception as e:
            logger.debug(f"获取股票 {stock_code} 名称失败: {e}")

        return f"股票{stock_code}"

    def get_fundamental_data(self, stock_code: str) -> Dict[str, Any]:
        """
        获取基本面数据（从实时行情构造）

        Args:
            stock_code: 股票代码

        Returns:
            包含基本面指标的字典
        """
        try:
            # 从实时行情获取估值指标
            quote = self.get_realtime_quote(stock_code)
            if not quote:
                return {}

            # 构建基本面数据字典
            fundamental_data = {
                'pe_ratio': getattr(quote, 'pe_ratio', 0.0),
                'pb_ratio': getattr(quote, 'pb_ratio', 0.0),
                'total_mv': getattr(quote, 'total_mv', 0.0),
                'circ_mv': getattr(quote, 'circulation_mv', 0.0),
                'roe': 0.0,  # 同花顺API不直接提供ROE
                'revenue_growth': 0.0,  # 同花顺API不直接提供营收增长率
            }

            return fundamental_data

        except Exception as e:
            logger.error(f"[API错误] 获取股票 {stock_code} 基本面数据失败: {e}")
            return {}

    def get_enhanced_data(self, stock_code: str, days: int = 60) -> Dict[str, Any]:
        """
        获取增强数据（实时行情为主）

        Args:
            stock_code: 股票代码
            days: 历史数据天数（同花顺API主要提供实时数据）

        Returns:
            包含所有数据的字典
        """
        result = {
            'code': stock_code,
            'daily_data': None,
            'realtime_quote': None,
        }

        # 获取实时行情（主要数据）
        result['realtime_quote'] = self.get_realtime_quote(stock_code)

        # 尝试获取简单的日线数据
        try:
            df = self.get_daily_data(stock_code, days=1)  # 只获取当日数据
            result['daily_data'] = df
        except Exception as e:
            logger.warning(f"获取 {stock_code} 日线数据失败: {e}")

        return result


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)

    fetcher = TonghuashunFetcher()

    # 测试实时行情
    print("=" * 50)
    print("测试同花顺实时行情获取")
    print("=" * 50)
    try:
        quote = fetcher.get_realtime_quote('600519')  # 茅台
        if quote:
            print(f"[实时行情] {quote.name}: 价格={quote.price}, 涨跌幅={quote.change_pct}%")
            print(f"[实时行情] 振幅={quote.amplitude}%, 成交额={quote.amount/1e8:.2f}亿")
        else:
            print("[实时行情] 未获取到数据")
    except Exception as e:
        print(f"[实时行情] 获取失败: {e}")

    # 测试日线数据
    print("\n" + "=" * 50)
    print("测试同花顺日线数据获取")
    print("=" * 50)
    try:
        df = fetcher.get_daily_data('600519')  # 茅台
        print(f"[日线数据] 获取成功，共 {len(df)} 条数据")
        print(df.tail())
    except Exception as e:
        print(f"[日线数据] 获取失败: {e}")
