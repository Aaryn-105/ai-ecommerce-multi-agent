import re
content = open("backend/services/report_polisher.py", "r", encoding="utf-8").read()

# Check that the file is readable
print("File length:", len(content))

# Update product_analysis
pa_replacement = (
    '"product_analysis": (\n'
    '        "[选品场景专项要求]\\n"\n'
    '        "- \u8f93\u51fa\u5019\u9009\u5546\u54c1\u539f\u59cb\u6307\u6807\u8868\uff08\u4ef7\u683c/\u8bc4\u5206/\u8bc4\u4ef7\u6570/\u7efc\u5408\u5f97\u5206/\u63a8\u8350\u7b49\u7ea7\uff09\u3002\\n"\n'
    '        "- \u6309\u7167\u539f\u59cb\u6307\u6807->Min-Max\u5f52\u4e00\u5316->\u52a0\u6743\u8d21\u732e\u5206\u89e3->\u7efc\u5408\u8bc4\u5206\u56db\u6b65\u8f93\u51fa\u9009\u54c1\u6a21\u578b\u3002\\n"\n'
    '        "- \u6bcf\u4e2a\u7ef4\u5ea6\u9700\u8bf4\u660e\uff1a\u6307\u6807\u5b9a\u4e49\u3001\u8ba1\u7b97\u516c\u5f0f\u3001\u6743\u91cd\u3001\u6570\u636e\u6765\u6e90\u3002\\n"\n'
    '        "- \u5f52\u4e00\u5316\u77e9\u9635\u9700\u6ce8\u660e\u6bcf\u5217\u6700\u5927\u503c\u6765\u6e90\uff1b\u52a0\u6743\u8d21\u732e\u8868\u9700\u663e\u793a\u6bcf\u4e2a\u7ef4\u5ea6\u5bf9\u6700\u7ec8\u5206\u6570\u7684\u8d21\u732e\u503c\u548c\u8d21\u732e\u5360\u6bd4\u3002\\n"\n'
    '        "- \u5212\u5206\u5f3a\u52bf\u63a8\u8350(>=70\u5206)/\u63a8\u8350(40-70\u5206)/\u5907\u9009(<40\u5206)\u4e09\u7ea7\u3002\\n"\n'
    '        "- \u4f30\u7b97 30 \u5929 GMV \u533a\u95f4\uff08\u4e0b\u9650/\u4e0a\u9650\uff09\uff1b\u9884\u6d4b\u9500\u91cf > \u5e93\u5b58 80% \u65f6\u6807\u6ce8\u7ea2\u8272\u65ad\u8d27\u9884\u8b66\u3002\\n"\n'
    '        "- \u5bf9 Top 1 \u5546\u54c1\u7ed9\u51fa A/B \u6d4b\u8bd5\u5efa\u8bae\uff08\u5982\u964d\u4ef7 5% vs \u8d60\u54c1\u6346\u7ed1\uff09\u3002\\n"\n'
    '        "- \u5728\u4ef7\u683c\u5e26\u5206\u5e03\u3001\u7efc\u5408\u8bc4\u5206\u67f1\u72b6\u56fe\u3001\u8f6c\u5316\u6f0f\u6597\u5904\u63d2\u5165[\u56fe\u8868\u5360\u4f4d]\u8bf4\u660e\u3002"\n'
    '    ),'
)

old_pa = (
    '"product_analysis": (\n'
    '        "[选品场景专项要求]\\n"\n'
    '        "- 输出候选商品原始指标表（价格/评分/销量/库存/综合得分）。\\n"\n'
    '        "- 输出加权评分模型，划分\'强势推荐/推荐/备选\'三级。\\n"\n'
    '        "- 估算 30 天 GMV 区间；预测销量 > 库存 80% 时标注断货预警。\\n"\n'
    '        "- 对 Top 1 商品给出 A/B 测试建议（如降价 5% vs 赠品）。"\n'
    '    ),'
)

if old_pa in content:
    content = content.replace(old_pa, pa_replacement)
    print("product_analysis updated")
else:
    print("product_analysis NOT FOUND")

# Update trend_forecast
tf_replacement = (
    '"trend_forecast": (\n'
    '        "[趋势预测场景专项要求]\\n"\n'
    '        "- 按 7 天/30 天窗口列预测销量、置信度、拟合模型、WAPE误差。\\n"\n'
    '        "- 划分上升期/稳定期/衰退期，并给出对应运营动作（上升期扩量、稳定期维持、衰退期捆绑销售）。\\n"\n'
    '        "- 评分 x 置信度二维矩阵：高评高置信=必胜品，高评低置信=小流量测试，低评高置信=需优化商品页。\\n"\n'
    '        "- 标注所采用的预测模型及模型适用性说明。"\n'
    '    ),'
)

old_tf = (
    '"trend_forecast": (\n'
    '        "[趋势预测场景专项要求]\\n"\n'
    '        "- 按 7 天/30 天窗口列预测销量与置信度。\\n"\n'
    '        "- 划分上升期/稳定期/衰退期，并给出对应运营动作。\\n"\n'
    '        "- 评分 x 置信度二维矩阵：高评高置信=必胜品，高评低置信=小流量测试。"\n'
    '    ),'
)

if old_tf in content:
    content = content.replace(old_tf, tf_replacement)
    print("trend_forecast updated")
else:
    print("trend_forecast NOT FOUND")

# Update competitor_analysis
ca_replacement = (
    '"competitor_analysis": (\n'
    '        "[竞品对比场景专项要求]\\n"\n'
    '        "- 价格带分布（<10/10-50/50-100/100+）与目标商品在其中的百分位定位。\\n"\n'
    '        "- 核心维度对比矩阵（价格/评分/销量/品牌力/差异化卖点）。\\n"\n'
    '        "- 竞品优劣势分析：每个竞品的2-3个核心优势和劣势。\\n"\n'
    '        "- 应对策略：差异化话术方向、避其锋芒的价格策略或跟随策略。\\n"\n'
    '        "- 缺口分析：市场中未被充分满足的需求点。"\n'
    '    ),'
)

old_ca = (
    '"competitor_analysis": (\n'
    '        "[竞品对比场景专项要求]\\n"\n'
    '        "- 价格带分布（<10/10-50/50-100/>100）与本次商品百分位。\\n"\n'
    '        "- 评分/销量/差异化对比矩阵。\\n"\n'
    '        "- 应对策略：差异化话术、避其锋芒或价格跟随。"\n'
    '    ),'
)

if old_ca in content:
    content = content.replace(old_ca, ca_replacement)
    print("competitor_analysis updated")
else:
    print("competitor_analysis NOT FOUND")

# Now write the file
open("backend/services/report_polisher.py", "w", encoding="utf-8").write(content)
print("Write OK, total length:", len(content))
