# -*- coding: utf-8 -*-
"""
===================================
数据源策略层 - 包初始化
===================================

本包实现策略模式管理多个数据源，实现：
1. 统一的数据获取接口
2. 自动故障切换
3. 防封禁流控策略

数据源优先级：
0.1. SinaFetcher (Priority 0.1) - 极速数据源，新浪财经API
0. TencentFetcher (Priority 0) - 最高优先级，专门用于快速模式
0.5. TonghuashunFetcher (Priority 0.5) - 同花顺数据源，与腾讯并列
1. AkshareFetcher (Priority 1) - 默认数据源
2. TushareFetcher (Priority 2) - 来自 tushare 库
3. BaostockFetcher (Priority 3) - 来自 baostock 库
4. YfinanceFetcher (Priority 4) - 来自 yfinance 库
5. EfinanceFetcher (Priority 5) - 来自 efinance 库，仅在明确指定时使用
"""

from .base import BaseFetcher, DataFetcherManager
from .sina_fetcher import SinaFetcher
from .tencent_fetcher import TencentFetcher
from .tonghuashun_fetcher import TonghuashunFetcher
from .efinance_fetcher import EfinanceFetcher
from .akshare_fetcher import AkshareFetcher
from .tushare_fetcher import TushareFetcher
from .baostock_fetcher import BaostockFetcher
from .yfinance_fetcher import YfinanceFetcher

__all__ = [
    'BaseFetcher',
    'DataFetcherManager',
    'SinaFetcher',
    'TencentFetcher',
    'TonghuashunFetcher',
    'EfinanceFetcher',
    'AkshareFetcher',
    'TushareFetcher',
    'BaostockFetcher',
    'YfinanceFetcher',
]
