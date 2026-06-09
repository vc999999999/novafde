import type { DownloadInfo } from '../types';
import { Button } from '@/components/ui/button';

interface Props {
  info: DownloadInfo;
  onDownload: () => void;
}

export default function DownloadCard({ info, onDownload }: Props) {
  return (
    <div className="flex items-center justify-between gap-5 p-5 rounded-[var(--radius-lg)] border border-success-border bg-gradient-to-br from-success-dim to-accent/3 shadow-sm">
      <div>
        <h3 className="text-[var(--text-md)] font-semibold">{info.packageName}</h3>
        <div className="flex gap-4 mt-1 text-[var(--text-sm)] text-muted-foreground">
          <span>v{info.version}</span>
          <span>{info.generatedAt}</span>
          <span>{info.platforms.join(', ')}</span>
          <span>{info.fileCount} 文件</span>
          <span>{info.size}</span>
        </div>
      </div>
      <Button onClick={onDownload} type="button">
        下载 zip
      </Button>
    </div>
  );
}