# -*- coding: utf-8 -*-
"""
消息面分析器

负责股票消息面分析，包括新闻、公告等信息的情感分析和评分。

Copyright (c) 2026 stock selector. All rights reserved.
"""

import logging
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("stock_selector.analyzer.news")


class NewsAnalyzer:
    """
    消息面分析器

    分析维度：
    - 新闻关键词分析（利好/利空）
    - 情感评分计算
    - 市场情绪判断
    - 政策影响分析
    - 宏观环境分析
    """

    POSITIVE_KEYWORDS = {
        '上涨': 2, '利好': 3, '增长': 2, '盈利': 2, '创新': 1,
        '突破': 2, '政策支持': 3, '订单': 1, '合作': 1, '并购': 2,
        '业绩预增': 3, '分红': 2, '回购': 2, '增持': 2,
        '涨停': 3, '创新高': 2, '景气': 2, '复苏': 2, '扩张': 1,
        '超预期': 2, '大幅增长': 3, '市场份额提升': 2, '技术领先': 2,
        '产能扩张': 2, '签订大单': 2, '产业链整合': 2, '国产替代': 2
    }

    NEGATIVE_KEYWORDS = {
        '下跌': -2, '利空': -3, '亏损': -2, '下滑': -2, '风险': -1,
        '警告': -2, '政策限制': -3, '诉讼': -2, '违规': -3, '减持': -1,
        '业绩预亏': -3, '质押': -1, '冻结': -2,
        '跌停': -3, '创新低': -2, '衰退': -2, '裁员': -2, '债务危机': -3,
        '商誉减值': -2, '库存积压': -2, '需求萎缩': -2, '竞争加剧': -1,
        '监管调查': -2, '处罚': -2, '终止合作': -2, '违约': -3
    }

    POLICY_KEYWORDS = {
        '产业政策': 2, '税收优惠': 2, '财政补贴': 2, '扶持政策': 2,
        '注册制': 1, '科创板': 1, '创业板改革': 1, '北交所': 1,
        '新能源政策': 2, '半导体政策': 2, '医药政策': 1, '消费政策': 1,
        '房地产政策': -1, '教育双减': -1, '互联网监管': -1,
        '碳中和': 2, '碳达峰': 2, '节能减排': 1, '环保政策': 1,
        '一带一路': 1, '自贸区': 1, '粤港澳大湾区': 1, '长三角一体化': 1,
        '专精特新': 2, '小巨人': 2, '制造业升级': 2, '数字经济': 2,
        '工信部': 1, '发改委': 1, '财政部': 1, '证监会': 1, '银保监会': 1,
        '降准': 1, '降息': 1, '麻辣粉': 1, '酸辣粉': 1, '公开市场操作': 0,
        'IPO': 0, '再融资': 0, '并购重组审核': 0, '注册生效': 1,
        '监管收紧': -1, '行业整顿': -1, '反垄断': -1, '数据安全审查': -1
    }

    MACRO_KEYWORDS = {
        '美联储': 0, '加息': -1, '降息': 1, '缩表': -1, '扩表': 1,
        '通胀': -1, 'CPI': -1, 'PPI': 0, '非农': 0, '就业数据': 0,
        'GDP': 0, 'PMI': 0, '采购经理人指数': 0, '消费者信心指数': 0,
        '美股': 0, '纳斯达克': 0, '标普500': 0, '道琼斯': 0, '恒生指数': 0,
        '欧洲央行': 0, '日本央行': 0, '英国央行': 0,
        '俄乌冲突': -1, '中东局势': -1, '中美关系': 0, '贸易战': -1,
        '地缘政治': -1, '全球供应链': 0, '原油价格': 0, '黄金价格': 0,
        '人民币汇率': 0, '美元指数': 0, '外汇储备': 0,
        '进出口': 0, '贸易顺差': 1, '贸易逆差': -1, '外资流入': 1, '外资流出': -1,
        '北向资金': 0, '南下资金': 0, '杠杆资金': 0, '融资融券': 0,
        '社融': 0, 'M2': 0, '信贷数据': 0, '居民存款': 0,
        '经济复苏': 1, '经济下行': -1, '经济稳定': 0, '增速放缓': -1,
        '华尔街': 0, '纽交所': 0, '美交所': 0, '做空': -1, '做多': 1,
        '特朗普': 0, '拜登': 0, '白宫': 0, '美国政府': 0, '国会': 0,
        '美国财政部': 0, '美国贸易代表': 0, '商务部': 0, '制裁': -1,
        '关税': -1, '科技战': -1, '芯片禁令': -1, '实体清单': -1,
        'G7': 0, 'G20': 0, '联合国': 0, '世卫组织': 0, '世贸组织': 0,
        'OPEC': 0, '石油输出国': 0, '原油减产': 1, '原油增产': -1,
        '英国脱欧': 0, '欧元区': 0, '欧债危机': -1,
        '日本政府': 0, '日元': 0, '日本央行宽松': 1,
        '新兴市场': 0, '发展中国家': 0, '债务危机': -1,
        '金融危机': -2, '经济危机': -2, '银行危机': -2, '流动性危机': -2,
        '主权信用评级': 0, '标普评级': 0, '穆迪评级': 0, '惠誉评级': 0,
        '外资机构': 0, '共同基金': 0, '对冲基金': 0, '养老金': 0,
        '北上资金': 0, 'QFII': 0, 'RQFII': 0, '沪股通': 0, '深股通': 0,
        '恐慌指数': 0, 'VIX': 0, '波动率': 0, '风险偏好': 0,
        '避险情绪': -1, '避险资产': 0, '避险资金': 0,
        '德国': 0, '法国': 0, '英国': 0, '意大利': 0, '西班牙': 0,
        '欧盟委员会': 0, '欧洲议会': 0, '欧元': 0, '英镑': 0,
        '巴黎': 0, '伦敦': 0, '法兰克福': 0, '欧洲股市': 0,
        '普京': 0, '俄罗斯': 0, '俄罗斯央行': 0, '卢布': 0, '俄国': 0,
        '泽连斯基': 0, '乌克兰': 0, '北约': 0, '欧盟制裁': -1,
        '以色列': 0, '巴勒斯坦': 0, '中东和平': 0, '伊朗': 0, '沙特': 0,
        ' OPEC+': 0, '能源危机': -1, '天然气': 0, '石油': 0,
        '印度': 0, '莫迪': 0, '印度政府': 0, '印度央行': 0, '卢比': 0,
        '韩国': 0, '三星': 0, 'LG': 0, '现代汽车': 0, '韩元': 0, 'KOSPI': 0,
        '澳大利亚': 0, '澳联储': 0, '澳元': 0, '铁矿石': 0,
        '加拿大': 0, '加央行': 0, '加元': 0, '多伦多': 0,
        '巴西': 0, '墨西哥': 0, '阿根廷': 0, '拉美': 0, '新兴货币': 0,
        '中国': 0, '中国央行': 0, '人民银行': 0, '人民币': 0, 'A股': 0, '港股': 0,
        '政治局': 0, '国务院': 0, '发改委': 1, '证监会': 0, '银保监会': 0,
        '全国人大': 0, '两会': 0, '十四五': 1, '二十大': 0,
        '李强': 0, '习近平': 0, '刘鹤': 0, '易纲': 0,
        '芯片法案': 0, '通胀削减法案': 0, '基础设施法案': 0,
        '财政刺激': 1, '货币宽松': 1, '流动性注入': 1,
        '债务上限': 0, '政府关门': -1, '信用评级下调': -1,
        '大选': 0, '黑天鹅': -2, '灰犀牛': -1, '尾部风险': -1,
        '地缘风险': -1, '台海局势': 0, '南海问题': 0, '朝鲜': 0, '半岛': 0,
        '全球疫情': -1, '猴痘': -1, '流感': 0, '公共卫生事件': -1,
        '气候危机': -1, '极端天气': -1, '自然灾害': -1, '地震': -1,
        'AI': 0, '人工智能': 0, 'ChatGPT': 0, '大模型': 0, '科技股': 0,
        '马斯克': 0, '特斯拉': 0, 'SpaceX': 0, '苹果': 0, '谷歌': 0, '微软': 0, '亚马逊': 0,
        '英伟达': 0, 'AMD': 0, '英特尔': 0, '高通': 0, '台积电': 0, '三星电子': 0,
        '中概股': 0, '阿里巴巴': 0, '腾讯': 0, '百度': 0, '京东': 0, '拼多多': 0,
        '做空机构': 0, '浑水': 0, '香橼': 0, '做空报告': -1,
        '回购': 1, '增持': 1, '减持': -1, '解禁': -1, '定增': 0,
        'IPO': 0, '上市': 0, '退市': -1, '借壳': 0,
        '年报': 0, '季报': 0, '中报': 0, '业绩预告': 0, '业绩变脸': -1,
        '审计': 0, '财务造假': -2, '会计事务所': 0,
        '重组': 0, '并购': 0, '分拆': 0, '破产': -2, '债务违约': -2,
        '可转债': 0, '优先股': 0, '永续债': 0, '城投债': 0,
        '美债收益率': 0, '国债': 0, '地方债': 0, '企业债': 0,
        '信用利差': 0, '违约率': -1, '评级下调': -1,
        '做市商': 0, '量化基金': 0, '指数基金': 0, '主动管理': 0,
        'ETF': 0, '公募基金': 0, '私募基金': 0, '险资': 0, '社保基金': 0,
        '外资买超': 1, '外资卖超': -1, '主力资金': 0, '散户': 0,
        '杠杆率': 0, '保证金': 0, '平仓': -1, '爆仓': -2,
        '汇率波动': 0, '外汇管制': 0, '资本外流': -1, '资本流入': 1,
        '全球化的': 0, '逆全球化': -1, '脱钩': -1, '产业链转移': 0
    }

    INDUSTRY_KEYWORDS = {
        '行业景气': 1, '行业复苏': 1, '行业龙头': 1, '市场份额': 0,
        '产能过剩': -1, '行业竞争': -1, '行业整合': 0, '替代威胁': -1,
        '技术突破': 2, '技术迭代': 0, '研发投入': 0, '专利': 0,
        '产品发布': 1, '新品上市': 1, '产品升级': 1, '质量问题': -2,
        '安全事故': -2, '环保问题': -2, '生产事故': -2,
        '原材料价格': 0, '成本上涨': -1, '成本下降': 1, '毛利率': 0,
        '供应链': 0, '供应商': 0, '客户': 0, '经销商': 0,
        '应收账款': -1, '现金流': 0, '存货': 0, '周转率': 0
    }

    def analyze(self, news_context: Optional[str],
                stock_name: str, code: str) -> Tuple[str, int, str, str, str]:
        """
        分析消息面

        Args:
            news_context: 新闻上下文
            stock_name: 股票名称
            code: 股票代码

        Returns:
            Tuple[分析详情, 消息面评分, 新闻标题列表, 政策信息, 宏观信息]
        """
        if not news_context:
            return f"暂无{stock_name}({code})相关新闻信息", 0, "", "", ""

        details = []
        score = 50
        headlines = []
        policy_info = ""
        macro_info = ""

        details, score, headlines, policy_info, macro_info = self._analyze_keywords(
            news_context, details, score, headlines, policy_info, macro_info
        )

        if not details:
            details.append("新闻内容中性，无明显利好利空")

        news_headlines_str = "；".join(headlines) if headlines else ""
        return "；".join(details), score, news_headlines_str, policy_info, macro_info

    def _analyze_keywords(self, news_context: str,
                          details: list, score: int,
                          headlines: list, policy_info: str,
                          macro_info: str) -> Tuple[list, int, list, str, str]:
        """分析新闻关键词"""
        positive_score = 0
        negative_score = 0

        for keyword, weight in self.POSITIVE_KEYWORDS.items():
            count = news_context.count(keyword)
            if count > 0:
                positive_score += weight * count
                details.append(f"发现积极关键词'{keyword}'({count}次)")

        for keyword, weight in self.NEGATIVE_KEYWORDS.items():
            count = news_context.count(keyword)
            if count > 0:
                negative_score += weight * count
                details.append(f"发现消极关键词'{keyword}'({count}次)")

        for keyword, weight in self.POLICY_KEYWORDS.items():
            count = news_context.count(keyword)
            if count > 0:
                if weight > 0:
                    policy_info += f"{keyword}(+{weight})；"
                elif weight < 0:
                    policy_info += f"{keyword}({weight})；"

        for keyword, weight in self.MACRO_KEYWORDS.items():
            count = news_context.count(keyword)
            if count > 0:
                if weight > 0:
                    macro_info += f"{keyword}(利好)；"
                elif weight < 0:
                    macro_info += f"{keyword}(利空)；"

        for keyword, weight in self.INDUSTRY_KEYWORDS.items():
            count = news_context.count(keyword)
            if count > 0:
                if weight > 0:
                    details.append(f"行业利好：{keyword}")
                    positive_score += weight
                elif weight < 0:
                    details.append(f"行业利空：{keyword}")
                    negative_score += abs(weight)

        total_keywords = positive_score + abs(negative_score)
        if total_keywords > 0:
            score = 50 + (positive_score + negative_score) * 2
            score = max(0, min(100, score))

        lines = news_context.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if any(kw in line for kw in ['【', '】', '搜索结果', '来源：']):
                continue
            if len(line) > 10 and len(line) < 150:
                clean_line = line.split('。')[0] if '。' in line else line
                clean_line = clean_line.split('；')[0] if '；' in clean_line else clean_line
                if clean_line and len(clean_line) > 5:
                    headlines.append(clean_line[:60])

        return details, score, headlines, policy_info, macro_info

    def calculate_sentiment_score(self, news_context: str) -> int:
        """计算新闻情绪分"""
        if not news_context:
            return 50

        score = 50
        positive_score = 0
        negative_score = 0

        for keyword, weight in self.POSITIVE_KEYWORDS.items():
            count = news_context.count(keyword)
            if count > 0:
                positive_score += weight * count

        for keyword, weight in self.NEGATIVE_KEYWORDS.items():
            count = news_context.count(keyword)
            if count > 0:
                negative_score += weight * count

        score = 50 + (positive_score + negative_score) * 2
        return max(0, min(100, score))
