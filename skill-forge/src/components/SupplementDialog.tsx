import { useMemo, useState } from 'react';
import type { SupplementAnswer, UserQuestion } from '../types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';


type AnswerValue = string | string[];

export default function SupplementDialog({
  questions,
  scores,
  submitting,
  onSubmit,
  onSkip,
}: {
  questions: UserQuestion[];
  scores: {
    overall: number | null;
    activation: number | null;
    implementation: number | null;
  };
  submitting: boolean;
  onSubmit: (answers: SupplementAnswer[]) => void;
  onSkip: () => void;
}) {
  const initial = useMemo(
    () => Object.fromEntries(
      questions.map((question) => [
        question.issueId,
        question.existingAnswer ?? (question.inputControl === 'multi-select' ? [] : ''),
      ]),
    ) as Record<string, AnswerValue>,
    [questions],
  );
  const [answers, setAnswers] = useState<Record<string, AnswerValue>>(initial);

  const submit = () => {
    const payload = questions
      .map((question) => ({
        issueId: question.issueId,
        answer: answers[question.issueId],
      }))
      .filter((item): item is SupplementAnswer => (
        Array.isArray(item.answer) ? item.answer.length > 0 : Boolean(item.answer?.trim())
      ));
    onSubmit(payload);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 px-4 backdrop-blur-sm"
      onClick={onSkip}
      onKeyDown={(e) => { if (e.key === 'Escape') onSkip(); }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="supplement-title"
        onClick={(e) => e.stopPropagation()}
        className="max-h-[86dvh] w-full max-w-[640px] overflow-y-auto rounded-[var(--radius-md)] border border-panel-border bg-panel p-6 shadow-2xl"
      >
        <div className="mb-5">
          <p className="text-[11px] uppercase tracking-[0.18em] text-warning">需要业务事实</p>
          <h2 id="supplement-title" className="mt-2 text-xl font-semibold">补充信息以提高 Skill 质量</h2>
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
            当前问题无法由 Agent 可靠推断。补充内容会并入原任务，不会创建新的草稿或重置已完成评测。
          </p>
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
            <span>总分 {scores.overall ?? '--'}</span>
            <span>触发 {scores.activation ?? '--'}</span>
            <span>实现 {scores.implementation ?? '--'}</span>
          </div>
        </div>

        <div className="flex flex-col gap-5">
          {questions.map((question) => {
            const value = answers[question.issueId];
            return (
              <div key={question.issueId} className="space-y-2">
                <Label htmlFor={question.issueId}>{question.question}</Label>
                {question.inputControl === 'long-text' && (
                  <Textarea
                    id={question.issueId}
                    value={typeof value === 'string' ? value : ''}
                    onChange={(event) => setAnswers((current) => ({
                      ...current,
                      [question.issueId]: event.target.value,
                    }))}
                    rows={4}
                  />
                )}
                {question.inputControl === 'short-text' && (
                  <Input
                    id={question.issueId}
                    value={typeof value === 'string' ? value : ''}
                    onChange={(event) => setAnswers((current) => ({
                      ...current,
                      [question.issueId]: event.target.value,
                    }))}
                  />
                )}
                {question.inputControl === 'single-select' && (
                  <select
                    id={question.issueId}
                    className="w-full rounded-[var(--radius-sm)] border border-white/10 bg-surface p-2.5 text-sm"
                    value={typeof value === 'string' ? value : ''}
                    onChange={(event) => setAnswers((current) => ({
                      ...current,
                      [question.issueId]: event.target.value,
                    }))}
                  >
                    <option value="">请选择</option>
                    {question.options.map((option) => <option key={option}>{option}</option>)}
                  </select>
                )}
                {question.inputControl === 'multi-select' && (
                  <div id={question.issueId} className="flex flex-wrap gap-2">
                    {question.options.map((option) => {
                      const selected = Array.isArray(value) && value.includes(option);
                      return (
                        <Button
                          key={option}
                          type="button"
                          variant={selected ? 'default' : 'outline'}
                          size="sm"
                          onClick={() => setAnswers((current) => {
                            const selectedValues = Array.isArray(current[question.issueId])
                              ? current[question.issueId] as string[]
                              : [];
                            return {
                              ...current,
                              [question.issueId]: selected
                                ? selectedValues.filter((item) => item !== option)
                                : [...selectedValues, option],
                            };
                          })}
                        >
                          {option}
                        </Button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="mt-6 flex flex-col-reverse gap-2 border-t border-panel-border pt-4 sm:flex-row sm:justify-end">
          <Button type="button" variant="outline" onClick={onSkip} disabled={submitting}>
            暂不补充，继续生成
          </Button>
          <Button type="button" onClick={submit} disabled={submitting}>
            {submitting ? '正在提交...' : '补充并继续'}
          </Button>
        </div>
      </div>
    </div>
  );
}
