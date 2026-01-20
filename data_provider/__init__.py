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
1. AkshareFetcher (Priority 1) - 最高优先级，默认数据源
2. TushareFetcher (Priority 2) - 来自 tushare 库
3. BaostockFetcher (Priority 3) - 来自 baostock 库
4. YfinanceFetcher (Priority 4) - 来自 yfinance 库
5. EfinanceFetcher (Priority 5) - 来自 efinance 库，仅在明确指定时使用
"""

from .base import BaseFetcher, DataFetcherManager
from .efinance_fetcher import EfinanceFetcher
from .akshare_fetcher import AkshareFetcher
from .tushare_fetcher import TushareFetcher
from .baostock_fetcher import BaostockFetcher
from .yfinance_fetcher import YfinanceFetcher

__all__ = [
    'BaseFetcher',
    'DataFetcherManager',
    'EfinanceFetcher',
    'AkshareFetcher',
    'TushareFetcher',
    'BaostockFetcher',
    'YfinanceFetcher',
]
