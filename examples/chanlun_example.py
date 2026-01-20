#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论分析使用示例

展示如何使用缠论分析模块进行股票技术分析
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzers.chanlun_analyzer import ChanLunAnalyzer, analyze_stock_chanlun
from data_provider.akshare_fetcher import AkshareFetcher
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)


def analyze_stock_with_chanlun(stock_code: str):
    """使用缠论分析指定股票"""
    print(f"🌊 对 {stock_code} 进行缠论分析")
    print("=" * 60)

    try:
        # 获取股票数据
        fetcher = AkshareFetcher()
        df, source = fetcher.get_daily_data(stock_code, days=120)

        if df is None or len(df) < 30:
            print(f"❌ 无法获取 {stock_code} 的数据")
            return

        print(f"📊 数据来源: {source}")
        print(f"📈 数据范围: {df['date'].iloc[0]} 至 {df['date'].iloc[-1]}")
        print(f"📏 数据长度: {len(df)} 条K线")
        print(f"💰 价格区间: {df['low'].min():.2f} - {df['high'].max():.2f}")

        # 进行缠论分析
        result = analyze_stock_chanlun(df)

        if not result:
            print("❌ 缠论分析失败")
            return

        # 显示分析结果
        print(f"\n🔍 缠论分析结果:")
        print(f"分型数量: {len(result.get('fenxings', []))}")
        print(f"笔数量: {len(result.get('bis', []))}")
        print(f"中枢数量: {len(result.get('zhongshus', []))}")
        print(f"买卖点数量: {len(result.get('buy_sell_points', []))}")
        print(f"走势类型: {result.get('trend_type', '未知')}")
        print(f"缠论评分: {result.get('chanlun_score', 0):.1f}/100")

        # 详细分型信息
        fenxings = result.get('fenxings', [])
        if fenxings:
            print(f"\n📍 最近5个分型:")
            for fx in fenxings[-5:]:
                emoji = "🔺" if fx.type.value == "顶分型" else "🔻"
                print(f"  {emoji} {fx.date}: {fx.type.value} @ {fx.price:.2f}")

        # 中枢信息
        zhongshus = result.get('zhongshus', [])
        if zhongshus:
            print(f"\n🎯 中枢信息:")
            for i, zs in enumerate(zhongshus[-3:], 1):  # 显示最近3个中枢
                print(f"  中枢{i}: [{zs.low:.2f} - {zs.high:.2f}] (包含{zs.bi_count}笔)")

        # 买卖点信息
        buy_sell_points = result.get('buy_sell_points', [])
        if buy_sell_points:
            print(f"\n💰 最近买卖点:")
            recent_points = buy_sell_points[-5:]  # 最近5个点
            for point in recent_points:
                emoji = "🟢" if "买" in point.type.value else "🔴"
                print(f"  {emoji} {point.date}: {point.type.value} @ {point.price:.2f}")
                print(f"     置信度: {point.confidence:.1f}, 原因: {point.reason}")

        # 背驰分析
        beichi = result.get('beichi_analysis', {})
        if beichi.get('has_beichi'):
            emoji = "⚠️" if beichi.get('type') == "上涨背驰" else "💡"
            print(f"\n{emoji} 背驰分析: {beichi.get('type')}")
            print(f"   背驰强度: {beichi.get('strength', 0):.2f}")
        else:
            print(f"\n✅ 背驰分析: 当前无明显背驰")

        # 投资建议
        print(f"\n💡 缠论投资建议:")
        score = result.get('chanlun_score', 50)
        trend = result.get('trend_type', '')

        if score >= 70:
            print("   🔥 强烈推荐: 缠论信号积极，适合买入")
        elif score >= 60:
            print("   🟢 推荐: 缠论信号较好，可以考虑买入")
        elif score >= 40:
            print("   🟡 观望: 缠论信号中性，建议等待更好时机")
        else:
            print("   🔴 回避: 缠论信号偏弱，建议谨慎")

        if hasattr(trend, 'value'):
            trend_str = trend.value
        else:
            trend_str = str(trend)

        if trend_str == "上涨":
            print("   📈 趋势: 当前处于上涨趋势")
        elif trend_str == "下跌":
            print("   📉 趋势: 当前处于下跌趋势")
        else:
            print("   📊 趋势: 当前处于盘整状态")

        print(f"\n📝 {result.get('summary', '分析完成')}")

    except Exception as e:
        print(f"❌ 分析失败: {e}")
        import traceback

        traceback.print_exc()


def main():
    """主函数"""
    print("🌊 缠论分析示例")
    print("基于缠中说禅理论的股票技术分析")
    print("=" * 60)

    # 示例股票列表
    example_stocks = [
        "600519",  # 贵州茅台
        "300750",  # 宁德时代
        "000858",  # 五粮液
    ]

    print("📋 将分析以下股票:")
    for i, code in enumerate(example_stocks, 1):
        print(f"  {i}. {code}")

    print("\n" + "=" * 60)

    # 逐个分析
    for code in example_stocks:
        analyze_stock_with_chanlun(code)
        print("\n" + "=" * 60)

    print("🎉 缠论分析示例完成！")
    print("\n💡 缠论核心概念:")
    print("• 分型: 局部高低点，是构成笔的基础")
    print("• 笔: 连接相邻异类分型的直线")
    print("• 中枢: 某级别走势类型中，被至少三个连续次级别走势类型所重叠的部分")
    print("• 买卖点: 基于走势结构和中枢关系确定的交易时机")
    print("• 背驰: 价格创新高/低但力度减弱，预示趋势可能转折")


if __name__ == "__main__":
    main()
