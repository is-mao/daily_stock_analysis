# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - 股票精选模块
===================================

职责：
1. 从全市场股票池中筛选出值得关注的股票
2. 基于技术面、基本面、消息面多维度评分
3. 提供分级推荐（强烈推荐/推荐/关注）
4. 支持多种筛选策略和条件组合

筛选理念：
- 技术面：多头排列 + 乖离率安全 + 量能配合
- 基本面：业绩稳定 + 行业景气 + 估值合理
- 消息面：无重大利空 + 有利好催化
- 流动性：日成交额 > 1亿，避免流动性陷阱
"""

import logging
import time
import random
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np

from config import get_config
from storage import get_db
from data_provider import DataFetcherManager
from data_provider.akshare_fetcher import AkshareFetcher
from analyzer import GeminiAnalyzer, AnalysisResult
from analyzers.chanlun_analyzer import analyze_stock_chanlun

logger = logging.getLogger(__name__)


class RecommendLevel(Enum):
    """推荐级别"""

    STRONG_BUY = "强烈推荐"  # 90-100分
    BUY = "推荐"  # 75-89分
    WATCH = "关注"  # 60-74分
    HOLD = "观望"  # 40-59分
    AVOID = "回避"  # 0-39分


class SelectionStrategy(Enum):
    """筛选策略"""

    TREND_FOLLOWING = "趋势跟踪"  # 多头排列 + 突破
    VALUE_HUNTING = "价值挖掘"  # 低估值 + 基本面好
    MOMENTUM = "动量策略"  # 强势股 + 量价配合
    REVERSAL = "反转策略"  # 超跌反弹 + 技术修复
    COMPREHENSIVE = "综合策略"  # 多维度综合评分


@dataclass
class StockScore:
    """股票评分数据"""

    code: str
    name: str

    # 分项评分 (0-100)
    technical_score: float = 0.0  # 技术面评分
    fundamental_score: float = 0.0  # 基本面评分
    sentiment_score: float = 0.0  # 情绪面评分
    liquidity_score: float = 0.0  # 流动性评分

    # 综合评分
    total_score: float = 0.0  # 总分 (0-100)
    recommend_level: RecommendLevel = RecommendLevel.HOLD

    # 关键指标
    current_price: float = 0.0
    ma5: float = 0.0
    ma10: float = 0.0
    ma20: float = 0.0
    volume_ratio: float = 0.0  # 量比
    turnover_rate: float = 0.0  # 换手率
    pe_ratio: float = 0.0  # 市盈率
    pb_ratio: float = 0.0  # 市净率

    # 买卖点位
    buy_price: float = 0.0  # 建议买入价
    stop_loss: float = 0.0  # 止损价
    target_price: float = 0.0  # 目标价

    # 推荐理由
    reason: str = ""
    risk_warning: str = ""

    # 技术分析详情
    technical_details: Dict[str, Any] = None

    def __post_init__(self):
        """初始化后处理"""
        if self.technical_details is None:
            self.technical_details = {}

    def get_emoji(self) -> str:
        """获取推荐级别对应的emoji"""
        emoji_map = {
            RecommendLevel.STRONG_BUY: "🔥",
            RecommendLevel.BUY: "🟢",
            RecommendLevel.WATCH: "🟡",
            RecommendLevel.HOLD: "⚪",
            RecommendLevel.AVOID: "🔴",
        }
        return emoji_map.get(self.recommend_level, "⚪")


class StockSelector:
    """
    股票精选器

    职责：
    1. 从全市场筛选优质股票
    2. 多维度评分排序
    3. 生成每日精选报告
    """

    def __init__(self, config=None, fast_mode=False):
        self.config = config or get_config()
        self.db = get_db()
        self.fetcher_manager = DataFetcherManager()
        self.akshare_fetcher = AkshareFetcher()
        self.analyzer = GeminiAnalyzer()

        # 数据源配置
        self.preferred_data_source = 'auto'  # 默认自动选择

        # 快速模式配置
        self.fast_mode = fast_mode
        if fast_mode:
            logger.info("🚀 启用快速模式：减少延时和股票数量")

        # 筛选参数
        self.min_market_cap = 50e8  # 最小市值50亿
        self.min_daily_amount = 1e8  # 最小日成交额1亿
        self.max_pe_ratio = 50  # 最大市盈率
        self.min_volume_ratio = 1.2  # 最小量比

        logger.info("股票精选器初始化完成")

    def get_stock_pool(self) -> List[str]:
        """
        获取股票池 - 优化版：只分析前20个热点板块，每个板块前20只股票

        Returns:
            股票代码列表（最多400只：20板块 × 20股票）
        """
        try:
            logger.info("开始获取热点板块股票池...")

            # 获取热点板块股票
            hot_sector_stocks = self._get_hot_sector_stocks()
            if hot_sector_stocks:
                logger.info(f"热点板块股票池获取成功，共 {len(hot_sector_stocks)} 只股票")
                return hot_sector_stocks

            # 如果获取热点板块失败，使用备选方案
            logger.warning("热点板块获取失败，使用备选股票池")
            return self._get_fallback_stock_pool()

        except Exception as e:
            logger.error(f"获取股票池失败: {e}")
            return self._get_fallback_stock_pool()

    def _get_hot_sector_stocks(self) -> List[str]:
        """
        获取热点板块股票

        策略：
        1. 获取概念板块涨跌幅排行
        2. 选择前20个热点板块
        3. 每个板块选择前20只股票（按涨跌幅或成交额排序）

        Returns:
            股票代码列表
        """
        try:
            import akshare as ak

            # 获取概念板块涨跌幅排行
            logger.info("获取概念板块排行...")
            concept_df = ak.stock_board_concept_name_em()

            if concept_df is None or concept_df.empty:
                logger.warning("无法获取概念板块数据")
                return []

            # 选择前20个热点板块（按涨跌幅排序）
            # 快速模式只选择前10个板块
            sector_count = 10 if self.fast_mode else 20
            hot_concepts = concept_df.head(sector_count)
            logger.info(f"选择前{sector_count}个热点板块: {list(hot_concepts['板块名称'])}")

            all_stocks = []

            for idx, row in hot_concepts.iterrows():
                concept_name = row['板块名称']
                try:
                    logger.info(f"获取板块 [{concept_name}] 的股票...")

                    # 获取板块内股票
                    concept_stocks_df = ak.stock_board_concept_cons_em(symbol=concept_name)

                    if concept_stocks_df is None or concept_stocks_df.empty:
                        logger.warning(f"板块 [{concept_name}] 无股票数据")
                        continue

                    # 选择前20只股票（按涨跌幅排序）
                    # 快速模式只选择前10只
                    stock_count = 10 if self.fast_mode else 20
                    top_stocks = concept_stocks_df.head(stock_count)
                    stock_codes = top_stocks['代码'].tolist()

                    logger.info(f"板块 [{concept_name}] 获取 {len(stock_codes)} 只股票")
                    all_stocks.extend(stock_codes)

                    # 防止请求过快，快速模式减少延时
                    sleep_time = random.uniform(0.3, 0.8) if self.fast_mode else random.uniform(1, 2)
                    time.sleep(sleep_time)

                except Exception as e:
                    logger.error(f"获取板块 [{concept_name}] 股票失败: {e}")
                    continue

            # 去重
            unique_stocks = list(set(all_stocks))

            # 快速模式进一步限制股票数量
            if self.fast_mode and len(unique_stocks) > 50:
                # 快速模式最多只分析50只股票
                unique_stocks = unique_stocks[:50]
                logger.info(f"🚀 快速模式：股票池限制为 {len(unique_stocks)} 只")

            logger.info(f"热点板块股票池构建完成，去重后共 {len(unique_stocks)} 只股票")

            return unique_stocks

        except Exception as e:
            logger.error(f"获取热点板块股票失败: {e}")
            return []

    def _get_fallback_stock_pool(self) -> List[str]:
        """
        备选股票池：精选各行业龙头股

        当热点板块获取失败时使用，包含各行业代表性股票
        """
        # 快速模式使用更小的备选池
        if self.fast_mode:
            return [
                # 核心龙头股（快速模式精选）
                '600519',  # 贵州茅台
                '300750',  # 宁德时代
                '000858',  # 五粮液
                '002594',  # 比亚迪
                '600036',  # 招商银行
                '000001',  # 平安银行
                '601012',  # 隆基绿能
                '688599',  # 天合光能
                '002460',  # 赣锋锂业
                '300014',  # 亿纬锂能
                '600809',  # 山西汾酒
                '000799',  # 酒鬼酒
                '002304',  # 洋河股份
                '000596',  # 古井贡酒
                '601166',  # 兴业银行
            ]

        return [
            # 白酒龙头
            '600519',
            '000858',
            '000596',
            '002304',
            '600809',
            '000799',
            # 新能源汽车
            '300750',
            '002594',
            '601012',
            '688599',
            '002460',
            '300014',
            # 银行
            '600036',
            '000001',
            '601166',
            '600000',
            '601328',
            '000002',
            # 科技龙头
            '000002',
            '002415',
            '300059',
            '002475',
            '600570',
            '002241',
            # 医药生物
            '600276',
            '000661',
            '300760',
            '688111',
            '300347',
            '002821',
            # 消费品
            '000333',
            '600887',
            '002714',
            '603288',
            '600519',
            '000568',
            # 地产建筑
            '600048',
            '001979',
            '000069',
            '600340',
            '000002',
            '601668',
            # 军工
            '600893',
            '002013',
            '000768',
            '600038',
            '002179',
            '600150',
            # 化工
            '600309',
            '002648',
            '000792',
            '600426',
            '002601',
            '600160',
            # 机械设备
            '000157',
            '002008',
            '300014',
            '002202',
            '000425',
            '600031',
            # 电力设备
            '300274',
            '002129',
            '300316',
            '688005',
            '002459',
            '300450',
            # 食品饮料
            '000858',
            '600887',
            '000895',
            '002568',
            '600779',
            '000729',
            # 家电
            '000333',
            '000651',
            '002032',
            '600690',
            '002050',
            '000921',
            # 汽车
            '601633',
            '000625',
            '600104',
            '002594',
            '000800',
            '601238',
            # 钢铁有色
            '600019',
            '000709',
            '002460',
            '600362',
            '000831',
            '002466',
            # 煤炭石油
            '601088',
            '600188',
            '601898',
            '600348',
            '000983',
            '600123',
            # 交通运输
            '600115',
            '600026',
            '000089',
            '600009',
            '002352',
            '600317',
            # 通信
            '000063',
            '600050',
            '000938',
            '002415',
            '600498',
            '000997',
            # 计算机
            '002415',
            '300059',
            '002410',
            '300496',
            '002230',
            '300033',
            # 传媒
            '300251',
            '002555',
            '300413',
            '000156',
            '002739',
            '300364',
        ]

    def calculate_technical_score(self, df: pd.DataFrame, code: str) -> Tuple[float, Dict[str, Any]]:
        """
        计算技术面评分

        评分维度：
        1. 均线排列 (25分)
        2. 乖离率安全性 (20分)
        3. 量能配合 (20分)
        4. K线形态 (15分)
        5. 缠论分析 (20分) - 新增

        Args:
            df: 股票历史数据
            code: 股票代码

        Returns:
            Tuple[技术面评分, 详细指标]
        """
        if df is None or len(df) < 30:
            return 0.0, {}

        try:
            # 计算技术指标
            df = df.copy()
            df['ma5'] = df['close'].rolling(5).mean()
            df['ma10'] = df['close'].rolling(10).mean()
            df['ma20'] = df['close'].rolling(20).mean()
            df['ma60'] = df['close'].rolling(60).mean()

            latest = df.iloc[-1]
            current_price = latest['close']
            ma5 = latest['ma5']
            ma10 = latest['ma10']
            ma20 = latest['ma20']
            ma60 = latest['ma60']

            score = 0.0
            details = {'current_price': current_price, 'ma5': ma5, 'ma10': ma10, 'ma20': ma20, 'ma60': ma60}

            # 1. 均线排列评分 (25分)
            ma_score = 0
            if ma5 > ma10 > ma20:  # 多头排列
                ma_score = 25
            elif ma5 > ma10:  # 短期多头
                ma_score = 18
            elif ma5 < ma10 < ma20:  # 空头排列
                ma_score = 0
            else:  # 震荡
                ma_score = 10

            score += ma_score
            details['ma_alignment'] = "多头排列" if ma5 > ma10 > ma20 else "震荡" if ma5 > ma10 else "空头排列"

            # 2. 乖离率安全性 (20分)
            bias_ma5 = (current_price - ma5) / ma5 * 100
            bias_ma20 = (current_price - ma20) / ma20 * 100

            bias_score = 0
            if -2 <= bias_ma5 <= 3:  # 乖离率安全区间
                bias_score = 20
            elif -5 <= bias_ma5 <= 5:  # 可接受区间
                bias_score = 12
            elif bias_ma5 > 8:  # 严重偏离，追高风险
                bias_score = 0
            else:  # 超跌
                bias_score = 8

            score += bias_score
            details['bias_ma5'] = bias_ma5
            details['bias_ma20'] = bias_ma20

            # 3. 量能配合 (20分)
            volume_ma5 = df['volume'].rolling(5).mean().iloc[-1]
            volume_ma20 = df['volume'].rolling(20).mean().iloc[-1]
            current_volume = latest['volume']

            volume_score = 0
            if current_volume > volume_ma5 * 1.5:  # 明显放量
                volume_score = 20
            elif current_volume > volume_ma5:  # 温和放量
                volume_score = 16
            elif current_volume > volume_ma20 * 0.8:  # 正常量能
                volume_score = 12
            else:  # 缩量
                volume_score = 4

            score += volume_score
            details['volume_ratio_calc'] = current_volume / volume_ma5

            # 4. K线形态 (15分)
            pattern_score = 0
            recent_5 = df.tail(5)

            # 连续上涨
            if (recent_5['close'] > recent_5['close'].shift(1)).sum() >= 3:
                pattern_score = 15
            # 震荡上行
            elif recent_5['close'].iloc[-1] > recent_5['close'].iloc[0]:
                pattern_score = 12
            # 横盘整理
            elif abs(recent_5['close'].iloc[-1] - recent_5['close'].iloc[0]) / recent_5['close'].iloc[0] < 0.03:
                pattern_score = 8
            else:
                pattern_score = 4

            score += pattern_score
            details['pattern'] = "上涨趋势" if pattern_score >= 12 else "震荡" if pattern_score >= 8 else "下跌趋势"

            # 5. 缠论分析 (20分) - 新增
            chanlun_score = 0
            chanlun_details = {}

            try:
                # 进行缠论分析
                chanlun_result = analyze_stock_chanlun(df)
                if chanlun_result:
                    # 基于缠论评分
                    chanlun_base_score = chanlun_result.get('chanlun_score', 50)
                    chanlun_score = (chanlun_base_score - 50) * 0.4  # 转换为-20到20分
                    chanlun_score = max(0, min(20, chanlun_score + 10))  # 调整为0-20分

                    # 买卖点加分
                    buy_sell_points = chanlun_result.get('buy_sell_points', [])
                    recent_buy_points = [p for p in buy_sell_points if '买' in p.type.value and p.index >= len(df) - 5]
                    if recent_buy_points:
                        chanlun_score = min(20, chanlun_score + len(recent_buy_points) * 2)

                    # 背驰分析
                    beichi = chanlun_result.get('beichi_analysis', {})
                    if beichi.get('has_beichi') and beichi.get('type') == '下跌背驰':
                        chanlun_score = min(20, chanlun_score + 5)

                    chanlun_details = {
                        'trend_type': (
                            chanlun_result.get('trend_type', '').value
                            if hasattr(chanlun_result.get('trend_type', ''), 'value')
                            else str(chanlun_result.get('trend_type', ''))
                        ),
                        'zhongshu_count': len(chanlun_result.get('zhongshus', [])),
                        'buy_points': len([p for p in buy_sell_points if '买' in p.type.value]),
                        'sell_points': len([p for p in buy_sell_points if '卖' in p.type.value]),
                        'has_beichi': beichi.get('has_beichi', False),
                        'beichi_type': beichi.get('type', '无'),
                    }
                else:
                    chanlun_score = 10  # 默认中性分数

            except Exception as e:
                logger.warning(f"[{code}] 缠论分析失败: {e}")
                chanlun_score = 10  # 默认中性分数
                chanlun_details = {'error': str(e)}

            score += chanlun_score
            details['chanlun'] = chanlun_details
            details['chanlun_score'] = chanlun_score

            return min(score, 100.0), details

        except Exception as e:
            logger.error(f"[{code}] 计算技术面评分失败: {e}")
            return 0.0, {}

    def calculate_fundamental_score(self, code: str) -> Tuple[float, Dict[str, Any]]:
        """
        计算基本面评分

        评分维度：
        1. 估值水平 (40分)
        2. 盈利能力 (30分)
        3. 成长性 (30分)

        Args:
            code: 股票代码

        Returns:
            Tuple[基本面评分, 详细指标]
        """
        try:
            # 获取基本面数据
            fundamental_data = self.akshare_fetcher.get_fundamental_data(code)
            if not fundamental_data:
                return 50.0, {}  # 默认中性评分

            score = 0.0
            details = fundamental_data.copy()

            pe_ratio = fundamental_data.get('pe_ratio', 0)
            pb_ratio = fundamental_data.get('pb_ratio', 0)
            roe = fundamental_data.get('roe', 0)
            revenue_growth = fundamental_data.get('revenue_growth', 0)

            # 1. 估值水平 (40分)
            valuation_score = 0
            if 0 < pe_ratio <= 15:  # 低估值
                valuation_score = 40
            elif 15 < pe_ratio <= 25:  # 合理估值
                valuation_score = 30
            elif 25 < pe_ratio <= 40:  # 偏高估值
                valuation_score = 20
            elif pe_ratio > 40:  # 高估值
                valuation_score = 10

            # PB修正
            if 0 < pb_ratio <= 2:
                valuation_score += 5
            elif pb_ratio > 5:
                valuation_score -= 5

            score += valuation_score

            # 2. 盈利能力 (30分)
            profitability_score = 0
            if roe >= 15:  # 优秀
                profitability_score = 30
            elif roe >= 10:  # 良好
                profitability_score = 25
            elif roe >= 5:  # 一般
                profitability_score = 15
            else:  # 较差
                profitability_score = 5

            score += profitability_score

            # 3. 成长性 (30分)
            growth_score = 0
            if revenue_growth >= 20:  # 高成长
                growth_score = 30
            elif revenue_growth >= 10:  # 稳定成长
                growth_score = 25
            elif revenue_growth >= 0:  # 正增长
                growth_score = 15
            else:  # 负增长
                growth_score = 5

            score += growth_score

            return min(score, 100.0), details

        except Exception as e:
            logger.error(f"[{code}] 计算基本面评分失败: {e}")
            return 50.0, {}

    def calculate_liquidity_score(self, df: pd.DataFrame, code: str) -> Tuple[float, Dict[str, Any]]:
        """
        计算流动性评分

        评分维度：
        1. 成交额 (50分)
        2. 换手率 (30分)
        3. 量比 (20分)

        Args:
            df: 股票历史数据
            code: 股票代码

        Returns:
            Tuple[流动性评分, 详细指标]
        """
        if df is None or len(df) < 5:
            return 0.0, {}

        try:
            latest = df.iloc[-1]
            daily_amount = latest.get('amount', 0)

            score = 0.0
            details = {'daily_amount': daily_amount}

            # 1. 成交额评分 (50分)
            amount_score = 0
            if daily_amount >= 10e8:  # 10亿以上
                amount_score = 50
            elif daily_amount >= 5e8:  # 5-10亿
                amount_score = 40
            elif daily_amount >= 2e8:  # 2-5亿
                amount_score = 30
            elif daily_amount >= 1e8:  # 1-2亿
                amount_score = 20
            else:  # 1亿以下
                amount_score = 0

            score += amount_score

            # 2. 获取实时数据补充流动性指标
            try:
                realtime_quote = self.akshare_fetcher.get_realtime_quote(code)
                if realtime_quote:
                    turnover_rate = realtime_quote.turnover_rate
                    volume_ratio = realtime_quote.volume_ratio

                    # 换手率评分 (30分)
                    turnover_score = 0
                    if 2 <= turnover_rate <= 8:  # 适中换手
                        turnover_score = 30
                    elif 1 <= turnover_rate <= 12:  # 可接受范围
                        turnover_score = 20
                    elif turnover_rate > 15:  # 过度投机
                        turnover_score = 5
                    else:  # 换手不足
                        turnover_score = 10

                    score += turnover_score

                    # 量比评分 (20分)
                    volume_ratio_score = 0
                    if 1.2 <= volume_ratio <= 3:  # 温和放量
                        volume_ratio_score = 20
                    elif 1 <= volume_ratio <= 5:  # 可接受范围
                        volume_ratio_score = 15
                    elif volume_ratio > 5:  # 异常放量
                        volume_ratio_score = 5
                    else:  # 缩量
                        volume_ratio_score = 10

                    score += volume_ratio_score

                    details.update({'turnover_rate': turnover_rate, 'volume_ratio': volume_ratio})

            except Exception as e:
                logger.warning(f"[{code}] 获取实时流动性数据失败: {e}")
                score += 25  # 给默认分数

            return min(score, 100.0), details

        except Exception as e:
            logger.error(f"[{code}] 计算流动性评分失败: {e}")
            return 0.0, {}

    def evaluate_stock(self, code: str) -> Optional[StockScore]:
        """
        评估单只股票

        Args:
            code: 股票代码

        Returns:
            StockScore 或 None
        """
        try:
            logger.info(f"开始评估股票 {code}")

            # 获取历史数据（支持指定数据源）
            if self.preferred_data_source == 'efinance':
                # 使用EFinance数据源（最快）
                from data_provider.efinance_fetcher import EfinanceFetcher

                efinance_fetcher = EfinanceFetcher()
                df = efinance_fetcher.get_daily_data(code, days=60)
                source = "EfinanceFetcher"
                logger.info(f"[{code}] 使用EFinance数据源获取数据")
            elif self.preferred_data_source == 'akshare':
                # 使用AkShare数据源
                df = self.akshare_fetcher.get_daily_data(code, days=60)
                source = "AkshareFetcher"
                logger.info(f"[{code}] 使用AkShare数据源获取数据")
            else:
                # 使用默认的数据源管理器（自动选择）
                df, source = self.fetcher_manager.get_daily_data(code, days=60)

            if df is None or len(df) < 30:
                logger.warning(f"[{code}] 历史数据不足，跳过评估")
                return None

            # 获取股票名称
            stock_name = self.akshare_fetcher.get_stock_name(code)
            if not stock_name:
                stock_name = f"股票{code}"

            # 计算各维度评分
            technical_score, tech_details = self.calculate_technical_score(df, code)
            fundamental_score, fund_details = self.calculate_fundamental_score(code)
            liquidity_score, liquid_details = self.calculate_liquidity_score(df, code)

            # 综合评分 (权重分配)
            weights = {
                'technical': 0.4,  # 技术面权重40%
                'fundamental': 0.35,  # 基本面权重35%
                'liquidity': 0.25,  # 流动性权重25%
            }

            total_score = (
                technical_score * weights['technical']
                + fundamental_score * weights['fundamental']
                + liquidity_score * weights['liquidity']
            )

            # 确定推荐级别
            if total_score >= 90:
                recommend_level = RecommendLevel.STRONG_BUY
            elif total_score >= 75:
                recommend_level = RecommendLevel.BUY
            elif total_score >= 60:
                recommend_level = RecommendLevel.WATCH
            elif total_score >= 40:
                recommend_level = RecommendLevel.HOLD
            else:
                recommend_level = RecommendLevel.AVOID

            # 计算买卖点位
            current_price = tech_details.get('current_price', 0)
            ma5 = tech_details.get('ma5', current_price)
            ma10 = tech_details.get('ma10', current_price)

            buy_price = min(ma5, current_price * 0.98)  # 买入价：MA5或当前价格的98%
            stop_loss = ma10 * 0.95  # 止损价：MA10的95%
            target_price = current_price * 1.15  # 目标价：当前价格的115%

            # 生成推荐理由
            reason_parts = []
            if technical_score >= 75:
                reason_parts.append("技术面强势")
            if fundamental_score >= 75:
                reason_parts.append("基本面优秀")
            if liquidity_score >= 75:
                reason_parts.append("流动性充足")

            reason = "、".join(reason_parts) if reason_parts else "综合评分达标"

            # 风险提示
            risk_warnings = []
            if tech_details.get('bias_ma5', 0) > 5:
                risk_warnings.append("乖离率偏高，注意追高风险")
            if fund_details.get('pe_ratio', 0) > 40:
                risk_warnings.append("估值偏高，注意回调风险")

            risk_warning = "；".join(risk_warnings) if risk_warnings else ""

            # 创建评分对象
            stock_score = StockScore(
                code=code,
                name=stock_name,
                technical_score=technical_score,
                fundamental_score=fundamental_score,
                sentiment_score=0.0,  # 暂时不计算情绪面
                liquidity_score=liquidity_score,
                total_score=total_score,
                recommend_level=recommend_level,
                current_price=current_price,
                ma5=ma5,
                ma10=ma10,
                ma20=tech_details.get('ma20', current_price),
                volume_ratio=liquid_details.get('volume_ratio', 0),
                turnover_rate=liquid_details.get('turnover_rate', 0),
                pe_ratio=fund_details.get('pe_ratio', 0),
                pb_ratio=fund_details.get('pb_ratio', 0),
                buy_price=buy_price,
                stop_loss=stop_loss,
                target_price=target_price,
                reason=reason,
                risk_warning=risk_warning,
                technical_details=tech_details,  # 保存技术分析详情
            )

            logger.info(f"[{code}] {stock_name} 评估完成: {total_score:.1f}分 ({recommend_level.value})")
            return stock_score

        except Exception as e:
            logger.error(f"[{code}] 股票评估失败: {e}")
            return None

    def select_daily_stocks(
        self, strategy: SelectionStrategy = SelectionStrategy.COMPREHENSIVE, max_stocks: int = 20
    ) -> List[StockScore]:
        """
        每日股票精选 - 优化版

        从热点板块中精选优质股票，大大减少分析时间

        Args:
            strategy: 筛选策略
            max_stocks: 最大返回股票数量

        Returns:
            精选股票列表（按评分排序）
        """
        logger.info(f"开始每日股票精选，策略: {strategy.value}，最大数量: {max_stocks}")

        # 获取热点板块股票池（最多400只）
        stock_pool = self.get_stock_pool()
        logger.info(f"热点板块股票池大小: {len(stock_pool)}")

        if not stock_pool:
            logger.error("股票池为空，无法进行精选")
            return []

        # 如果股票池仍然很大，进一步筛选
        # 快速模式使用更小的股票池
        max_pool_size = 50 if self.fast_mode else 200

        if len(stock_pool) > max_pool_size:
            # 优先选择市值适中的股票（避免过小和过大的股票）
            filtered_pool = self._filter_by_market_cap(stock_pool)
            if filtered_pool:
                stock_pool = filtered_pool[:max_pool_size]
                logger.info(f"按市值筛选后，股票池缩减至: {len(stock_pool)} 只")
            else:
                # 如果市值筛选失败，直接截取
                stock_pool = stock_pool[:max_pool_size]
                logger.info(f"直接截取股票池至: {len(stock_pool)} 只")

        selected_stocks = []
        total_stocks = len(stock_pool)

        # 逐个评估股票
        for i, code in enumerate(stock_pool):
            try:
                progress = f"{i+1}/{total_stocks}"
                logger.info(f"评估进度: {progress} - {code}")

                stock_score = self.evaluate_stock(code)
                if stock_score and stock_score.total_score >= 60:  # 只保留60分以上的股票
                    selected_stocks.append(stock_score)
                    logger.info(f"✅ {code} 入选，评分: {stock_score.total_score:.1f}")
                else:
                    logger.debug(f"❌ {code} 未达标，评分: {stock_score.total_score if stock_score else 0:.1f}")

                # 防止请求过快，但减少延时
                # 快速模式进一步减少延时
                if self.fast_mode:
                    time.sleep(random.uniform(0.1, 0.3))
                else:
                    time.sleep(random.uniform(0.5, 1.5))

                # 如果已经找到足够多的优质股票，可以提前结束
                # 快速模式更早结束
                early_stop_count = max_stocks if self.fast_mode else max_stocks * 2
                if len(selected_stocks) >= early_stop_count:
                    logger.info(f"已找到 {len(selected_stocks)} 只优质股票，提前结束筛选")
                    break

            except Exception as e:
                logger.error(f"评估股票 {code} 时出错: {e}")
                continue

        # 按评分排序
        selected_stocks.sort(key=lambda x: x.total_score, reverse=True)

        # 返回前N只
        result = selected_stocks[:max_stocks]

        logger.info(f"股票精选完成！共筛选出 {len(result)} 只优质股票")
        if result:
            logger.info("精选结果预览:")
            for i, stock in enumerate(result[:5]):  # 显示前5只
                logger.info(
                    f"  {i+1}. {stock.name}({stock.code}): {stock.total_score:.1f}分 - {stock.recommend_level.value}"
                )

        # 二次筛选：过滤掉创业板(300)和科创板(688)，选出前20只可操作股票
        tradeable_stocks = self._filter_tradeable_stocks(result)

        # 将可操作股票信息添加到结果中，用于通知
        if hasattr(self, '_tradeable_stocks'):
            self._tradeable_stocks = tradeable_stocks
        else:
            # 如果没有这个属性，直接设置
            self._tradeable_stocks = tradeable_stocks

        return result

    def _filter_by_market_cap(self, stock_codes: List[str]) -> List[str]:
        """
        按市值筛选股票

        优先选择市值适中的股票（50亿-5000亿）

        Args:
            stock_codes: 股票代码列表

        Returns:
            筛选后的股票代码列表
        """
        try:
            filtered_codes = []

            for code in stock_codes:
                try:
                    # 获取实时行情（包含市值信息）
                    quote = self.akshare_fetcher.get_realtime_quote(code)
                    if quote and quote.total_mv > 0:
                        # 市值范围：50亿-5000亿
                        market_cap_billion = quote.total_mv / 1e8  # 转换为亿元
                        if 50 <= market_cap_billion <= 5000:
                            filtered_codes.append(code)

                    # 防止请求过快
                    time.sleep(0.2)

                except Exception as e:
                    logger.debug(f"获取 {code} 市值信息失败: {e}")
                    # 如果获取失败，仍然保留该股票
                    filtered_codes.append(code)

            logger.info(f"市值筛选完成: {len(stock_codes)} -> {len(filtered_codes)}")
            return filtered_codes

        except Exception as e:
            logger.error(f"市值筛选失败: {e}")
            return stock_codes  # 返回原列表

    def _filter_tradeable_stocks(self, selected_stocks: List[StockScore]) -> List[StockScore]:
        """
        二次筛选：过滤掉创业板(300)和科创板(688)股票，选出前20只可操作股票

        Args:
            selected_stocks: 初步精选的股票列表

        Returns:
            可操作的股票列表（最多20只）
        """
        try:
            logger.info("开始二次筛选：过滤创业板和科创板股票...")

            # 过滤掉创业板(300)和科创板(688)
            tradeable_stocks = []
            filtered_out = []

            for stock in selected_stocks:
                code = stock.code
                if code.startswith('300') or code.startswith('688'):
                    filtered_out.append(f"{stock.name}({code})")
                else:
                    tradeable_stocks.append(stock)

            # 记录过滤信息
            if filtered_out:
                logger.info(f"过滤掉创业板/科创板股票 {len(filtered_out)} 只: {', '.join(filtered_out[:5])}")
                if len(filtered_out) > 5:
                    logger.info(f"  还有 {len(filtered_out) - 5} 只...")

            # 选择前20只可操作股票
            top_tradeable = tradeable_stocks[:20]

            logger.info(f"二次筛选完成：可操作股票 {len(top_tradeable)} 只")
            if top_tradeable:
                logger.info("🎯 前20只可操作股票:")
                for i, stock in enumerate(top_tradeable):
                    emoji = stock.get_emoji()
                    logger.info(
                        f"  {i+1:2d}. {emoji} {stock.name}({stock.code}): "
                        f"{stock.total_score:.1f}分 - {stock.recommend_level.value} - ¥{stock.current_price:.2f}"
                    )

            return top_tradeable

        except Exception as e:
            logger.error(f"二次筛选失败: {e}")
            return selected_stocks[:20]  # 返回前20只原始结果

    def generate_selection_report(self, selected_stocks: List[StockScore]) -> str:
        """
        生成精选报告

        Args:
            selected_stocks: 精选股票列表

        Returns:
            Markdown格式的报告
        """
        if not selected_stocks:
            return "今日暂无符合条件的精选股票"

        report_lines = []

        # 报告标题
        today = datetime.now().strftime('%Y-%m-%d')
        report_lines.append(f"# 🎯 {today} 每日股票精选")
        report_lines.append("")

        # 统计信息
        strong_buy = len([s for s in selected_stocks if s.recommend_level == RecommendLevel.STRONG_BUY])
        buy = len([s for s in selected_stocks if s.recommend_level == RecommendLevel.BUY])
        watch = len([s for s in selected_stocks if s.recommend_level == RecommendLevel.WATCH])

        report_lines.append(
            f"**精选统计**: 共{len(selected_stocks)}只 | 🔥强推:{strong_buy} 🟢推荐:{buy} 🟡关注:{watch}"
        )
        report_lines.append("")

        # 添加可操作股票专区（排除创业板300和科创板688）
        tradeable_stocks = getattr(self, '_tradeable_stocks', [])
        if tradeable_stocks:
            report_lines.append("## 🎯 可操作股票推荐 (前20只，已排除创业板300/科创板688)")
            report_lines.append("")
            report_lines.append("*以下股票可直接操作，无需担心交易限制*")
            report_lines.append("")

            for i, stock in enumerate(tradeable_stocks, 1):
                emoji = stock.get_emoji()
                report_lines.append(f"**{i:2d}. {emoji} {stock.name}({stock.code})**")
                report_lines.append(f"   📊 评分: {stock.total_score:.1f}分 | 推荐: {stock.recommend_level.value}")
                report_lines.append(
                    f"   💰 价格: ¥{stock.current_price:.2f} | 操作: 买入¥{stock.buy_price:.2f} 止损¥{stock.stop_loss:.2f}"
                )

                # 添加关键指标
                if stock.volume_ratio > 0:
                    report_lines.append(
                        f"   📈 量比: {stock.volume_ratio:.2f} | 换手: {stock.turnover_rate:.2f}% | PE: {stock.pe_ratio:.1f}"
                    )

                # 添加缠论分析简要信息
                if stock.technical_details and 'chanlun' in stock.technical_details:
                    chanlun_info = stock.technical_details['chanlun']
                    if not chanlun_info.get('error'):
                        chanlun_summary = []
                        if chanlun_info.get('trend_type'):
                            trend_emoji = {"上涨": "📈", "下跌": "📉", "盘整": "📊"}.get(
                                chanlun_info['trend_type'], "📊"
                            )
                            chanlun_summary.append(f"{trend_emoji}{chanlun_info['trend_type']}")

                        if chanlun_info.get('buy_points', 0) > 0:
                            chanlun_summary.append(f"🟢{chanlun_info['buy_points']}买点")

                        if chanlun_info.get('has_beichi') and "下跌" in chanlun_info.get('beichi_type', ''):
                            chanlun_summary.append("💡下跌背驰")

                        if chanlun_summary:
                            report_lines.append(f"   🌊 缠论: {' '.join(chanlun_summary)}")

                report_lines.append("")

            report_lines.append("---")
            report_lines.append("")

        # 完整精选结果分级展示
        for level in [RecommendLevel.STRONG_BUY, RecommendLevel.BUY, RecommendLevel.WATCH]:
            level_stocks = [s for s in selected_stocks if s.recommend_level == level]
            if not level_stocks:
                continue

            report_lines.append(f"## {level.value} ({len(level_stocks)}只)")
            report_lines.append("")

            for stock in level_stocks:
                emoji = stock.get_emoji()
                report_lines.append(f"### {emoji} {stock.name}({stock.code})")
                report_lines.append(f"**综合评分**: {stock.total_score:.1f}分")
                report_lines.append(f"**当前价格**: ¥{stock.current_price:.2f}")
                report_lines.append(
                    f"**操作建议**: 买入¥{stock.buy_price:.2f} | 止损¥{stock.stop_loss:.2f} | 目标¥{stock.target_price:.2f}"
                )

                # 分项评分
                report_lines.append(
                    f"**技术面**: {stock.technical_score:.1f}分 | **基本面**: {stock.fundamental_score:.1f}分 | **流动性**: {stock.liquidity_score:.1f}分"
                )

                # 缠论分析详情
                if stock.technical_details and 'chanlun' in stock.technical_details:
                    chanlun_info = stock.technical_details['chanlun']
                    if not chanlun_info.get('error'):
                        report_lines.append(f"**🌊 缠论分析**: {stock.technical_details.get('chanlun_score', 0):.1f}分")

                        # 缠论详情
                        chanlun_details = []
                        if chanlun_info.get('trend_type'):
                            trend_emoji = {"上涨": "📈", "下跌": "📉", "盘整": "📊"}.get(
                                chanlun_info['trend_type'], "📊"
                            )
                            chanlun_details.append(f"{trend_emoji}{chanlun_info['trend_type']}")

                        if chanlun_info.get('zhongshu_count', 0) > 0:
                            chanlun_details.append(f"中枢{chanlun_info['zhongshu_count']}个")

                        buy_points = chanlun_info.get('buy_points', 0)
                        sell_points = chanlun_info.get('sell_points', 0)
                        if buy_points > 0:
                            chanlun_details.append(f"🟢买点{buy_points}个")
                        if sell_points > 0:
                            chanlun_details.append(f"🔴卖点{sell_points}个")

                        if chanlun_info.get('has_beichi'):
                            beichi_type = chanlun_info.get('beichi_type', '未知')
                            beichi_emoji = "💡" if "下跌" in beichi_type else "⚠️"
                            chanlun_details.append(f"{beichi_emoji}{beichi_type}")

                        if chanlun_details:
                            report_lines.append(f"   *{' | '.join(chanlun_details)}*")

                # 关键指标
                if stock.volume_ratio > 0:
                    report_lines.append(
                        f"**量比**: {stock.volume_ratio:.2f} | **换手率**: {stock.turnover_rate:.2f}% | **PE**: {stock.pe_ratio:.1f}"
                    )

                # 推荐理由
                if stock.reason:
                    report_lines.append(f"**推荐理由**: {stock.reason}")

                # 风险提示
                if stock.risk_warning:
                    report_lines.append(f"**风险提示**: {stock.risk_warning}")

                report_lines.append("")

        # 免责声明
        report_lines.append("---")
        report_lines.append("**免责声明**: 本报告仅供参考，不构成投资建议。股市有风险，投资需谨慎。")

        return "\n".join(report_lines)
