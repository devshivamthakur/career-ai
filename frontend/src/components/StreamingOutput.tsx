import React, { useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { type TailorStep } from '../hooks/useResumeTailor';

interface StreamingOutputProps {
  content: string;
  steps: TailorStep[];
  isStreaming: boolean;
  error: string | null;
}

const StreamingOutput: React.FC<StreamingOutputProps> = ({
  content,
  steps,
  isStreaming,
  error,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [content]);

  const stripMarkdown = (md: string) => {
    return md
      .replace(/^#+\s+/gm, '') // headers
      .replace(/(\*\*|__)(.*?)\1/g, '$2') // bold
      .replace(/(\*|_)(.*?)\1/g, '$2') // italic
      .replace(/~~(.*?)~~/g, '$1') // strikethrough
      .replace(/`{1,3}(.*?)`{1,3}/g, '$1') // code
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // links
      .replace(/^\s*[-*+]\s+/gm, '• ') // unordered lists
      .replace(/^\s*\d+\.\s+/gm, '• ') // ordered lists
      .replace(/^\s*>\s+/gm, '') // blockquotes
      .replace(/\n{3,}/g, '\n\n') // multiple newlines
      .trim();
  };

  const handleExport = (format: 'txt' | 'pdf') => {
    if (format === 'txt') {
      const cleanText = stripMarkdown(content);
      const blob = new Blob([cleanText], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'tailored-resume.txt';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } else {
      const printWindow = window.open('', '_blank');
      if (printWindow && contentRef.current) {
        const htmlContent = contentRef.current.innerHTML;
        printWindow.document.write(
          `<html>
            <head>
              <title>Tailored Resume</title>
              <style>
                @page { margin: 0; size: A4 portrait; }
                body { font-family: 'Arial', 'Helvetica Neue', Helvetica, sans-serif; line-height: 1.4; color: #000; max-width: 800px; margin: 0 auto; padding: 1.5cm; font-size: 11pt; }
                h1 { font-size: 24pt; text-align: center; margin: 0 0 0.2em 0; text-transform: uppercase; font-weight: 700; letter-spacing: 1px; }
                h1 + p { text-align: center; margin-top: 0; margin-bottom: 1.5em; font-size: 10pt; }
                h2 { display: block; width: 100%; font-size: 13pt; color: #000; margin-top: 1.2em; margin-bottom: 0.5em; text-transform: uppercase; border-bottom: 1px solid #000; padding-bottom: 4px; }
                h3 { font-size: 11pt; color: #111; margin-top: 0.8em; margin-bottom: 0.2em; font-weight: bold; }
                p { margin-bottom: 0.6em; }
                ul, ol { margin-bottom: 0.8em; padding-left: 24px; margin-top: 0.4em; }
                li { margin-bottom: 0.3em; text-align: justify; }
                strong { font-weight: bold; }
                a { color: #000; text-decoration: none; }
              </style>
            </head>
            <body>
              ${htmlContent}
            </body>
          </html>`
        );
        printWindow.document.close();
        
        // Wait a small amount for styles to apply before printing
        setTimeout(() => {
          printWindow.print();
        }, 250);
      }
    }
  };

  const hasContent = content ? content.trim().length > 0 : false;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold text-gray-900">Tailored Resume</h2>
        {isStreaming && (
          <div className="flex items-center space-x-2 text-blue-600">
            <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span className="text-sm font-medium">Streaming...</span>
          </div>
        )}
      </div>

      {/* Progress Steps Checklist */}
      <div className="mb-6 p-4 bg-gray-50 border border-gray-100 rounded-lg space-y-2">
        {steps.map((step) => (
          <div key={step.id} className="flex items-center space-x-3">
            <div className={`flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center ${
              step.status === 'completed' ? 'bg-green-100 text-green-600' :
              step.status === 'in-progress' ? 'bg-blue-100 text-blue-600' :
              step.status === 'error' ? 'bg-red-100 text-red-600' :
              'bg-gray-50 text-gray-300'
            }`}>
              {step.status === 'completed' ? (
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
              ) : step.status === 'in-progress' ? (
                <div className="w-2 h-2 bg-blue-600 rounded-full animate-pulse" />
              ) : (
                <div className="w-1.5 h-1.5 bg-gray-300 rounded-full" />
              )}
            </div>
            <span className={`text-sm ${
              step.status === 'completed' ? 'text-gray-700 font-medium' :
              step.status === 'in-progress' ? 'text-blue-700 font-medium' :
              'text-gray-400'
            }`}>
              {step.label}
              {step.status === 'in-progress' && '...'}
            </span>
          </div>
        ))}
      </div>

      <div ref={scrollRef} className="flex-grow bg-gray-50 border border-gray-200 rounded-lg p-4 overflow-y-auto h-96 relative shadow-inner">
        {error ? (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
            <h3 className="font-semibold text-red-800 mb-2">Error</h3>
            <p className="text-red-700 text-sm">{error}</p>
          </div>
        ) : !hasContent ? (
          <div className="flex items-center justify-center h-full text-gray-500">
            {isStreaming ? "Analyzing and tailoring..." : "Your tailored resume will appear here..."}
          </div>
        ) : (
          <div ref={contentRef} className="prose prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {content}
            </ReactMarkdown>
          </div>
        )}
      </div>

      {hasContent && !isStreaming && !error && (
        <div className="mt-4 flex space-x-2">
          <button
            onClick={() => handleExport('txt')}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            disabled={!hasContent || isStreaming}
          >
            Export as TXT
          </button>
          <button
            onClick={() => handleExport('pdf')}
            className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 disabled:opacity-50"
            disabled={!hasContent || isStreaming}
          >
            Export as PDF
          </button>
        </div>
      )}
    </div>
  );
};

export default StreamingOutput;
