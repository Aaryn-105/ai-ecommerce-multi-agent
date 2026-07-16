/** AgentMessage — renders the assistant reply as Markdown + optional ReportCards. */
import ReactMarkdown from "react-markdown";
import ReportCard from "./ReportCard";

interface AgentMessageProps {
  reply: string;
  sections?: Record<string, unknown>;
  plan?: Record<string, unknown>[];
}

export default function AgentMessage({ reply, sections, plan }: AgentMessageProps) {
  const hasSections = sections && Object.keys(sections).length > 0;
  const hasPlan = plan && plan.length > 0;

  return (
    <div className="msg msg-agent">
      <div className="msg-avatar">🤖</div>
      <div className="msg-bubble msg-bubble-agent">
        {/* Markdown reply */}
        <div className="msg-markdown">
          <ReactMarkdown>{reply}</ReactMarkdown>
        </div>

        {/* Execution plan summary */}
        {hasPlan && (
          <details className="msg-plan-details" open={false}>
            <summary className="msg-plan-summary">
              执行计划（{plan!.length} 步）
            </summary>
            <ol className="msg-plan-list">
              {plan!.map((step, i) => (
                <li key={i} className="msg-plan-step">
                  <span className="plan-step-agent">
                    {String(step.agent ?? step.description ?? `步骤 ${i + 1}`)}
                  </span>
                  {!!step.status && (
                    <span className={`plan-step-status status-${String(step.status)}`}>
                      {String(step.status)}
                    </span>
                  )}
                </li>
              ))}
            </ol>
          </details>
        )}

        {/* ReportCards for each agent section */}
        {hasSections && (
          <div className="msg-sections">
            {Object.entries(sections!).map(([agentName, data]) => (
              <ReportCard
                key={agentName}
                agentName={agentName}
                data={data as Record<string, unknown>}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}