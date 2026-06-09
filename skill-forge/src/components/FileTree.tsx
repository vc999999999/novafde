import type { FileNode } from '../types';

interface Props {
  files: FileNode[];
  depth?: number;
}

function FileTreeNode({ node, depth = 0 }: { node: FileNode; depth: number }) {
  const indent = depth * 16;
  return (
    <div>
      <div className="flex items-center gap-2 py-px" style={{ paddingLeft: indent }}>
        <span className={node.type === 'folder' ? 'text-accent' : 'text-muted-foreground'}>
          {node.type === 'folder' ? '▸' : '·'}
        </span>
        <span className={node.type === 'folder' ? 'text-accent' : 'text-muted-foreground'}>
          {node.name}
        </span>
        {node.size && <span className="ml-auto text-[12px] text-tertiary">{node.size}</span>}
      </div>
      {node.children?.map((child) => (
        <FileTreeNode key={child.name} node={child} depth={depth + 1} />
      ))}
    </div>
  );
}

export default function FileTree({ files }: Props) {
  return (
    <div className="font-mono text-[var(--text-sm)] leading-[1.8]">
      {files.map((node) => (
        <FileTreeNode key={node.name} node={node} depth={0} />
      ))}
    </div>
  );
}