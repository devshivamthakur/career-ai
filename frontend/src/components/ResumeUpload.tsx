import React, { useRef, useState } from 'react';
import { API_BASE_URL } from '../api/client';

interface ResumeUploadProps {
  onUploadSuccess: (resumeData: any) => void;
  isLoading?: boolean;
}

export const ResumeUpload: React.FC<ResumeUploadProps> = ({ 
  onUploadSuccess, 
  isLoading = false 
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [error, setError] = useState<string>('');
  const [fileName, setFileName] = useState<string>('');

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setFileName(file.name);
    setError('');

    if (file.type !== 'application/pdf') {
      setError('Please upload a PDF file');
      return;
    }

    handleUpload(file);
  };

  const handleUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    try {
      setUploadProgress(0);
      
      const response = await fetch(`${API_BASE_URL}/resume/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      const data = await response.json();
      setUploadProgress(100);
      
      // Give visual feedback before resetting
      setTimeout(() => {
        setUploadProgress(0);
        onUploadSuccess(data.data);
      }, 500);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
      setUploadProgress(0);
    }
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
      setFileName(file.name);
      handleUpload(file);
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-gray-900">Upload Master Resume</h2>
      
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
          disabled={isLoading || uploadProgress > 0}
        />
        
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading || uploadProgress > 0}
          className="inline-flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Choose PDF or Drag & Drop
        </button>

        {fileName && (
          <p className="mt-2 text-sm text-gray-600">
            Selected: <span className="font-semibold">{fileName}</span>
          </p>
        )}
      </div>

      {uploadProgress > 0 && uploadProgress < 100 && (
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="bg-blue-600 h-2 rounded-full transition-all duration-300"
            style={{ width: `${uploadProgress}%` }}
          ></div>
        </div>
      )}

      {uploadProgress === 100 && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-green-800">
          ✓ Resume uploaded and parsed successfully
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
          ✕ {error}
        </div>
      )}
    </div>
  );
};

export default ResumeUpload;
