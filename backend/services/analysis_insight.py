from __future__ import annotations

import json
import logging
import re
from typing import Any

from backend.core.config import settings
from backend.services.llm_service import LLMService

logger = logging.getLogger(__name__)

_AGENT_INSTRUCTIONS = {
    'product_analysis': (
        '\u4ee5\u5546\u54c1\u8fd0\u8425\u4e13\u5bb6\u8eab\u4efd\u89e3\u91ca\u5019\u9009\u5546\u54c1\u6392\u5e8f\u3002\n'
        '1) \u8bc6\u522b\u9ad8\u6f5c\u529b\u5546\u54c1\uff1b\u8bf4\u660e\u5176\u8bc4\u5206\u4e3b\u9a71\u52a8\u662f\u201c\u6d41\u91cf\u201d\u8fd8\u662f\u201c\u8f6c\u5316\u201d\u3002\n'
        '2) \u7ed9\u51fa\u201c\u5f3a\u52bf\u63a8\u8350/\u63a8\u8350/\u5907\u9009\u201d\u4e09\u7ea7\u6807\u7b7e\u3002\n'
        '3) \u7ed3\u5408\u9884\u6d4b\u9500\u91cf\u4e0e\u4ef7\u683c\u4f30\u7b97 30 \u5929 GMV \u533a\u95f4\uff08\u4e0b\u9650/\u4e0a\u9650\uff09\u3002\n'
        '4) \u68c0\u67e5\u5e93\u5b58\u4e0e\u9884\u6d4b\u9500\u91cf\u5339\u914d\u5ea6\uff0c\u9884\u6d4b\u9500\u91cf > \u5e93\u5b58*80% \u6807\u6ce8\u65ad\u8d27\u9884\u8b66\u3002\n'
        '5) \u5bf9 Top 1 \u5546\u54c1\u7ed9\u51fa A/B \u6d4b\u8bd5\u5efa\u8bae\uff08\u5982\u964d\u4ef7 5% vs \u8d60\u914d\u4ef6\uff09\u5e76\u6307\u660e\u9884\u671f\u8861\u91cf\u6307\u6807\u3002'
    ),
    'trend_forecast': (
        '\u4ee5\u589e\u957f\u5206\u6790\u5e08\u8eab\u4efd\u89e3\u91ca\u9884\u6d4b\u4fe1\u53f7\u3002\n'
        '1) \u6309 7\u5929/30\u5929/90\u5929 \u7a97\u53e3\u5217\u51fa\u9884\u6d4b\u9500\u91cf\u4e0e\u7f6e\u4fe1\u5ea6\u3002\n'
        '2) \u5c06\u5546\u54c1\u5206\u4e3a\u4e0a\u5347\u671f/\u7a33\u5b9a\u671f/\u8870\u9000\u671f\u4e09\u7c7b\u3002\n'
        '3) \u505a\u201c\u8bc4\u5206 \u00d7 \u7f6e\u4fe1\u5ea6\u201d\u4e8c\u7ef4\u77e9\u9635\uff1a\u9ad8\u8bc4\u5206+\u9ad8\u7f6e\u4fe1\u5ea6=\u5fc5\u80dc\u54c1\uff1b\u9ad8\u8bc4\u5206+\u4f4e\u7f6e\u4fe1\u5ea6=\u5c0f\u6d41\u91cf\u6d4b\u8bd5\u54c1\u3002\n'
        '4) \u68c0\u67e5\u6ce2\u52a8\u6027\uff1a\u5982\u6709\u6781\u7aef\u503c\uff0c\u8bf4\u660e\u662f\u5426\u7f29\u5c3e\u5904\u7406\u3002\n'
        '5) \u8870\u9000\u671f\u5546\u54c1\u5fc5\u987b\u7ed9\u51fa\u201c\u6346\u7ed1\u9500\u552e/\u6e05\u4ed3/\u4e0b\u67b6\u201d\u5177\u4f53\u52a8\u4f5c\u3002'
    ),
    'competitor_analysis': (
        '\u4ee5\u7ade\u540c\u5206\u6790\u5e08\u8eab\u4efd\u89e3\u91ca\u5dee\u5f02\u5316\u673a\u4f1a\u3002\n'
        '1) \u6309\u4ef7\u683c\u5e26 <10/10-50/50-100/>100 USD \u5206\u6876\u5217\u51fa\u5546\u54c1\u6570\u4e0e\u5360\u6bd4\u3002\n'
        '2) \u7ed9\u51fa\u201c\u8bc4\u5206\u5206\u5e03\u5bf9\u6bd4\u201d\uff1a\u672c\u6b21\u5546\u54c1 vs \u7c7b\u76ee\u5747\u503c\u3002\n'
        '3) \u8bf4\u660e\u5b9a\u4f4d\u5dee\u5f02\uff08\u4eba\u7fa4/\u4ef7\u683c/\u5356\u70b9\uff09\u3002\n'
        '4) \u7ed9\u51fa\u8fdb\u5165 vs \u907f\u5f00\u5efa\u8bae\uff1a\u660e\u786e\u54ea\u7c7b\u7ade\u54c1\u4e0d\u5e94\u6b63\u9762\u7ade\u4e89\u3002'
    ),
    'inventory': (
        '\u4ee5\u4f9b\u5e94\u94fe\u5206\u6790\u5e08\u8eab\u4efd\u89e3\u91ca\u5e93\u5b58\u98ce\u9669\u3002\n'
        '1) \u6309 \u6ede\u9500/\u4f4e/\u6b63\u5e38/\u7d27\u5f20/\u65ad\u8d27\u9884\u8b66 \u4e94\u7ea7\u6807\u6ce8\u5e93\u5b58\u5065\u5eb7\u5ea6\u3002\n'
        '2) \u6309 \u201c\u8d44\u91d1\u5360\u7528 \u00d7 \u98ce\u9669\u7b49\u7ea7\u201d \u6392\u5e8f\u8865\u8d27\u4f18\u5148\u7ea7\u3002\n'
        '3) \u6307\u51fa\u6ede\u9500 SKU \u7684\u6e05\u4ed3\u5efa\u8bae\u4e0e\u9884\u8ba1\u635f\u8017\u7387\u3002\n'
        '4) \u65ad\u8d27 SKU \u5fc5\u987b\u7ed9\u51fa\u7d27\u6025\u8865\u8d27\u6570\u91cf\u4e0e\u5230\u8d27\u65f6\u95f4\u7a97\u3002'
    ),
    'pricing': (
        '\u4ee5\u5b9a\u4ef7\u5206\u6790\u5e08\u8eab\u4efd\u89e3\u91ca\u4ef7\u683c\u673a\u4f1a\u3002\n'
        '1) \u8f93\u51fa\u4ef7\u683c\u5f39\u6027\u533a\u95f4\uff1a\u57fa\u4e8e 3 \u56e0\u5b50\u6a21\u578b\u7684\u5efa\u8bae\u4ef7\u533a\u95f4\u4e0e\u7f6e\u4fe1\u5ea6\u3002\n'
        '2) \u7ed9\u51fa\u201c\u7ade\u54c1\u4ef7\u683c\u5e26\u201d\uff1a\u672c\u6b21\u5546\u54c1\u76f8\u5bf9\u7c7b\u76ee\u4ef7\u683c\u767e\u5206\u4f4d\u3002\n'
        '3) \u8bbe\u7f6e\u201c\u8bd5\u4ef7\u533a\u95f4\u201d\uff1a\u5141\u8bb8 A/B \u6d4b\u8bd5\u7684 \u00b15% \u8303\u56f4\u4e0e\u9884\u671f\u8f6c\u5316\u5f71\u54cd\u3002\n'
        '4) \u8bbe\u7f6e\u201c\u4ef7\u683c\u76d1\u63a7\u9608\u503c\u201d\uff1a\u4ef7\u683c\u504f\u79bb\u5efa\u8bae\u4ef7 \u00b13% \u65f6\u7684\u544a\u8b66\u89c4\u5219\u3002'
    ),
    'promotion': (
        '\u4ee5\u8425\u9500\u8fd0\u8425\u4e13\u5bb6\u8eab\u4efd\u89e3\u91ca\u4fc3\u9500\u673a\u4f1a\u3002\n'
        '1) \u8bf4\u660e\u4fc3\u9500\u7c7b\u578b\u5339\u914d\u7406\u7531\uff1a\u4e3a\u4ec0\u4e48\u8fd9\u4e2a\u54c1\u7c7b/\u5ba2\u5355\u4ef7\u9002\u5408\u67d0\u7c7b\u4fc3\u9500\u3002\n'
        '2) \u7ed9\u51fa\u201c\u6298\u6263\u6df1\u5ea6\u5efa\u8bae\u201d\uff1a\u7ed3\u5408\u6bdb\u5229\u7a7a\u95f4\u7ed9\u51fa\u6700\u4f4e\u6298\u6263\u7ea2\u7ebf\u4e0e\u6700\u4f18\u6298\u6263\u533a\u95f4\u3002\n'
        '3) \u7ed9\u51fa\u201c\u6863\u671f\u5efa\u8bae\u201d\uff1a\u9002\u5408\u7684\u4fc3\u9500\u6863\u671f\uff08\u5927\u4fc3/\u5e73\u9500/\u6e05\u4ed3\uff09\u3002\n'
        '4) \u4f30\u7b97 ROI \u533a\u95f4\uff1a\u57fa\u4e8e\u5386\u53f2\u4fc3\u9500\u7cfb\u6570\u7684\u9884\u4f30 GMV \u589e\u91cf\u4e0e\u5229\u6da6\u7387\u3002'
    ),
    'marketing_copy': (
        '\u4ee5\u5185\u5bb9\u8425\u9500\u4e13\u5bb6\u8eab\u4efd\u89e3\u91ca\u6587\u6848\u673a\u4f1a\u3002\n'
        '1) \u4ece\u5546\u54c1\u8bc4\u5206/\u4ef7\u683c/\u5e93\u5b58\u4e2d\u63d0\u70bc 3 \u4e2a\u6838\u5fc3\u5356\u70b9\u3002\n'
        '2) \u753b\u50cf\u76ee\u6807\u4eba\u7fa4\uff1a\u57fa\u4e8e\u7c7b\u76ee\u4e0e\u4ef7\u683c\u5b9a\u4f4d\u7684\u76ee\u6807\u4eba\u7fa4\u3002\n'
        '3) \u660e\u786e\u201c\u5dee\u5f02\u5316\u8bdd\u672f\u201d\uff1a\u672c\u6b21\u5546\u54c1\u4e0e\u540c\u4ef7\u4f4d\u7ade\u54c1\u7684\u5356\u70b9\u5dee\u5f02\u3002'
    ),
}

_SYSTEM_PROMPT = (
    '\u4f60\u662f\u62e5\u670910\u5e74\u4ee5\u4e0a\u7ecf\u9a8c\u7684\u8d44\u6df1\u7535\u5546\u5546\u4e1a\u6570\u636e\u5206\u6790\u5e08\uff0c\u64c5\u957f\u96f6\u552e/\u7535\u5546\u5546\u54c1\u8fd0\u8425\u4e0e\u589e\u957f\u7b56\u7565\u3002\n\n'
    '\u4e25\u683c\u8981\u6c42\uff1a\n'
    '1) \u53ea\u80fd\u4f9d\u636e\u8f93\u5165\u8bc1\u636e\u4f5c\u7ed3\u8bba\uff0c\u4e0d\u5f97\u7f16\u9020\u5546\u54c1\u3001\u4ef7\u683c\u3001\u9500\u91cf\u3001\u7ade\u54c1\u3001\u5e93\u5b58\u6216\u5e02\u573a\u6570\u636e\u3002\n'
    '2) \u7981\u6b62\u8f93\u51fa\u601d\u7ef4\u94fe\u3001\u6a21\u578b\u63a8\u7406\u8fc7\u7a0b\u3001\u8349\u7a3f\u3001\u5de5\u5177\u8c03\u7528\u8fc7\u7a0b\u6216\u4efb\u4f55 <think> \u6807\u7b7e\u3002\n'
    '3) \u6240\u6709\u6570\u5b57\u5fc5\u987b\u4e0e\u8bc1\u636e\u4e00\u81f4\uff1b\u6a21\u578b\u4f30\u7b97\u5fc5\u987b\u6807\u660e\u4f30\u7b97\u5c5e\u6027\uff0c\u4e0d\u80fd\u5199\u6210\u771f\u5b9e\u9500\u91cf\u3002\n'
    '4) \u4e1a\u52a1\u7ed3\u8bba\u5fc5\u987b\u56de\u7b54\u201c\u53d1\u73b0\u4e86\u4ec0\u4e48\u3001\u5bf9\u4e1a\u52a1\u610f\u5473\u4ec0\u4e48\u3001\u4e0b\u4e00\u6b65\u505a\u4ec0\u4e48\u201d\u3002\n'
    '5) \u5185\u5bb9\u8981\u5305\u542b\u5177\u4f53\u6570\u636e\u70b9\uff08\u6570\u5b57/\u6bd4\u4f8b/\u54c1\u7c7b\uff09\uff0c\u907f\u514d\u7a7a\u6cdb\u3001\u5957\u8bdd\u3002\n'
    '6) \u82e5\u8bc1\u636e\u4e0d\u8db3\uff0c\u5fc5\u987b\u660e\u786e\u5199\u51fa\u8bc1\u636e\u8fb9\u754c\u548c\u9700\u8981\u8865\u5145\u7684\u6570\u636e\u3002\n\n'
    '\u8f93\u51fa\u5b57\u6bb5\u8981\u6c42\uff1a\n'
    '- insight\uff1a120-200 \u5b57\uff0c\u5305\u542b\u4e00\u53e5\u8bdd\u7ed3\u8bba + \u4e3b\u8981\u9a71\u52a8\u6307\u6807 + \u4e1a\u52a1\u610f\u5473\n'
    '- key_findings\uff1a3-5 \u6761\uff0c\u6bcf\u6761\u5e26\u5177\u4f53\u6570\u636e\uff08\u6570\u5b57/\u6bd4\u4f8b/\u54c1\u7c7b\uff09\n'
    '- recommended_actions\uff1a2-4 \u6761\u53ef\u6267\u884c\u52a8\u4f5c\uff0c\u542b A/B \u6d4b\u8bd5\u6216\u76d1\u63a7\u6307\u6807\n'
    '- limitations\uff1a1-3 \u6761\u6570\u636e\u9650\u5236\u6216\u98ce\u9669\n\n'
    '\u4e25\u683c\u8fd4\u56de JSON\uff0c\u4e0d\u8981\u5305\u542b\u4efb\u4f55 JSON \u4ee5\u5916\u7684\u6587\u672c\u3002'
)


def _clean_text(value: Any) -> str:
    text = str(value or '').strip()
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'```(?:json|markdown)?', '', text, flags=re.IGNORECASE).replace('```', '')
    return text.strip()


def _clean_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        text = _clean_text(item)
        if text:
            cleaned.append(text)
    return cleaned[:limit]


class AnalysisInsightService:
    'Call the configured LLM with compact deterministic evidence.'

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service or LLMService()

    async def generate(
        self,
        agent_name: str,
        user_query: str,
        evidence: dict[str, Any],
        fallback_insight: str,
        fallback_findings: list[str],
        limitations: list[str] | None = None,
    ) -> dict[str, Any]:
        'Return concise insight fields without exposing intermediate reasoning.'
        fallback = {
            'insight': fallback_insight,
            'key_findings': fallback_findings[:5],
            'recommended_actions': [],
            'limitations': limitations or [],
            'insight_source': '\u89c4\u5219\u6458\u8981',
            'llm_used': False,
            'llm_calls': 0,
        }
        if not user_query or not settings.OPENAI_API_KEY:
            return fallback
        # Skip LLM call when evidence is empty (e.g. 0 matched products) - fallback is already informative.
        if not evidence or not any(evidence.values()):
            return fallback

        payload = {
            'user_query': user_query,
            'analysis_type': agent_name,
            'task_instruction': _AGENT_INSTRUCTIONS.get(agent_name, '\u89e3\u91ca\u6307\u6807\u53d8\u5316\u5e76\u7ed9\u51fa\u7ecf\u8425\u5efa\u8bae\u3002'),
            'evidence': evidence,
        }
        try:
            result = await self._llm.chat(
                system_prompt=_SYSTEM_PROMPT,
                user_message=json.dumps(payload, ensure_ascii=False, separators=(',', ':')),
                temperature=0.25,
                max_tokens=700,
                json_mode=True,
                fallback=None,
            )
            if isinstance(result, dict):
                insight = _clean_text(result.get('insight') or result.get('summary'))
                findings = _clean_list(result.get('key_findings'), 5)
                actions = _clean_list(result.get('recommended_actions'), 4)
                model_limits = _clean_list(result.get('limitations'), 4)
                if insight and findings:
                    return {
                        'insight': insight,
                        'key_findings': findings,
                        'recommended_actions': actions,
                        'limitations': model_limits or (limitations or []),
                        'insight_source': '\u004c\u004c\u004d\u6d1e\u5bdf',
                        'llm_used': True,
                        'llm_calls': 1,
                    }
        except Exception as exc:
            logger.warning('%s insight generation failed: %s', agent_name, exc)
        return fallback
