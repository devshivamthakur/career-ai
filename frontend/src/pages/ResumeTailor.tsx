import React, { useState } from 'react';
import ResumeUpload from '../components/ResumeUpload';
import JobDescriptionForm from '../components/JobDescriptionForm';
import StreamingOutput from '../components/StreamingOutput';
import useResumeTailor from '../hooks/useResumeTailor';

export const ResumeTailorPage: React.FC = () => {
  const { uploadedResume, isLoading, error, stream, uploadResume, tailorResume } = useResumeTailor();
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [tailoredContent, setTailoredContent] = useState<string>('');
  const [resumeText, setResumeText] = useState<string>('');

  const handleUploadSuccess = async (resumeData: any) => {
    // In a real app, we'd get the full text from the API response
    // For now, we'll use a placeholder
    setResumeText(resumeData.parsed_data.full_text);
    await uploadResume(resumeData.parsed_data.full_text);
  };

  const handleGenerateTailoredResume = async (jobDescription: string) => {
    if (!resumeText) {
      alert('Please upload a resume first');
      return;
    }

    try {
      setIsStreaming(true);
      await tailorResume(resumeText, jobDescription);
    } catch (err) {
      console.error('Error tailoring resume:', err);
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="max-w-6xl mx-auto px-4 py-12">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-gray-900 mb-2">CareerAI</h1>
          <p className="text-xl text-gray-600">Smart Resume Tailor</p>
          <p className="text-sm text-gray-500 mt-2">
            Automatically tailor your resume to match any job description in minutes
          </p>
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left Column: Upload & Job Description */}
          <div className="space-y-8">
            {/* Resume Upload */}
            <div className="bg-white rounded-lg shadow-lg p-8">
              <ResumeUpload
                onUploadSuccess={handleUploadSuccess}
                isLoading={isLoading}
              />
              
              {uploadedResume && (
                <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-lg">
                  <p className="text-sm text-green-800">
                    ✓ Resume ready for tailoring
                  </p>
                </div>
              )}
            </div>

            {/* Job Description Form */}
            {resumeText && (
              <div className="bg-white rounded-lg shadow-lg p-8">
                <JobDescriptionForm
                  onSubmit={handleGenerateTailoredResume}
                  isLoading={isStreaming}
                  disabled={isLoading}
                />
              </div>
            )}
          </div>

          {/* Right Column: Streaming Output */}
          <div className="bg-white rounded-lg shadow-lg p-8">
            <StreamingOutput
              stream={stream}
              isStreaming={isStreaming}
              onComplete={(content) => {
                setTailoredContent(content);
              }}
            />
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mt-8 bg-red-50 border border-red-200 rounded-lg p-6 max-w-2xl mx-auto">
            <h3 className="font-semibold text-red-800 mb-2">Error</h3>
            <p className="text-red-700 text-sm">{error}</p>
          </div>
        )}

        {/* Features Section */}
        <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <div className="text-3xl mb-2">📄</div>
            <h3 className="font-semibold text-gray-900 mb-2">Upload PDF</h3>
            <p className="text-sm text-gray-600">
              Upload your master resume as a PDF. We'll automatically extract and parse it.
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <div className="text-3xl mb-2">⚡</div>
            <h3 className="font-semibold text-gray-900 mb-2">Real-time Tailoring</h3>
            <p className="text-sm text-gray-600">
              Paste any job description and watch as we tailor your resume in real-time using AI.
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <div className="text-3xl mb-2">💾</div>
            <h3 className="font-semibold text-gray-900 mb-2">Export & Share</h3>
            <p className="text-sm text-gray-600">
              Download your tailored resume as PDF or TXT and submit it directly.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ResumeTailorPage;
