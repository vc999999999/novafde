import FormGroup from '../FormGroup';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Textarea } from '@/components/ui/textarea';

interface Props {
  content: string;
  onChange: (content: string) => void;
}

export default function SupplementStep({ content, onChange }: Props) {
  return (
    <div>
      <Alert className="mb-5 border-accent-border bg-accent-dim text-foreground">
        <AlertDescription>
          这里完全自由填写，也可以留空。生成时它只作为低优先级背景参考，不能覆盖必须遵守的规则。
        </AlertDescription>
      </Alert>

      <FormGroup label="补充说明" hint="可填写额外背景、案例、表达偏好、遗漏信息或临时要求">
        <Textarea
          value={content}
          onChange={(event) => onChange(event.target.value)}
          placeholder="自由填写你还想告诉 Agent 的内容"
          rows={14}
        />
      </FormGroup>
    </div>
  );
}
