#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===================================
股票精选功能演示脚本
===================================

演示如何使用股票精选功能
"""

import logging
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from stock_selector import StockSelector, SelectionStrategy, RecommendLevel
from config import get_config

# 配置简单日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)

logger = logging.getLogger(__name__)


def demo_stock_selection():
    """演示股票精选功能"""
    print("=" * 60)
    print("🎯 A股智能分析系统 - 股票精选功能演示")
    print("=" * 60)
    
    try:
        # 创建配置和精选器
        config = get_config()
        selector = StockSelector(config=config)
        
        print("\n📊 功能特性:")
        print("• 多维度评分：技术面(40%) + 基本面(35%) + 流动性(25%)")
        print("• 分级推荐：🔥强推(90+) 🟢推荐(75-89) 🟡关注(60-74)")
        print("• 精确点位：买入价、止损价、目标价")
        print("• 风险提示：自动识别追高风险、估值风险")
        
        print("\n🔍 开始演示股票评估...")
        
        # 演示股票列表（知名股票）
        demo_stocks = [
            ('600519', '贵州茅台'),
            ('000001', '平安银行'), 
            ('300750', '宁德时代'),
            ('002594', '比亚迪'),
            ('600036', '招商银行')
        ]
        
        results = []
        
        for code, name in demo_stocks:
            print(f"\n📈 正在评估: {name}({code})")
            
            try:
                stock_score = selector.evaluate_stock(code)
                
                if stock_score:
                    results.append(stock_score)
                    emoji = stock_score.get_emoji()
                    
                    print(f"   {emoji} 综合评分: {stock_score.total_score:.1f}分")
                    print(f"   📊 推荐级别: {stock_score.recommend_level.value}")
                    print(f"   💰 当前价格: ¥{stock_score.current_price:.2f}")
                    print(f"   📈 技术面: {stock_score.technical_score:.1f} | "
                          f"基本面: {stock_score.fundamental_score:.1f} | "
                          f"流动性: {stock_score.liquidity_score:.1f}")
                    
                    if stock_score.reason:
                        print(f"   ✅ 推荐理由: {stock_score.reason}")
                    
                    if stock_score.risk_warning:
                        print(f"   ⚠️  风险提示: {stock_score.risk_warning}")
                        
                else:
                    print(f"   ❌ 评估失败")
                    
            except Exception as e:
                print(f"   ❌ 评估出错: {e}")
        
        # 显示排序结果
        if results:
            print("\n" + "=" * 60)
            print("📊 评估结果排序 (按评分降序)")
            print("=" * 60)
            
            # 按评分排序
            results.sort(key=lambda x: x.total_score, reverse=True)
            
            for i, stock in enumerate(results, 1):
                emoji = stock.get_emoji()
                print(f"{i}. {emoji} {stock.name}({stock.code})")
                print(f"   评分: {stock.total_score:.1f} | 级别: {stock.recommend_level.value}")
                print(f"   价格: ¥{stock.current_price:.2f} | 操作: 买入¥{stock.buy_price:.2f}")
                print()
            
            # 生成简化报告
            print("=" * 60)
            print("📋 精选报告预览")
            print("=" * 60)
            
            # 统计各级别数量
            strong_buy = len([s for s in results if s.recommend_level == RecommendLevel.STRONG_BUY])
            buy = len([s for s in results if s.recommend_level == RecommendLevel.BUY])
            watch = len([s for s in results if s.recommend_level == RecommendLevel.WATCH])
            
            print(f"🎯 演示精选统计: 共{len(results)}只 | 🔥强推:{strong_buy} 🟢推荐:{buy} 🟡关注:{watch}")
            print()
            
            # 显示前3只
            for stock in results[:3]:
                emoji = stock.get_emoji()
                print(f"{emoji} {stock.recommend_level.value} | {stock.name}({stock.code})")
                print(f"📌 综合评分{stock.total_score:.1f}分，当前价格¥{stock.current_price:.2f}")
                print(f"💰 操作建议: 买入¥{stock.buy_price:.2f} | 止损¥{stock.stop_loss:.2f} | 目标¥{stock.target_price:.2f}")
                if stock.reason:
                    print(f"✅ {stock.reason}")
                print()
        
        print("=" * 60)
        print("🚀 演示完成！")
        print()
        print("💡 使用方法:")
        print("   python main.py --stock-selection")
        print("   python main.py --stock-selection --selection-count 30")
        print("   python main.py --stock-selection --selection-strategy trend_following")
        print()
        print("📖 详细文档: STOCK_SELECTION_GUIDE.md")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    demo_stock_selection()