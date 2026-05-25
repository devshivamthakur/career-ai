import React, { useRef, useState } from 'react';

interface ResumeUploadProps {
  onFileSelect: (file: File) => void;
  isLoading?: boolean;
}

export const ResumeUpload: React.FC<ResumeUploadProps> = ({ 
  onFileSelect, 
  isLoading = false 
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState<string>('');
  const [error, setError] = useState<string>('');

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setFileName(file.name);
    setError('');

    if (file.type !== 'application/pdf') {
      setError('Please upload a PDF file');
      setFileName('');
      return;
    }

    if (file.size > 10 * 1024 * 1024) { // 10MB limit
      setError('File is too large (max 10MB)');
      setFileName('');
      return;
    }

    onFileSelect(file);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.currentTarget.classList.add('bg-blue-50');
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.currentTarget.classList.remove('bg-blue-50');
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.currentTarget.classList.remove('bg-blue-50');
    
    const file = e.dataTransfer.files?.[0];
    if (file) {
      if (file.type === 'application/pdf') {
        setFileName(file.name);
        setError('');
        onFileSelect(file);
      } else {
        setError('Please drop a PDF file');
        setFileName('');
      }
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-gray-900">Upload Your Resume</h2>
      
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-blue-400 transition-colors"
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          onChange={handleFileSelect}
          className="hidden"
          disabled={isLoading}
        />
        
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading}
          className="inline-flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Choose PDF or Drag & Drop
        </button>

        {fileName && (
          <p className="mt-2 text-sm text-gray-600">
            Selected: <span className="font-semibold text-green-600">✓ {fileName}</span>
          </p>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800 text-sm">
          ✕ {error}
        </div>
      )}

      <p className="text-xs text-gray-500">
        Supported: PDF files up to 10MB. Your resume will be processed securely.
      </p>
    </div>
  );
};

export default ResumeUpload;
