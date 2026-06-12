import { useRef, useState } from 'react';
import { FileText, Upload, X } from 'lucide-react';
import FormGroup from '../FormGroup';
import type { OutputSpecFile, SupplementInfo } from '../../types';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

/* 与后端 app/models.py 中 OutputSpecFile 的限制保持一致 */
export const OUTPUT_SPEC_ALLOWED_EXTENSIONS = [
  'md', 'markdown', 'txt', 'json', 'yaml', 'yml', 'csv', 'tsv', 'xml', 'html',
];
export const OUTPUT_SPEC_MAX_BYTES = 65_536; // 64 KB
export const OUTPUT_SPEC_MAX_FILES = 3;

const ACCEPT_ATTR = OUTPUT_SPEC_ALLOWED_EXTENSIONS.map((ext) => `.${ext}`).join(',');

function formatSize(bytes: number) {
  return bytes >= 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${bytes} B`;
}

interface Props {
  supplement: SupplementInfo;
  onUpdate: (supplement: SupplementInfo) => void;
}

export default function SupplementStep({ supplement, onUpdate }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const files = supplement.outputSpecFiles;

  const handleFiles = async (selected: FileList | null) => {
    if (!selected?.length) return;
    setFileError(null);

    const next = [...files];
    for (const file of Array.from(selected)) {
      if (next.length >= OUTPUT_SPEC_MAX_FILES) {
        setFileError(`最多上传 ${OUTPUT_SPEC_MAX_FILES} 个文件。`);
        break;
      }
      const extension = file.name.includes('.')
        ? file.name.split('.').pop()!.toLowerCase()
        : '';
      if (!OUTPUT_SPEC_ALLOWED_EXTENSIONS.includes(extension)) {
        setFileError(
          `「${file.name}」类型不支持。仅支持文本格式：${OUTPUT_SPEC_ALLOWED_EXTENSIONS.join(' / ')}，AI 无法处理二进制文件。`,
        );
        continue;
      }
      if (file.size > OUTPUT_SPEC_MAX_BYTES) {
        setFileError(
          `「${file.name}」为 ${formatSize(file.size)}，超过 ${formatSize(OUTPUT_SPEC_MAX_BYTES)} 上限。请精简为格式样例或规范片段，过大的文件 AI 无法处理。`,
        );
        continue;
      }
      if (next.some((existing) => existing.name === file.name)) {
        setFileError(`「${file.name}」已添加过。`);
        continue;
      }
      let content: string;
      try {
        content = await file.text();
      } catch {
        setFileError(`读取「${file.name}」失败，请重试。`);
        continue;
      }
      if (!content.trim()) {
        setFileError(`「${file.name}」内容为空。`);
        continue;
      }
      next.push({ name: file.name, size: file.size, content });
    }

    if (next.length !== files.length) {
      onUpdate({ ...supplement, outputSpecFiles: next });
    }
    if (inputRef.current) inputRef.current.value = '';
  };

  const removeFile = (target: OutputSpecFile) => {
    setFileError(null);
    onUpdate({
      ...supplement,
      outputSpecFiles: files.filter((file) => file.name !== target.name),
    });
  };

  return (
    <div>
      <Alert className="mb-5 border-accent-border bg-accent-dim text-foreground">
        <AlertDescription>
          这里完全自由填写，也可以留空。生成时它只作为低优先级背景参考，不能覆盖必须遵守的规则。
        </AlertDescription>
      </Alert>

      <FormGroup label="补充说明" hint="可填写额外背景、案例、表达偏好、遗漏信息或临时要求">
        <Textarea
          value={supplement.content}
          onChange={(event) => onUpdate({ ...supplement, content: event.target.value })}
          placeholder="自由填写你还想告诉 Agent 的内容"
          rows={14}
        />
      </FormGroup>

      <FormGroup
        label="输出格式样例文件（可选）"
        hint={`上传期望产出文件的样例或格式规范，AI 会按它约束输出格式。仅支持文本格式（${OUTPUT_SPEC_ALLOWED_EXTENSIONS.join(' / ')}），单个文件不超过 ${formatSize(OUTPUT_SPEC_MAX_BYTES)}，最多 ${OUTPUT_SPEC_MAX_FILES} 个`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT_ATTR}
          multiple
          className="hidden"
          onChange={(event) => void handleFiles(event.target.files)}
        />

        {files.length > 0 && (
          <ul className="mb-3 flex flex-col gap-2">
            {files.map((file) => (
              <li
                key={file.name}
                className="flex items-center justify-between gap-3 rounded-[var(--radius-md)] border border-panel-border bg-surface px-3 py-2"
              >
                <span className="flex min-w-0 items-center gap-2 text-sm">
                  <FileText className="size-4 shrink-0 text-muted-foreground" />
                  <span className="truncate font-mono">{file.name}</span>
                  <span className="shrink-0 text-xs text-muted-foreground" data-numeric>
                    {formatSize(file.size)}
                  </span>
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={`移除 ${file.name}`}
                  className="size-7 shrink-0 text-muted-foreground hover:text-error"
                  onClick={() => removeFile(file)}
                >
                  <X className="size-4" />
                </Button>
              </li>
            ))}
          </ul>
        )}

        <Button
          type="button"
          variant="outline"
          onClick={() => inputRef.current?.click()}
          disabled={files.length >= OUTPUT_SPEC_MAX_FILES}
        >
          <Upload className="size-4" />
          {files.length >= OUTPUT_SPEC_MAX_FILES
            ? `已达 ${OUTPUT_SPEC_MAX_FILES} 个上限`
            : '选择本地文件'}
        </Button>

        {fileError && (
          <Alert className="mt-3 border-warning-border bg-warning-dim text-warning">
            <AlertDescription>{fileError}</AlertDescription>
          </Alert>
        )}
      </FormGroup>
    </div>
  );
}
