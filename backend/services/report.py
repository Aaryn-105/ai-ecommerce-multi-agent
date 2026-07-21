from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.models.conversation import Conversation
from backend.models.report import Report
from backend.services.report_document import build_report_document


class ReportService:
    'Persist a chat analysis and its rendered report as one history record.'

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_report(
        self,
        conversation: Conversation,
        user_query: str,
        content: str,
        summary: str,
        sections: dict[str, Any],
        plan: list[dict[str, Any]],
    ) -> Report:
        title_text = user_query.strip().replace('\n', ' ')
        title = '\u5bf9\u8bdd\u5206\u6790\uff5c' + (title_text[:72] or '\u7535\u5546\u4e1a\u52a1\u5206\u6790')
        report_document = build_report_document(
            content,
            title=title,
            summary=summary,
        )
        stored_sections = {
            '_report_markdown': content,
            '_report_document': report_document,
            '_user_query': user_query,
            '_agent_sections': sections,
            '_plan': plan,
        }
        report = Report(
            conversation_id=conversation.id,
            title=title,
            summary=summary,
            sections=stored_sections,
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    @staticmethod
    def unpack(report: Report) -> tuple[str, str, dict[str, Any]]:
        'Return markdown content, query, and agent sections for legacy records too.'
        stored = report.sections if isinstance(report.sections, dict) else {}
        if '_agent_sections' in stored:
            return (
                str(stored.get('_report_markdown') or ''),
                str(stored.get('_user_query') or ''),
                stored.get('_agent_sections') or {},
            )
        return '', '', stored
