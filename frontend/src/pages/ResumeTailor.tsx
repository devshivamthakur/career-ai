import React, { useState } from 'react';
import ResumeUpload from '../components/ResumeUpload';
import JobDescriptionForm from '../components/JobDescriptionForm';
import StreamingOutput from '../components/StreamingOutput';
import useResumeTailor from '../hooks/useResumeTailor';

export const ResumeTailorPage: React.FC = () => {
  const { isLoading, error, content, matchedSkills, missingSkills, atsScore, steps, tailorResume } = useResumeTailor();
  const [cvFile, setCvFile] = useState<File | null>(null);

  console.log(content,"jfhfh")
  const handleFileSelect = (file: File) => {
    setCvFile(file);
  };

  const handleGenerateTailoredResume = async (jobDescription: string) => {
    if (!cvFile) {
      alert('Please upload a resume first');
      return;
    }
    try {
      await tailorResume(cvFile, jobDescription);
    } catch (err) {
      console.error('Error in tailorResume:', err);
      // The hook will set the error state, so we don't need to do it here.
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
                onFileSelect={handleFileSelect}
                isLoading={isLoading}
              />
              
              {cvFile && (
                <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-lg">
                  <p className="text-sm text-green-800">
                    ✓ Resume ready: {cvFile.name}
                  </p>
                </div>
              )}
            </div>

            {/* Job Description Form */}
            {cvFile && (
              <div className="bg-white rounded-lg shadow-lg p-8">
                <JobDescriptionForm
                  onSubmit={handleGenerateTailoredResume}
                  isLoading={isLoading}
                  disabled={isLoading}
                />
              </div>
            )}

            {!cvFile && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 text-center">
                <p className="text-sm text-blue-800">
                  👆 Upload your resume first to get started
                </p>
              </div>
            )}
          </div>

          {/* Right Column: Streaming Output */}
          <div className="bg-white rounded-lg shadow-lg p-8 flex flex-col space-y-6">
            
            {/* ATS Score & Skills Match Section */}
            {(matchedSkills.length > 0 || missingSkills.length > 0 || atsScore !== null) && (
              <div className="flex flex-col space-y-4">
                {atsScore !== null && (
                  <div className="flex items-center justify-between p-4 bg-gradient-to-r from-indigo-50 to-blue-50 border border-indigo-100 rounded-lg">
                    <div>
                      <h3 className="font-semibold text-indigo-900 flex items-center">
                        <svg className="w-5 h-5 mr-2 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                        Original Resume ATS Match Score
                      </h3>
                      <p className="text-sm text-indigo-700 mt-1">Based on comparison with the job description</p>
                    </div>
                    <div className="relative w-16 h-16 flex items-center justify-center">
                      <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                        <path className="text-indigo-100" strokeWidth="3" stroke="currentColor" fill="none" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
                        <path className={atsScore >= 75 ? "text-green-500" : atsScore >= 50 ? "text-yellow-500" : "text-red-500"} strokeWidth="3" strokeDasharray={`${atsScore}, 100`} stroke="currentColor" fill="none" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
                      </svg>
                      <span className="absolute text-lg font-bold text-indigo-900">{atsScore}%</span>
                    </div>
                  </div>
                )}
                
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 bg-green-50 border border-green-100 rounded-lg flex flex-col">
                    <h3 className="font-semibold text-green-800 mb-2 flex items-center shrink-0">
                      <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
                      Matched Skills
                    </h3>
                    <div className="flex flex-wrap gap-1 max-h-32 overflow-y-auto pr-1">
                      {matchedSkills.map((skill, idx) => (
                        <span key={idx} className="px-2 py-1 bg-green-200 text-green-800 text-xs rounded-full">{skill}</span>
                      ))}
                      {matchedSkills.length === 0 && <span className="text-sm text-green-600">None found</span>}
                    </div>
                  </div>
                  <div className="p-4 bg-red-50 border border-red-100 rounded-lg flex flex-col">
                    <h3 className="font-semibold text-red-800 mb-2 flex items-center shrink-0">
                      <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                      Missing Skills
                    </h3>
                    <div className="flex flex-wrap gap-1 max-h-32 overflow-y-auto pr-1">
                      {missingSkills.map((skill, idx) => (
                        <span key={idx} className="px-2 py-1 bg-red-200 text-red-800 text-xs rounded-full">{skill}</span>
                      ))}
                      {missingSkills.length === 0 && <span className="text-sm text-red-600">None found</span>}
                    </div>
                  </div>
                </div>
              </div>
            )}

            <StreamingOutput
              content={content}
              steps={steps}
              isStreaming={isLoading}
              error={error}
            /> 
          </div>
        </div>

        {/* Features Section */}
        <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <div className="text-3xl mb-2">📄</div>
            <h3 className="font-semibold text-gray-900 mb-2">Upload PDF</h3>
            <p className="text-sm text-gray-600">
              Upload your resume as a PDF. We extract the text and AI handles the analysis.
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <div className="text-3xl mb-2">⚡</div>
            <h3 className="font-semibold text-gray-900 mb-2">Real-time Tailoring</h3>
            <p className="text-sm text-gray-600">
              Paste any job description and watch as AI tailors your resume in real-time using advanced analysis.
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <div className="text-3xl mb-2">💾</div>
            <h3 className="font-semibold text-gray-900 mb-2">Export & Share</h3>
            <p className="text-sm text-gray-600">
              Download your tailored resume as PDF or TXT and submit it directly to employers.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ResumeTailorPage;
