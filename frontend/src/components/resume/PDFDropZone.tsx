import { memo, useState, useRef, type DragEvent, type ChangeEvent } from 'react';
import { Upload, FileText, CheckCircle2, X, AlertCircle } from 'lucide-react';

interface PDFDropZoneProps {
  onFileSelect: (file: File | null) => void;
  currentFile: File | null;
  maxSizeMB?: number;
  disabled?: boolean;
}

export const PDFDropZone = memo(function PDFDropZone({
  onFileSelect,
  currentFile,
  maxSizeMB = 10,
  disabled,
}: PDFDropZoneProps) {
  const [isDragover, setIsDragover] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const maxBytes = maxSizeMB * 1024 * 1024;

  function validateAndSet(file: File) {
    setError(null);

    if (file.type !== 'application/pdf') {
      setError('Only PDF files are accepted');
      return;
    }

    if (file.size > maxBytes) {
      setError(`File exceeds ${maxSizeMB}MB limit`);
      return;
    }

    onFileSelect(file);
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    setIsDragover(false);
    if (disabled) return;

    const file = e.dataTransfer.files[0];
    if (file) validateAndSet(file);
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
    if (!disabled) setIsDragover(true);
  }

  function handleDragLeave() {
    setIsDragover(false);
  }

  function handleInputChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) validateAndSet(file);
    e.target.value = '';
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  // Success state
  if (currentFile) {
    return (
      <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-success/10 border border-success/30">
        <FileText size={20} className="text-success shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-text-primary font-medium truncate">{currentFile.name}</p>
          <p className="text-xs text-text-secondary">{formatSize(currentFile.size)}</p>
        </div>
        <CheckCircle2 size={18} className="text-success shrink-0" />
        <button
          onClick={() => onFileSelect(null)}
          disabled={disabled}
          className="p-1 text-text-secondary hover:text-danger transition-colors shrink-0"
        >
          <X size={16} />
        </button>
      </div>
    );
  }

  return (
    <div>
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => inputRef.current?.click()}
        className={`flex flex-col items-center justify-center gap-3 px-6 py-10 rounded-lg border-2 border-dashed cursor-pointer transition-colors ${
          isDragover
            ? 'border-accent bg-accent/5'
            : error
              ? 'border-danger/50 bg-danger/5'
              : 'border-border hover:border-accent/40 hover:bg-bg-elevated/50'
        } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        {error ? (
          <AlertCircle size={28} className="text-danger" />
        ) : (
          <Upload size={28} className="text-text-secondary" />
        )}
        <div className="text-center">
          {error ? (
            <p className="text-sm text-danger">{error}</p>
          ) : (
            <>
              <p className="text-sm text-text-primary font-medium">Drop your resume PDF here</p>
              <p className="text-xs text-text-secondary mt-1">or click to upload (max {maxSizeMB}MB)</p>
            </>
          )}
        </div>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,application/pdf"
        onChange={handleInputChange}
        className="hidden"
      />
    </div>
  );
});
