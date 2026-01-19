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

logger = logging.getLogger(__name__)


class RecommendLevel(Enum):
    """推荐级别"""
    STRONG_BUY = "强烈推荐"      # 90-100分
    BUY = "推荐"               # 75-89分  
    WATCH = "关注"             # 60-74分
    HOLD = "观望"              # 40-59分
    AVOID = "回避"             # 0-39分


class SelectionStrategy(Enum):
    """筛选策略"""
    TREND_FOLLOWING = "趋势跟踪"    # 多头排列 + 突破
    VALUE_HUNTING = "价值挖掘"      # 低估值 + 基本面好
    MOMENTUM = "动量策略"           # 强势股 + 量价配合
    REVERSAL = "反转策略"           # 超跌反弹 + 技术修复
    COMPREHENSIVE = "综合策略"       # 多维度综合评分


@dataclass
class StockScore:
    """股票评分数据"""
    code: str
    name: str
    
    # 分项评分 (0-100)
    technical_score: float = 0.0      # 技术面评分
    fundamental_score: float = 0.0    # 基本面评分
    sentiment_score: float = 0.0      # 情绪面评分
    liquidity_score: float = 0.0      # 流动性评分
    
    # 综合评分
    total_score: float = 0.0          # 总分 (0-100)
    recommend_level: RecommendLevel = RecommendLevel.HOLD
    
    # 关键指标
    current_price: float = 0.0
    ma5: float = 0.0
    ma10: float = 0.0
    ma20: float = 0.0
    volume_ratio: float = 0.0         # 量比
    turnover_rate: float = 0.0        # 换手率
    pe_ratio: float = 0.0             # 市盈率
    pb_ratio: float = 0.0             # 市净率
    
    # 买卖点位
    buy_price: float = 0.0            # 建议买入价
    stop_loss: float = 0.0            # 止损价
    target_price: float = 0.0         # 目标价
    
    # 推荐理由
    reason: str = ""
    risk_warning: str = ""
    
    def get_emoji(self) -> str:
        """获取推荐级别对应的emoji"""
        emoji_map = {
            RecommendLevel.STRONG_BUY: "🔥",
            RecommendLevel.BUY: "🟢", 
            RecommendLevel.WATCH: "🟡",
            RecommendLevel.HOLD: "⚪",
            RecommendLevel.AVOID: "🔴"
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
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.db = get_db()
        self.fetcher_manager = DataFetcherManager()
        self.akshare_fetcher = AkshareFetcher()
        self.analyzer = GeminiAnalyzer()
        
        # 筛选参数
        self.min_market_cap = 50e8        # 最小市值50亿
        self.min_daily_amount = 1e8       # 最小日成交额1亿
        self.max_pe_ratio = 50            # 最大市盈率
        self.min_volume_ratio = 1.2       # 最小量比
        
        logger.info("股票精选器初始化完成")
    
    def get_stock_pool(self) -> List[str]:
        """
        获取股票池
        
        从全市场中筛选出基础条件合格的股票
        
        Returns:
            股票代码列表
        """
        try:
            logger.info("开始获取股票池...")
            
            # 获取A股基本信息
            stock_basic = self.akshare_fetcher.get_stock_basic()
            if stock_basic is None or stock_basic.empty:
                logger.warning("无法获取股票基本信息，使用默认股票池")
                return self._get_default_stock_pool()
            
            # 基础筛选条件
            filtered_stocks = stock_basic[
                (stock_basic['market_cap'] >= self.min_market_cap) &  # 市值筛选
                (stock_basic['pe_ratio'] > 0) &                       # 有效市盈率
                (stock_basic['pe_ratio'] <= self.max_pe_ratio) &      # 市盈率上限
                (~stock_basic['code'].str.startswith('688')) &        # 排除科创板
                (~stock_basic['code'].str.startswith('30')) &         # 排除创业板（可选）
                (stock_basic['status'] == '正常')                      # 正常交易
            ]
            
            stock_codes = filtered_stocks['code'].tolist()
            logger.info(f"股票池筛选完成，共 {len(stock_codes)} 只股票")
            
            # 如果股票太多，随机采样
            if len(stock_codes) > 500:
                stock_codes = random.sample(stock_codes, 500)
                logger.info(f"股票池过大，随机采样至 {len(stock_codes)} 只")
            
            return stock_codes
            
        except Exception as e:
            logger.error(f"获取股票池失败: {e}")
            return self._get_default_stock_pool()
    
    def _get_default_stock_pool(self) -> List[str]:
        """获取默认股票池（热门股票）"""
        return [
            # 白酒
            '600519', '000858', '000596', '002304',
            # 新能源
            '300750', '002594', '601012', '688599',
            # 银行
            '600036', '000001', '601166', '600000',
            # 科技
            '000002', '002415', '300059', '002475',
            # 医药
            '600276', '000661', '300760', '688111',
            # 消费
            '000333', '600887', '002714', '603288',
            # 地产
            '600048', '001979', '000069', '600340',
            # 军工
            '600893', '002013', '000768', '600038',
            # 化工
            '600309', '002648', '000792', '600426',
            # 机械
            '000157', '002008', '300014', '002202'
        ]
    
    def calculate_technical_score(self, df: pd.DataFrame, code: str) -> Tuple[float, Dict[str, Any]]:
        """
        计算技术面评分
        
        评分维度：
        1. 均线排列 (30分)
        2. 乖离率安全性 (25分) 
        3. 量能配合 (25分)
        4. K线形态 (20分)
        
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
            details = {
                'current_price': current_price,
                'ma5': ma5,
                'ma10': ma10,
                'ma20': ma20,
                'ma60': ma60
            }
            
            # 1. 均线排列评分 (30分)
            ma_score = 0
            if ma5 > ma10 > ma20:  # 多头排列
                ma_score = 30
            elif ma5 > ma10:       # 短期多头
                ma_score = 20
            elif ma5 < ma10 < ma20:  # 空头排列
                ma_score = 0
            else:                  # 震荡
                ma_score = 10
            
            score += ma_score
            details['ma_alignment'] = "多头排列" if ma5 > ma10 > ma20 else "震荡" if ma5 > ma10 else "空头排列"
            
            # 2. 乖离率安全性 (25分)
            bias_ma5 = (current_price - ma5) / ma5 * 100
            bias_ma20 = (current_price - ma20) / ma20 * 100
            
            bias_score = 0
            if -2 <= bias_ma5 <= 3:      # 乖离率安全区间
                bias_score = 25
            elif -5 <= bias_ma5 <= 5:    # 可接受区间
                bias_score = 15
            elif bias_ma5 > 8:           # 严重偏离，追高风险
                bias_score = 0
            else:                        # 超跌
                bias_score = 10
            
            score += bias_score
            details['bias_ma5'] = bias_ma5
            details['bias_ma20'] = bias_ma20
            
            # 3. 量能配合 (25分)
            volume_ma5 = df['volume'].rolling(5).mean().iloc[-1]
            volume_ma20 = df['volume'].rolling(20).mean().iloc[-1]
            current_volume = latest['volume']
            
            volume_score = 0
            if current_volume > volume_ma5 * 1.5:      # 明显放量
                volume_score = 25
            elif current_volume > volume_ma5:          # 温和放量
                volume_score = 20
            elif current_volume > volume_ma20 * 0.8:   # 正常量能
                volume_score = 15
            else:                                      # 缩量
                volume_score = 5
            
            score += volume_score
            details['volume_ratio_calc'] = current_volume / volume_ma5
            
            # 4. K线形态 (20分)
            pattern_score = 0
            recent_5 = df.tail(5)
            
            # 连续上涨
            if (recent_5['close'] > recent_5['close'].shift(1)).sum() >= 3:
                pattern_score = 20
            # 震荡上行
            elif recent_5['close'].iloc[-1] > recent_5['close'].iloc[0]:
                pattern_score = 15
            # 横盘整理
            elif abs(recent_5['close'].iloc[-1] - recent_5['close'].iloc[0]) / recent_5['close'].iloc[0] < 0.03:
                pattern_score = 10
            else:
                pattern_score = 5
            
            score += pattern_score
            details['pattern'] = "上涨趋势" if pattern_score >= 15 else "震荡" if pattern_score >= 10 else "下跌趋势"
            
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
            if 0 < pe_ratio <= 15:          # 低估值
                valuation_score = 40
            elif 15 < pe_ratio <= 25:       # 合理估值
                valuation_score = 30
            elif 25 < pe_ratio <= 40:       # 偏高估值
                valuation_score = 20
            elif pe_ratio > 40:             # 高估值
                valuation_score = 10
            
            # PB修正
            if 0 < pb_ratio <= 2:
                valuation_score += 5
            elif pb_ratio > 5:
                valuation_score -= 5
            
            score += valuation_score
            
            # 2. 盈利能力 (30分)
            profitability_score = 0
            if roe >= 15:                   # 优秀
                profitability_score = 30
            elif roe >= 10:                 # 良好
                profitability_score = 25
            elif roe >= 5:                  # 一般
                profitability_score = 15
            else:                           # 较差
                profitability_score = 5
            
            score += profitability_score
            
            # 3. 成长性 (30分)
            growth_score = 0
            if revenue_growth >= 20:        # 高成长
                growth_score = 30
            elif revenue_growth >= 10:      # 稳定成长
                growth_score = 25
            elif revenue_growth >= 0:       # 正增长
                growth_score = 15
            else:                           # 负增长
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
            if daily_amount >= 10e8:        # 10亿以上
                amount_score = 50
            elif daily_amount >= 5e8:       # 5-10亿
                amount_score = 40
            elif daily_amount >= 2e8:       # 2-5亿
                amount_score = 30
            elif daily_amount >= 1e8:       # 1-2亿
                amount_score = 20
            else:                           # 1亿以下
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
                    if 2 <= turnover_rate <= 8:      # 适中换手
                        turnover_score = 30
                    elif 1 <= turnover_rate <= 12:   # 可接受范围
                        turnover_score = 20
                    elif turnover_rate > 15:         # 过度投机
                        turnover_score = 5
                    else:                            # 换手不足
                        turnover_score = 10
                    
                    score += turnover_score
                    
                    # 量比评分 (20分)
                    volume_ratio_score = 0
                    if 1.2 <= volume_ratio <= 3:     # 温和放量
                        volume_ratio_score = 20
                    elif 1 <= volume_ratio <= 5:     # 可接受范围
                        volume_ratio_score = 15
                    elif volume_ratio > 5:           # 异常放量
                        volume_ratio_score = 5
                    else:                            # 缩量
                        volume_ratio_score = 10
                    
                    score += volume_ratio_score
                    
                    details.update({
                        'turnover_rate': turnover_rate,
                        'volume_ratio': volume_ratio
                    })
                
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
            
            # 获取历史数据
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
                'technical': 0.4,      # 技术面权重40%
                'fundamental': 0.35,   # 基本面权重35%
                'liquidity': 0.25      # 流动性权重25%
            }
            
            total_score = (
                technical_score * weights['technical'] +
                fundamental_score * weights['fundamental'] +
                liquidity_score * weights['liquidity']
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
            stop_loss = ma10 * 0.95                     # 止损价：MA10的95%
            target_price = current_price * 1.15         # 目标价：当前价格的115%
            
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
                risk_warning=risk_warning
            )
            
            logger.info(f"[{code}] {stock_name} 评估完成: {total_score:.1f}分 ({recommend_level.value})")
            return stock_score
            
        except Exception as e:
            logger.error(f"[{code}] 股票评估失败: {e}")
            return None
    
    def select_daily_stocks(
        self, 
        strategy: SelectionStrategy = SelectionStrategy.COMPREHENSIVE,
        max_stocks: int = 20
    ) -> List[StockScore]:
        """
        每日股票精选
        
        Args:
            strategy: 筛选策略
            max_stocks: 最大返回股票数量
            
        Returns:
            精选股票列表（按评分排序）
        """
        logger.info(f"开始每日股票精选，策略: {strategy.value}，最大数量: {max_stocks}")
        
        # 获取股票池
        stock_pool = self.get_stock_pool()
        logger.info(f"股票池大小: {len(stock_pool)}")
        
        # 为了演示，先从股票池中随机选择一部分进行评估
        # 实际使用中可以根据需要调整
        if len(stock_pool) > 100:
            sample_stocks = random.sample(stock_pool, 100)
            logger.info(f"从股票池中随机采样 {len(sample_stocks)} 只股票进行评估")
        else:
            sample_stocks = stock_pool
        
        selected_stocks = []
        
        # 逐个评估股票
        for i, code in enumerate(sample_stocks):
            try:
                logger.info(f"评估进度: {i+1}/{len(sample_stocks)} - {code}")
                
                stock_score = self.evaluate_stock(code)
                if stock_score and stock_score.total_score >= 60:  # 只保留60分以上的股票
                    selected_stocks.append(stock_score)
                
                # 防止请求过快
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                logger.error(f"评估股票 {code} 时出错: {e}")
                continue
        
        # 按评分排序
        selected_stocks.sort(key=lambda x: x.total_score, reverse=True)
        
        # 返回前N只
        result = selected_stocks[:max_stocks]
        
        logger.info(f"股票精选完成，共筛选出 {len(result)} 只优质股票")
        return result
    
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
        
        report_lines.append(f"**精选统计**: 共{len(selected_stocks)}只 | 🔥强推:{strong_buy} 🟢推荐:{buy} 🟡关注:{watch}")
        report_lines.append("")
        
        # 分级展示
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
                report_lines.append(f"**操作建议**: 买入¥{stock.buy_price:.2f} | 止损¥{stock.stop_loss:.2f} | 目标¥{stock.target_price:.2f}")
                
                # 分项评分
                report_lines.append(f"**技术面**: {stock.technical_score:.1f}分 | **基本面**: {stock.fundamental_score:.1f}分 | **流动性**: {stock.liquidity_score:.1f}分")
                
                # 关键指标
                if stock.volume_ratio > 0:
                    report_lines.append(f"**量比**: {stock.volume_ratio:.2f} | **换手率**: {stock.turnover_rate:.2f}% | **PE**: {stock.pe_ratio:.1f}")
                
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