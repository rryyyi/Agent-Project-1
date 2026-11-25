"""Explainable lexical baseline; confidence is heuristic, not calibrated probability."""

from jewelmentor.models import Route

RULES = {
    "objection": ("太贵", "嫌贵", "贵了", "异议", "降价", "折扣", "便宜", "犹豫", "不值"),
    "relationship": ("回访", "售后", "老客户", "复购", "维护", "客诉", "保养"),
    "product": ("4c", "净度", "切工", "克拉", "证书", "钻石", "黄金", "铂金", "材质", "培育钻"),
    "practice": ("角色扮演", "模拟", "演练", "练习", "你扮演", "实战"),
    "discovery": ("预算", "需求", "送礼", "求婚", "纪念", "怎么选", "推荐", "婚戒"),
}


def route(text: str) -> Route:
    lowered = text.lower()
    scores = {intent: sum(word in lowered for word in words) for intent, words in RULES.items()}
    ranked = sorted(scores, key=lambda key: scores[key], reverse=True)
    best = ranked[0]
    if not scores[best]:
        return Route(intent="clarify", confidence=0.2, reason="没有明确的珠宝培训信号，需要澄清训练目标")
    # Price objections override product mentions; practice remains explicit when there is no objection.
    if scores["objection"]:
        best = "objection"
    elif scores["practice"]:
        best = "practice"
    elif scores["relationship"]:
        best = "relationship"
    return Route(intent=best, confidence=min(0.92, 0.62 + 0.1 * scores[best]), reason=f"命中 {best} 词项 {scores[best]} 项；规则置信度未经概率校准")
