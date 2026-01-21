# -*- coding: utf-8 -*-
"""
===================================
SinaFetcher - 极速数据源 (Priority 0.1)
===================================

数据来源：新浪财经 API (hq.sinajs.cn)
特点：速度极快、稳定性高、免费无限制、毫秒级响应
定位：专门用于极速股票精选模式，速度优于腾讯数据源

接口说明：
- 实时行情：http://hq.sinajs.cn/list=sh600519,sz000001
- 批量查询：支持一次查询最多800只股票
- 历史数据：通过实时数据模拟构造

防封禁策略：
1. 每次请求前随机休眠 0.05-0.2 秒（极短延时）
2. 随机轮换 User-Agent
3. 使用 tenacity 实现指数退避重试
4. 批量查询减少请求次数
"""

import logging
import time
import random
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
class SinaRealtimeQuote:
    """
    新浪实时行情数据

    包含当日实时交易数据和基本指标
    """

    code: str
    name: str = ""
    price: float = 0.0  # 最新价
    change_pct: float = 0.0  # 涨跌幅(%)
    change_amount: float = 0.0  # 涨跌额

    # 量价指标
    volume: int = 0  # 成交量
    amount: float = 0.0  # 成交额
    volume_ratio: float = 0.0  # 量比（新浪API不直接提供，设为默认值）
    turnover_rate: float = 0.0  # 换手率(%)
    amplitude: float = 0.0  # 振幅(%)

    # 价格区间
    high: float = 0.0  # 最高价
    low: float = 0.0  # 最低价
    open_price: float = 0.0  # 开盘价
    pre_close: float = 0.0  # 昨收价

    # 估值指标（新浪API不直接提供，设为默认值）
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
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
]


# 缓存实时行情数据（避免重复请求）
_realtime_cache: Dict[str, Any] = {'data': {}, 'timestamp': 0, 'ttl': 30}  # 30秒缓存有效期


class SinaFetcher(BaseFetcher):
    """
    新浪财经数据源实现

    优先级：0.1（最高优先级，专门用于极速模式）
    数据来源：新浪财经 API (hq.sinajs.cn)

    主要 API：
    - 实时行情：http://hq.sinajs.cn/list={market_codes}
    - 批量查询：支持一次最多800只股票

    关键策略：
    - 每次请求前随机休眠 0.05-0.2 秒（极短延时）
    - 随机 User-Agent 轮换
    - 批量查询优化（一次获取多只股票）
    - 失败后指数退避重试（最多3次）
    """

    name = "SinaFetcher"
    priority = 0.1  # 最高优先级，专门用于极速模式

    def __init__(self, sleep_min: float = 0.05, sleep_max: float = 0.2):
        """
        初始化 SinaFetcher

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
                    'Referer': 'https://finance.sina.com.cn/',
                    'Accept': '*/*',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
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
        3. 然后再执行随机 jitter 休眠（极短）
        """
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            min_interval = self.sleep_min
            if elapsed < min_interval:
                additional_sleep = min_interval - elapsed
                logger.debug(f"补充休眠 {additional_sleep:.3f} 秒")
                time.sleep(additional_sleep)

        # 执行随机 jitter 休眠（极短延时）
        self.random_sleep(self.sleep_min, self.sleep_max)
        self._last_request_time = time.time()

    def _convert_stock_code(self, stock_code: str) -> str:
        """
        转换股票代码为新浪格式

        新浪要求的格式：
        - 沪市：sh600519
        - 深市：sz000001

        Args:
            stock_code: 原始代码，如 '600519', '000001'

        Returns:
            新浪格式代码，如 'sh600519', 'sz000001'
        """
        code = stock_code.strip()

        # 已经包含前缀的情况
        if code.startswith(('sh', 'sz')):
            return code.lower()

        # 去除可能的后缀
        code = code.replace('.SH', '').replace('.SZ', '').replace('.sh', '').replace('.sz', '')

        # 根据代码前缀判断市场
        if code.startswith(('600', '601', '603', '688')):
            return f"sh{code}"
        elif code.startswith(('000', '002', '300', '301')):
            return f"sz{code}"
        else:
            logger.warning(f"无法确定股票 {code} 的市场，默认使用深市")
            return f"sz{code}"

    def _parse_sina_data(self, content: str, stock_code: str) -> Optional[SinaRealtimeQuote]:
        """
        解析新浪返回的数据

        新浪返回格式：
        var hq_str_sh600519="贵州茅台,1850.00,1860.00,1840.00,1850.00,1845.00,1850.00,1851.00,12345678,1234567890.00,..."

        字段说明（按逗号分隔）：
        0:股票名称 1:今开 2:昨收 3:最新价 4:最高 5:最低 6:买一 7:卖一 8:成交量(股) 9:成交额(元)
        10:买一量 11:买一价 12:买二量 13:买二价 ... 30:日期 31:时间
        """
        try:
            # 提取数据部分
            match = re.search(r'="([^"]+)"', content)
            if not match:
                logger.warning(f"新浪API返回数据格式异常: {content[:100]}")
                return None

            data_str = match.group(1)
            if not data_str or data_str == "":
                logger.warning(f"新浪API返回空数据")
                return None

            fields = data_str.split(',')
            if len(fields) < 32:
                logger.warning(f"新浪API返回字段不足: {len(fields)} < 32")
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
            name = fields[0] if len(fields) > 0 else ""
            open_price = safe_float(1)
            pre_close = safe_float(2)
            current_price = safe_float(3)
            high = safe_float(4)
            low = safe_float(5)
            volume = safe_int(8)  # 成交量（股）
            amount = safe_float(9)  # 成交额（元）

            # 计算衍生指标
            change_amount = current_price - pre_close if pre_close > 0 else 0.0
            change_pct = (change_amount / pre_close * 100) if pre_close > 0 else 0.0
            amplitude = ((high - low) / pre_close * 100) if pre_close > 0 else 0.0

            quote = SinaRealtimeQuote(
                code=stock_code,
                name=name,
                price=current_price,
                change_pct=change_pct,
                change_amount=change_amount,
                volume=volume,
                amount=amount,
                turnover_rate=0.0,  # 新浪API不直接提供换手率
                amplitude=amplitude,
                high=high,
                low=low,
                open_price=open_price,
                pre_close=pre_close,
                pe_ratio=0.0,  # 新浪API不直接提供PE
                pb_ratio=0.0,  # 新浪API不直接提供PB
                total_mv=0.0,  # 新浪API不直接提供市值
                circulation_mv=0.0,  # 新浪API不直接提供流通市值
            )

            return quote

        except Exception as e:
            logger.error(f"解析新浪数据失败: {e}")
            return None

    @retry(
        stop=stop_after_attempt(3),  # 最多重试3次
        wait=wait_exponential(multiplier=0.3, min=0.5, max=5),  # 指数退避：0.3, 0.6, 1.2... 最大5秒
        retry=retry_if_exception_type((ConnectionError, TimeoutError, requests.RequestException)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        从新浪获取原始数据

        注意：新浪API主要提供实时数据，历史数据需要通过实时数据模拟
        这里我们获取实时数据并构造简单的历史数据格式

        流程：
        1. 设置随机 User-Agent
        2. 执行速率限制（极短随机休眠）
        3. 调用新浪实时行情API
        4. 处理返回数据
        """
        # 防封禁策略 1: 随机 User-Agent
        self._set_random_user_agent()

        # 防封禁策略 2: 强制休眠（极短）
        self._enforce_rate_limit()

        # 转换代码格式
        sina_code = self._convert_stock_code(stock_code)

        logger.info(f"[API调用] 新浪财经实时行情: {sina_code}")

        try:
            import time as _time

            api_start = _time.time()

            # 调用新浪实时行情API
            url = f"http://hq.sinajs.cn/list={sina_code}"
            response = self.session.get(url, timeout=5)
            response.raise_for_status()

            api_elapsed = _time.time() - api_start

            # 解析返回数据
            content = response.text.strip()
            if not content or 'null' in content or len(content) < 10:
                raise DataFetchError(f"新浪API未找到股票 {stock_code} 的数据")

            # 解析新浪数据
            quote = self._parse_sina_data(content, stock_code)
            if not quote:
                raise DataFetchError(f"新浪API数据解析失败")

            # 构造DataFrame（模拟历史数据格式）
            today = datetime.now().strftime('%Y-%m-%d')
            df_data = {
                'date': [today],
                'open': [quote.open_price],
                'high': [quote.high],
                'low': [quote.low],
                'close': [quote.price],
                'volume': [quote.volume],
                'amount': [quote.amount],
                'pct_chg': [quote.change_pct],
            }

            df = pd.DataFrame(df_data)

            logger.info(f"[API返回] 新浪财经 成功: {stock_code} 价格={quote.price}, 耗时 {api_elapsed:.3f}s")
            return df

        except Exception as e:
            error_msg = str(e).lower()

            # 检测反爬封禁
            if any(keyword in error_msg for keyword in ['banned', 'blocked', '频率', 'rate', '限制', '403', '429']):
                logger.warning(f"检测到可能被封禁: {e}")
                raise RateLimitError(f"新浪API可能被限流: {e}") from e

            raise DataFetchError(f"新浪API获取数据失败: {e}") from e

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        标准化新浪数据

        新浪返回的数据已经是标准格式，只需要添加股票代码
        """
        df = df.copy()

        # 添加股票代码列
        df['code'] = stock_code

        # 只保留需要的列
        keep_cols = ['code'] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]

        return df

    def get_realtime_quote(self, stock_code: str) -> Optional[SinaRealtimeQuote]:
        """
        获取实时行情数据

        Args:
            stock_code: 股票代码

        Returns:
            SinaRealtimeQuote 对象，获取失败返回 None
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
                return SinaRealtimeQuote(**quote_data)

            # 防封禁策略
            self._set_random_user_agent()
            self._enforce_rate_limit()

            # 转换代码格式
            sina_code = self._convert_stock_code(stock_code)

            logger.info(f"[API调用] 新浪实时行情: {sina_code}")
            import time as _time

            api_start = _time.time()

            # 调用新浪实时行情API
            url = f"http://hq.sinajs.cn/list={sina_code}"
            response = self.session.get(url, timeout=5)
            response.raise_for_status()

            api_elapsed = _time.time() - api_start

            # 解析返回数据
            content = response.text.strip()
            if not content or 'null' in content or len(content) < 10:
                logger.warning(f"[API返回] 未找到股票 {stock_code} 的实时行情")
                return None

            # 解析新浪数据
            quote = self._parse_sina_data(content, stock_code)
            if not quote:
                logger.warning(f"[API返回] 新浪数据解析失败")
                return None

            # 更新缓存
            _realtime_cache['data'][cache_key] = quote.to_dict()
            _realtime_cache['timestamp'] = current_time

            logger.info(
                f"[实时行情] {stock_code} {quote.name}: 价格={quote.price}, 涨跌={quote.change_pct}%, "
                f"耗时 {api_elapsed:.3f}s"
            )
            return quote

        except Exception as e:
            logger.error(f"[API错误] 获取 {stock_code} 实时行情失败: {e}")
            return None

    def get_batch_realtime_quotes(self, stock_codes: List[str]) -> Dict[str, Optional[SinaRealtimeQuote]]:
        """
        批量获取实时行情数据（新浪API优势功能）

        新浪API支持一次查询最多800只股票，大大提升效率

        Args:
            stock_codes: 股票代码列表

        Returns:
            股票代码到行情数据的映射字典
        """
        result = {}

        if not stock_codes:
            return result

        # 分批处理，每批最多800只
        batch_size = 800
        for i in range(0, len(stock_codes), batch_size):
            batch_codes = stock_codes[i : i + batch_size]
            batch_result = self._get_batch_quotes_single_request(batch_codes)
            result.update(batch_result)

        return result

    def _get_batch_quotes_single_request(self, stock_codes: List[str]) -> Dict[str, Optional[SinaRealtimeQuote]]:
        """
        单次批量请求获取实时行情

        Args:
            stock_codes: 股票代码列表（最多800只）

        Returns:
            股票代码到行情数据的映射字典
        """
        result = {}

        try:
            # 防封禁策略
            self._set_random_user_agent()
            self._enforce_rate_limit()

            # 转换代码格式
            sina_codes = [self._convert_stock_code(code) for code in stock_codes]
            codes_str = ','.join(sina_codes)

            logger.info(f"[API调用] 新浪批量实时行情: {len(stock_codes)} 只股票")
            import time as _time

            api_start = _time.time()

            # 调用新浪批量实时行情API
            url = f"http://hq.sinajs.cn/list={codes_str}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            api_elapsed = _time.time() - api_start

            # 解析返回数据
            content = response.text.strip()
            if not content:
                logger.warning(f"[API返回] 新浪批量API返回空数据")
                return result

            # 按行分割，每行对应一只股票
            lines = content.split('\n')

            for i, line in enumerate(lines):
                if i >= len(stock_codes):
                    break

                stock_code = stock_codes[i]
                quote = self._parse_sina_data(line, stock_code)
                result[stock_code] = quote

            success_count = sum(1 for v in result.values() if v is not None)
            logger.info(
                f"[批量行情] 新浪财经 成功: {success_count}/{len(stock_codes)} 只股票, " f"耗时 {api_elapsed:.3f}s"
            )

        except Exception as e:
            logger.error(f"[API错误] 新浪批量获取实时行情失败: {e}")
            # 失败时为所有股票返回None
            for code in stock_codes:
                result[code] = None

        return result

    def get_daily_data(self, stock_code: str, days: int = 60) -> Optional[pd.DataFrame]:
        """
        获取日线数据 - 新浪财经历史K线API

        新浪财经提供完整的历史K线数据API，支持多种时间周期

        Args:
            stock_code: 股票代码
            days: 历史数据天数（实际返回条数可能略有不同）

        Returns:
            包含日线数据的DataFrame，列名符合标准格式
        """
        try:
            # 防封禁策略
            self._set_random_user_agent()
            self._enforce_rate_limit()

            # 转换代码格式
            sina_code = self._convert_stock_code(stock_code)

            # 构建API URL - 使用新浪历史K线数据接口
            api_url = (
                f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
                f"CN_MarketData.getKLineData?symbol={sina_code}&scale=240&ma=no&datalen={days}"
            )

            logger.info(f"[API调用] 新浪财经历史K线: {sina_code}")

            import time as _time

            api_start = _time.time()

            # 调用新浪历史K线API
            response = self.session.get(api_url, timeout=10)
            response.raise_for_status()

            api_elapsed = _time.time() - api_start

            # 解析返回数据
            content = response.text.strip()
            if not content or 'null' in content or len(content) < 10:
                raise DataFetchError(f"新浪API未找到股票 {stock_code} 的历史数据")

            # 解析JSON数据
            import json

            try:
                kline_data = json.loads(content)
                if not isinstance(kline_data, list) or len(kline_data) == 0:
                    raise DataFetchError(f"新浪API返回的历史数据格式错误")

                # 转换为DataFrame
                df_data = []
                for item in kline_data:
                    try:
                        # 新浪API返回格式：{"day":"2025-10-27","open":"1440.000","high":"1452.490","low":"1435.990","close":"1440.410","volume":"3710239"}
                        row = {
                            'date': item['day'],
                            'open': float(item['open']),
                            'high': float(item['high']),
                            'low': float(item['low']),
                            'close': float(item['close']),
                            'volume': int(item['volume']),
                            'amount': 0.0,  # 新浪API不提供成交额，设为0
                            'pct_chg': 0.0,  # 涨跌幅需要计算
                        }
                        df_data.append(row)
                    except (KeyError, ValueError, TypeError) as e:
                        logger.warning(f"解析K线数据项失败: {item}, 错误: {e}")
                        continue

                if not df_data:
                    raise DataFetchError(f"新浪API历史数据解析后为空")

                # 创建DataFrame
                df = pd.DataFrame(df_data)

                # 确保日期格式正确
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date').reset_index(drop=True)

                # 计算涨跌幅
                if len(df) > 1:
                    df['pct_chg'] = df['close'].pct_change() * 100
                    df['pct_chg'].fillna(0, inplace=True)

                # 标准化数据
                df = self._normalize_data(df, stock_code)

                logger.info(
                    f"[API返回] 新浪财经历史K线 成功: {stock_code} 获取{len(df)}条数据, 耗时 {api_elapsed:.3f}s"
                )
                logger.info(
                    f"[数据范围] {df['date'].min().strftime('%Y-%m-%d')} ~ {df['date'].max().strftime('%Y-%m-%d')}"
                )

                return df

            except json.JSONDecodeError as e:
                raise DataFetchError(f"新浪API历史数据JSON解析失败: {e}")

        except Exception as e:
            error_msg = str(e).lower()

            # 检测反爬封禁
            if any(keyword in error_msg for keyword in ['banned', 'blocked', '频率', 'rate', '限制', '403', '429']):
                logger.warning(f"检测到可能被封禁: {e}")
                raise RateLimitError(f"新浪API可能被限流: {e}") from e

            raise DataFetchError(f"新浪API获取历史数据失败: {e}") from e

    def get_enhanced_data(self, stock_code: str, days: int = 60) -> Dict[str, Any]:
        """
        获取增强数据（实时行情为主）

        Args:
            stock_code: 股票代码
            days: 历史数据天数（新浪API主要提供实时数据）

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

    fetcher = SinaFetcher()

    # 测试实时行情
    print("=" * 50)
    print("测试新浪实时行情获取")
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

    # 测试批量行情
    print("\n" + "=" * 50)
    print("测试新浪批量实时行情获取")
    print("=" * 50)
    try:
        codes = ['600519', '000001', '300750', '002594', '000858']
        quotes = fetcher.get_batch_realtime_quotes(codes)
        print(f"[批量行情] 获取成功，共 {len(quotes)} 只股票")
        for code, quote in quotes.items():
            if quote:
                print(f"  {code} {quote.name}: ¥{quote.price:.2f} ({quote.change_pct:+.2f}%)")
            else:
                print(f"  {code}: 获取失败")
    except Exception as e:
        print(f"[批量行情] 获取失败: {e}")

    # 测试日线数据
    print("\n" + "=" * 50)
    print("测试新浪日线数据获取")
    print("=" * 50)
    try:
        df = fetcher.get_daily_data('600519')  # 茅台
        print(f"[日线数据] 获取成功，共 {len(df)} 条数据")
        print(df.tail())
    except Exception as e:
        print(f"[日线数据] 获取失败: {e}")
