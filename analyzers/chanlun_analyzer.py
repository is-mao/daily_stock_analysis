# -*- coding: utf-8 -*-
"""
===================================
缠论技术分析模块
===================================

基于缠中说禅理论的技术分析实现
核心概念：分型、笔、线段、中枢、走势类型、买卖点

参考：
- 缠中说禅《教你炒股票》108课
- ABU量化系统缠论实现
- 缠论核心理论体系

主要功能：
1. 分型识别（顶分型、底分型）
2. 笔的构造与识别
3. 线段的划分
4. 中枢的识别与分析
5. 走势类型判断（上涨、下跌、盘整）
6. 买卖点识别（一二三类买卖点）
7. 背驰分析
"""

import logging
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple, NamedTuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class FenXingType(Enum):
    """分型类型"""

    TOP = "顶分型"  # 顶分型
    BOTTOM = "底分型"  # 底分型
    NONE = "无分型"  # 无分型


class TrendType(Enum):
    """走势类型"""

    UP = "上涨"  # 上涨
    DOWN = "下跌"  # 下跌
    CONSOLIDATION = "盘整"  # 盘整


class BuySellPointType(Enum):
    """买卖点类型"""

    BUY_1 = "第一类买点"  # 第一类买点
    BUY_2 = "第二类买点"  # 第二类买点
    BUY_3 = "第三类买点"  # 第三类买点
    SELL_1 = "第一类卖点"  # 第一类卖点
    SELL_2 = "第二类卖点"  # 第二类卖点
    SELL_3 = "第三类卖点"  # 第三类卖点


@dataclass
class FenXing:
    """分型数据结构"""

    index: int  # K线索引
    date: str  # 日期
    price: float  # 价格（高点用high，低点用low）
    type: FenXingType  # 分型类型
    high: float  # 最高价
    low: float  # 最低价
    close: float  # 收盘价


@dataclass
class Bi:
    """笔数据结构"""

    start_fenxing: FenXing  # 起始分型
    end_fenxing: FenXing  # 结束分型
    direction: str  # 方向：up/down
    strength: float  # 笔的强度（价格变化幅度）
    length: int  # 笔的长度（K线数量）


@dataclass
class ZhongShu:
    """中枢数据结构"""

    high: float  # 中枢上沿
    low: float  # 中枢下沿
    start_index: int  # 开始位置
    end_index: int  # 结束位置
    level: str  # 级别
    bi_count: int  # 构成中枢的笔数量


@dataclass
class BuySellPoint:
    """买卖点数据结构"""

    index: int  # K线索引
    date: str  # 日期
    price: float  # 价格
    type: BuySellPointType  # 买卖点类型
    confidence: float  # 置信度 (0-1)
    reason: str  # 形成原因


class ChanLunAnalyzer:
    """缠论分析器"""

    def __init__(self):
        self.fenxings: List[FenXing] = []
        self.bis: List[Bi] = []
        self.zhongshus: List[ZhongShu] = []
        self.buy_sell_points: List[BuySellPoint] = []

    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        完整的缠论分析

        Args:
            df: K线数据，包含 date, open, high, low, close, volume

        Returns:
            分析结果字典
        """
        try:
            # 数据验证
            if df is None or df.empty:
                logger.warning("缠论分析：输入数据为空")
                return {}

            if len(df) < 10:
                logger.warning(f"缠论分析：数据量不足({len(df)}条)，至少需要10条")
                return {}

            # 检查必需的列
            required_cols = ['date', 'open', 'high', 'low', 'close']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                logger.warning(f"缠论分析：缺少必需列: {missing_cols}")
                return {}

            logger.info(f"开始缠论分析，数据量: {len(df)} 条")

            # 1. 识别分型
            self.fenxings = self._identify_fenxings(df)
            logger.info(f"识别到 {len(self.fenxings)} 个分型")

            # 2. 构造笔
            self.bis = self._construct_bis(self.fenxings)
            logger.info(f"构造了 {len(self.bis)} 笔")

            # 3. 识别中枢
            self.zhongshus = self._identify_zhongshus(self.bis)
            logger.info(f"识别到 {len(self.zhongshus)} 个中枢")

            # 4. 识别买卖点
            self.buy_sell_points = self._identify_buy_sell_points(df, self.bis, self.zhongshus)
            logger.info(f"识别到 {len(self.buy_sell_points)} 个买卖点")

            # 5. 走势类型判断
            trend_type = self._analyze_trend_type(self.bis, self.zhongshus)

            # 6. 背驰分析
            beichi_analysis = self._analyze_beichi(df, self.bis)

            # 7. 生成综合评分
            score = self._calculate_chanlun_score(trend_type, beichi_analysis, self.buy_sell_points)

            return {
                'fenxings': self.fenxings,
                'bis': self.bis,
                'zhongshus': self.zhongshus,
                'buy_sell_points': self.buy_sell_points,
                'trend_type': trend_type,
                'beichi_analysis': beichi_analysis,
                'chanlun_score': score,
                'summary': self._generate_summary(),
            }

        except Exception as e:
            logger.error(f"缠论分析失败: {e}")
            return {}

    def _identify_fenxings(self, df: pd.DataFrame) -> List[FenXing]:
        """识别分型"""
        fenxings = []

        for i in range(1, len(df) - 1):
            current = df.iloc[i]
            prev = df.iloc[i - 1]
            next_row = df.iloc[i + 1]

            # 顶分型：当前K线的高点是三根K线中最高的
            if (
                current['high'] > prev['high']
                and current['high'] > next_row['high']
                and current['low'] > prev['low']
                and current['low'] > next_row['low']
            ):

                fenxing = FenXing(
                    index=i,
                    date=current['date'],
                    price=current['high'],
                    type=FenXingType.TOP,
                    high=current['high'],
                    low=current['low'],
                    close=current['close'],
                )
                fenxings.append(fenxing)

            # 底分型：当前K线的低点是三根K线中最低的
            elif (
                current['low'] < prev['low']
                and current['low'] < next_row['low']
                and current['high'] < prev['high']
                and current['high'] < next_row['high']
            ):

                fenxing = FenXing(
                    index=i,
                    date=current['date'],
                    price=current['low'],
                    type=FenXingType.BOTTOM,
                    high=current['high'],
                    low=current['low'],
                    close=current['close'],
                )
                fenxings.append(fenxing)

        # 过滤相邻同类型分型，保留更极端的
        filtered_fenxings = self._filter_adjacent_fenxings(fenxings)

        return filtered_fenxings

    def _filter_adjacent_fenxings(self, fenxings: List[FenXing]) -> List[FenXing]:
        """过滤相邻的同类型分型，保留更极端的"""
        if len(fenxings) <= 1:
            return fenxings

        filtered = [fenxings[0]]

        for i in range(1, len(fenxings)):
            current = fenxings[i]
            last = filtered[-1]

            # 如果类型相同，保留更极端的
            if current.type == last.type:
                if current.type == FenXingType.TOP:
                    # 顶分型保留更高的
                    if current.price > last.price:
                        filtered[-1] = current
                else:
                    # 底分型保留更低的
                    if current.price < last.price:
                        filtered[-1] = current
            else:
                filtered.append(current)

        return filtered

    def _construct_bis(self, fenxings: List[FenXing]) -> List[Bi]:
        """构造笔"""
        bis = []

        for i in range(len(fenxings) - 1):
            start = fenxings[i]
            end = fenxings[i + 1]

            # 确定方向
            if start.type == FenXingType.BOTTOM and end.type == FenXingType.TOP:
                direction = "up"
            elif start.type == FenXingType.TOP and end.type == FenXingType.BOTTOM:
                direction = "down"
            else:
                continue  # 跳过无效的笔

            # 计算笔的强度和长度
            strength = abs(end.price - start.price) / start.price
            length = end.index - start.index

            bi = Bi(start_fenxing=start, end_fenxing=end, direction=direction, strength=strength, length=length)
            bis.append(bi)

        return bis

    def _identify_zhongshus(self, bis: List[Bi]) -> List[ZhongShu]:
        """识别中枢"""
        zhongshus = []

        # 至少需要3笔才能构成中枢
        if len(bis) < 3:
            return zhongshus

        i = 0
        while i < len(bis) - 2:
            # 尝试构造中枢
            zhongshu = self._try_construct_zhongshu(bis, i)
            if zhongshu:
                zhongshus.append(zhongshu)
                i = zhongshu.end_index
            else:
                i += 1

        return zhongshus

    def _try_construct_zhongshu(self, bis: List[Bi], start_idx: int) -> Optional[ZhongShu]:
        """尝试从指定位置构造中枢"""
        if start_idx + 2 >= len(bis):
            return None

        # 取连续三笔
        bi1, bi2, bi3 = bis[start_idx : start_idx + 3]

        # 计算重叠区间
        # 第一笔和第二笔的重叠
        overlap1_high = min(bi1.end_fenxing.price, bi2.end_fenxing.price)
        overlap1_low = max(bi1.start_fenxing.price, bi2.start_fenxing.price)

        # 第二笔和第三笔的重叠
        overlap2_high = min(bi2.end_fenxing.price, bi3.end_fenxing.price)
        overlap2_low = max(bi2.start_fenxing.price, bi3.start_fenxing.price)

        # 检查是否有重叠
        if overlap1_high <= overlap1_low or overlap2_high <= overlap2_low:
            return None

        # 中枢区间是两个重叠区间的交集
        zhongshu_high = min(overlap1_high, overlap2_high)
        zhongshu_low = max(overlap1_low, overlap2_low)

        if zhongshu_high <= zhongshu_low:
            return None

        # 扩展中枢，看后续笔是否在中枢范围内震荡
        end_idx = start_idx + 2
        bi_count = 3

        for j in range(start_idx + 3, len(bis)):
            bi = bis[j]
            # 如果笔在中枢范围内，扩展中枢
            if (
                bi.start_fenxing.price <= zhongshu_high
                and bi.start_fenxing.price >= zhongshu_low
                and bi.end_fenxing.price <= zhongshu_high
                and bi.end_fenxing.price >= zhongshu_low
            ):
                end_idx = j
                bi_count += 1
            else:
                break

        return ZhongShu(
            high=zhongshu_high,
            low=zhongshu_low,
            start_index=start_idx,
            end_index=end_idx,
            level="5分钟",  # 简化处理，实际应根据K线级别确定
            bi_count=bi_count,
        )

    def _identify_buy_sell_points(
        self, df: pd.DataFrame, bis: List[Bi], zhongshus: List[ZhongShu]
    ) -> List[BuySellPoint]:
        """识别买卖点"""
        points = []

        # 第一类买卖点：趋势的起点和终点
        points.extend(self._identify_first_class_points(bis, zhongshus))

        # 第二类买卖点：回调不创新低/新高的点
        points.extend(self._identify_second_class_points(bis, zhongshus))

        # 第三类买卖点：突破中枢的点
        points.extend(self._identify_third_class_points(bis, zhongshus))

        return sorted(points, key=lambda x: x.index)

    def _identify_first_class_points(self, bis: List[Bi], zhongshus: List[ZhongShu]) -> List[BuySellPoint]:
        """识别第一类买卖点"""
        points = []

        for zhongshu in zhongshus:
            # 第一类买点：下跌趋势结束，形成中枢后的第一个向上笔
            if zhongshu.start_index > 0:
                prev_bi = bis[zhongshu.start_index - 1]
                if prev_bi.direction == "down":
                    # 中枢后的第一个向上笔的起点
                    if zhongshu.end_index + 1 < len(bis):
                        next_bi = bis[zhongshu.end_index + 1]
                        if next_bi.direction == "up":
                            point = BuySellPoint(
                                index=next_bi.start_fenxing.index,
                                date=next_bi.start_fenxing.date,
                                price=next_bi.start_fenxing.price,
                                type=BuySellPointType.BUY_1,
                                confidence=0.8,
                                reason="下跌趋势结束，中枢后向上突破",
                            )
                            points.append(point)

            # 第一类卖点：上涨趋势结束
            if zhongshu.end_index + 1 < len(bis):
                next_bi = bis[zhongshu.end_index + 1]
                if next_bi.direction == "down":
                    point = BuySellPoint(
                        index=next_bi.start_fenxing.index,
                        date=next_bi.start_fenxing.date,
                        price=next_bi.start_fenxing.price,
                        type=BuySellPointType.SELL_1,
                        confidence=0.8,
                        reason="上涨趋势结束，开始下跌",
                    )
                    points.append(point)

        return points

    def _identify_second_class_points(self, bis: List[Bi], zhongshus: List[ZhongShu]) -> List[BuySellPoint]:
        """识别第二类买卖点"""
        points = []

        # 简化实现：在中枢震荡过程中寻找回调不创新低的买点
        for zhongshu in zhongshus:
            for i in range(zhongshu.start_index, zhongshu.end_index):
                if i + 1 < len(bis):
                    bi = bis[i]
                    next_bi = bis[i + 1]

                    # 第二类买点：回调不破中枢下沿
                    if bi.direction == "down" and next_bi.direction == "up" and bi.end_fenxing.price > zhongshu.low:
                        point = BuySellPoint(
                            index=next_bi.start_fenxing.index,
                            date=next_bi.start_fenxing.date,
                            price=next_bi.start_fenxing.price,
                            type=BuySellPointType.BUY_2,
                            confidence=0.6,
                            reason="回调不破中枢下沿",
                        )
                        points.append(point)

                    # 第二类卖点：反弹不破中枢上沿
                    elif bi.direction == "up" and next_bi.direction == "down" and bi.end_fenxing.price < zhongshu.high:
                        point = BuySellPoint(
                            index=next_bi.start_fenxing.index,
                            date=next_bi.start_fenxing.date,
                            price=next_bi.start_fenxing.price,
                            type=BuySellPointType.SELL_2,
                            confidence=0.6,
                            reason="反弹不破中枢上沿",
                        )
                        points.append(point)

        return points

    def _identify_third_class_points(self, bis: List[Bi], zhongshus: List[ZhongShu]) -> List[BuySellPoint]:
        """识别第三类买卖点"""
        points = []

        for zhongshu in zhongshus:
            if zhongshu.end_index + 1 < len(bis):
                next_bi = bis[zhongshu.end_index + 1]

                # 第三类买点：向上突破中枢后的回调
                if next_bi.direction == "up" and next_bi.end_fenxing.price > zhongshu.high:
                    if zhongshu.end_index + 2 < len(bis):
                        callback_bi = bis[zhongshu.end_index + 2]
                        if callback_bi.direction == "down" and callback_bi.end_fenxing.price > zhongshu.high:
                            point = BuySellPoint(
                                index=callback_bi.end_fenxing.index,
                                date=callback_bi.end_fenxing.date,
                                price=callback_bi.end_fenxing.price,
                                type=BuySellPointType.BUY_3,
                                confidence=0.7,
                                reason="向上突破后回调不破中枢",
                            )
                            points.append(point)

                # 第三类卖点：向下突破中枢后的反弹
                elif next_bi.direction == "down" and next_bi.end_fenxing.price < zhongshu.low:
                    if zhongshu.end_index + 2 < len(bis):
                        rebound_bi = bis[zhongshu.end_index + 2]
                        if rebound_bi.direction == "up" and rebound_bi.end_fenxing.price < zhongshu.low:
                            point = BuySellPoint(
                                index=rebound_bi.end_fenxing.index,
                                date=rebound_bi.end_fenxing.date,
                                price=rebound_bi.end_fenxing.price,
                                type=BuySellPointType.SELL_3,
                                confidence=0.7,
                                reason="向下突破后反弹不破中枢",
                            )
                            points.append(point)

        return points

    def _analyze_trend_type(self, bis: List[Bi], zhongshus: List[ZhongShu]) -> TrendType:
        """分析走势类型"""
        if not bis:
            return TrendType.CONSOLIDATION

        # 简化判断：看最近几笔的方向
        recent_bis = bis[-5:] if len(bis) >= 5 else bis

        up_count = sum(1 for bi in recent_bis if bi.direction == "up")
        down_count = sum(1 for bi in recent_bis if bi.direction == "down")

        if up_count > down_count * 1.5:
            return TrendType.UP
        elif down_count > up_count * 1.5:
            return TrendType.DOWN
        else:
            return TrendType.CONSOLIDATION

    def _analyze_beichi(self, df: pd.DataFrame, bis: List[Bi]) -> Dict[str, Any]:
        """背驰分析"""
        if len(bis) < 2:
            return {"has_beichi": False, "type": None, "strength": 0}

        # 简化的背驰分析：比较最近两笔的力度
        last_bi = bis[-1]
        prev_bi = bis[-2] if len(bis) >= 2 else None

        if not prev_bi or last_bi.direction != prev_bi.direction:
            return {"has_beichi": False, "type": None, "strength": 0}

        # 价格背驰：价格创新高/新低，但力度减弱
        price_diff = abs(last_bi.strength - prev_bi.strength) / prev_bi.strength

        has_beichi = False
        beichi_type = None

        if last_bi.direction == "up":
            # 上涨背驰：价格更高但力度更弱
            if last_bi.end_fenxing.price > prev_bi.end_fenxing.price and last_bi.strength < prev_bi.strength * 0.8:
                has_beichi = True
                beichi_type = "上涨背驰"
        else:
            # 下跌背驰：价格更低但力度更弱
            if last_bi.end_fenxing.price < prev_bi.end_fenxing.price and last_bi.strength < prev_bi.strength * 0.8:
                has_beichi = True
                beichi_type = "下跌背驰"

        return {"has_beichi": has_beichi, "type": beichi_type, "strength": price_diff}

    def _calculate_chanlun_score(
        self, trend_type: TrendType, beichi_analysis: Dict[str, Any], buy_sell_points: List[BuySellPoint]
    ) -> float:
        """计算缠论综合评分"""
        score = 50.0  # 基础分

        # 趋势类型加分
        if trend_type == TrendType.UP:
            score += 20
        elif trend_type == TrendType.DOWN:
            score -= 20

        # 背驰分析
        if beichi_analysis.get("has_beichi"):
            if beichi_analysis.get("type") == "下跌背驰":
                score += 15  # 下跌背驰是买入信号
            elif beichi_analysis.get("type") == "上涨背驰":
                score -= 15  # 上涨背驰是卖出信号

        # 买卖点分析
        recent_points = [p for p in buy_sell_points if p.index >= len(buy_sell_points) - 10]
        buy_points = [p for p in recent_points if "买" in p.type.value]
        sell_points = [p for p in recent_points if "卖" in p.type.value]

        if buy_points:
            score += len(buy_points) * 5
        if sell_points:
            score -= len(sell_points) * 5

        return max(0, min(100, score))

    def _generate_summary(self) -> str:
        """生成缠论分析摘要"""
        summary_parts = []

        if self.fenxings:
            summary_parts.append(f"识别到{len(self.fenxings)}个分型")

        if self.bis:
            summary_parts.append(f"构造了{len(self.bis)}笔")

        if self.zhongshus:
            summary_parts.append(f"发现{len(self.zhongshus)}个中枢")

        if self.buy_sell_points:
            buy_count = len([p for p in self.buy_sell_points if "买" in p.type.value])
            sell_count = len([p for p in self.buy_sell_points if "卖" in p.type.value])
            summary_parts.append(f"识别到{buy_count}个买点，{sell_count}个卖点")

        return "，".join(summary_parts) if summary_parts else "缠论分析完成"


def analyze_stock_chanlun(df: pd.DataFrame) -> Dict[str, Any]:
    """
    对股票进行缠论分析的便捷函数

    Args:
        df: K线数据

    Returns:
        缠论分析结果
    """
    analyzer = ChanLunAnalyzer()
    return analyzer.analyze(df)


# 示例使用
if __name__ == "__main__":
    # 这里可以添加测试代码
    pass
