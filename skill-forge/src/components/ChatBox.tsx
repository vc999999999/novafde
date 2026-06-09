import type { ChatMessage } from '../types';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';

interface Props {
  messages: ChatMessage[];
  onSend: (text: string) => void;
}

export default function ChatBox({ messages, onSend }: Props) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-panel-border bg-panel shadow-md overflow-hidden">
      <ScrollArea className="max-h-[280px] p-4">
        {messages.length === 0 && (
          <div className="py-6 px-5 text-center rounded-[var(--radius-md)] border border-dashed border-white/10 text-muted-foreground text-[var(--text-base)]">
            粘贴你的 SOP、流程描述或业务规则，Agent 会帮你归入表单字段。
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`mb-3 last:mb-0 ${msg.role === 'user' ? 'text-right' : ''}`}>
            <div className={`inline-block max-w-[80%] p-2 px-3 rounded-[var(--radius-md)] text-[var(--text-base)] leading-[var(--leading-relaxed)] ${
              msg.role === 'user'
                ? 'bg-accent-dim border border-accent/20 text-foreground'
                : 'bg-surface-up border border-white/6 text-secondary-foreground'
            }`}>
              {msg.content}
            </div>
          </div>
        ))}
      </ScrollArea>
      <div className="flex gap-2 p-3 px-4 border-t border-panel-border bg-white/[0.02]">
        <Input
          className="flex-1 rounded-full"
          placeholder="输入补充说明，按回车发送..."
          onKeyDown={(e) => {
            if (e.key === 'Enter' && e.currentTarget.value.trim()) {
              onSend(e.currentTarget.value.trim());
              e.currentTarget.value = '';
            }
          }}
        />
        <Button
          variant="outline"
          size="sm"
          onClick={(e) => {
            const input = e.currentTarget.previousElementSibling as HTMLInputElement;
            if (input?.value.trim()) {
              onSend(input.value.trim());
              input.value = '';
            }
          }}
          type="button"
        >
          发送
        </Button>
      </div>
    </div>
  );
}