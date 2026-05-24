import React, { useEffect, useRef, useState } from 'react';

interface StreamingOutputProps {
  stream: ReadableStream<Uint8Array> | null;
  isStreaming: boolean;
  onComplete?: (content: string) => void;
}

export const StreamingOutput: React.FC<StreamingOutputProps> = ({
  stream,
  isStreaming,
  onComplete,
}) => {
  const [content, setContent] = useState<string>('');
  const [error, setError] = useState<string>('');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!stream) return;

    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let fullContent = '';

    const read = async () => {
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            if (onComplete) {
              onComplete(fullContent);
            }
            break;
          }

          const chunk = decoder.decode(value, { stream: true });
          
          // Parse Server-Sent Events format
          const lines = chunk.split('\n');
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const jsonStr = line.substring(6);
                const data = JSON.parse(jsonStr);
                
                if (data.error) {
                  setError(data.error);
                } else if (data.content) {
                  fullContent += data.content;
                  setContent(fullContent);
                  // Auto-scroll to bottom
                  setTimeout(() => {
                    scrollRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
                  }, 0);
                }
              } catch (e) {
                console.error('Failed to parse SSE data:', e);
              }
            }
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Streaming error');
      }
    };

    read();
  }, [stream, onComplete]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
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

      <div
        ref={scrollRef}
        className="bg-white border border-gray-300 rounded-lg p-6 min-h-96 max-h-screen overflow-y-auto shadow-sm"
      >
        {content ? (
          <pre className="font-mono text-sm text-gray-800 whitespace-pre-wrap break-words">
            {content}
          </pre>
        ) : (
          <div className="flex items-center justify-center h-96 text-gray-400">
            {isStreaming ? (
              <div className="text-center">
                <svg className="animate-spin h-12 w-12 mx-auto mb-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <p>Generating your tailored resume...</p>
              </div>
            ) : (
              <p>Your tailored resume will appear here</p>
            )}
          </div>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
          <p className="font-semibold">Error</p>
          <p className="text-sm">{error}</p>
        </div>
      )}

      {!isStreaming && content && (
        <div className="flex space-x-3">
          <button
            onClick={() => {
              const element = document.createElement('a');
              element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(content));
              element.setAttribute('download', 'tailored_resume.txt');
              element.style.display = 'none';
              document.body.appendChild(element);
              element.click();
              document.body.removeChild(element);
            }}
            className="flex-1 inline-flex items-center justify-center px-4 py-2 border border-gray-300 rounded-lg shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Download as TXT
          </button>
          <button
            onClick={() => {
              const element = document.createElement('a');
              element.setAttribute('href', 'data:text/html;charset=utf-8,' + encodeURIComponent(`<pre>${content}</pre>`));
              element.setAttribute('download', 'tailored_resume.html');
              element.style.display = 'none';
              document.body.appendChild(element);
              element.click();
              document.body.removeChild(element);
            }}
            className="flex-1 inline-flex items-center justify-center px-4 py-2 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700"
          >
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
            </svg>
            Export as PDF
          </button>
        </div>
      )}
    </div>
  );
};

export default StreamingOutput;
