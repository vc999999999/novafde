import type { DownloadInfo } from '../types';
import { Button } from '@/components/ui/button';

interface Props {
  info: DownloadInfo;
  onDownload: () => void;
}

export default function DownloadCard({ info, onDownload }: Props) {
  return (
    <div className="flex flex-col items-stretch justify-between gap-4 rounded-[var(--radius-md)] border border-success-border bg-success-dim p-5 shadow-sm">
      <div className="min-w-0">
        <h3 className="break-all text-sm font-semibold">{info.packageName}</h3>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span>v{info.version}</span>
          <span>{info.generatedAt}</span>
          <span>{info.platforms.join(', ')}</span>
          <span>{info.fileCount} 文件</span>
          <span>{info.size}</span>
        </div>
      </div>
      <Button className="w-full" onClick={onDownload} type="button">
        下载 zip
      </Button>
    </div>
  );
}
