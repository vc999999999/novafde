import ChatBox from '../ChatBox';
import FormGroup from '../FormGroup';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface Props {
  messages: import('../../types').ChatMessage[];
  onSendMessage: (text: string) => void;
}

export default function SupplementStep({ messages, onSendMessage }: Props) {
  return (
    <div>
      <Alert className="border-warning-border bg-warning-dim text-warning">
        <AlertDescription>
          补充内容会随草稿提交给后端生成链路；关键字段仍建议在表单中确认。
        </AlertDescription>
      </Alert>

      <ChatBox messages={messages} onSend={onSendMessage} />

      <div className="mt-4">
        <FormGroup label="快速粘贴模板" hint="选择模板后会作为补充消息加入草稿">
          <div className="flex flex-wrap gap-2">
            {['SOP 文档', '业务流程', '经验总结', '踩坑记录'].map((tpl) => (
              <button
                key={tpl}
                className="rounded-full border border-white/12 bg-surface text-muted-foreground py-1.5 px-3.5 text-[var(--text-sm)] cursor-pointer transition-all hover:bg-white/6 hover:text-foreground hover:border-white/20"
                onClick={() => onSendMessage(`我有一份${tpl}，请帮我提取关键字段：\n\n[粘贴内容]`)}
                type="button"
              >
                {tpl}
              </button>
            ))}
          </div>
        </FormGroup>
      </div>
    </div>
  );
}