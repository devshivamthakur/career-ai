import { type FC, useState } from 'react';

interface JobDescriptionFormProps {
  onSubmit: (jobDescription: string) => void;
  isLoading?: boolean;
  disabled?: boolean;
  submitLabel?: string;
  helperText?: string;
}

export const JobDescriptionForm: FC<JobDescriptionFormProps> = ({
  onSubmit,
  isLoading = false,
  disabled = false,
  submitLabel = 'Generate',
  helperText,
}) => {
  const [jobDescription, setJobDescription] = useState<string>('');
  const [error, setError] = useState<string>('');
  const CHARACTER_LIMIT = 15000;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!jobDescription.trim()) {
      setError('Please paste a job description');
      return;
    }

    if (jobDescription.trim().length < 50) {
      setError('Job description seems too short. Please provide the complete job posting.');
      return;
    }

    if (jobDescription.length > CHARACTER_LIMIT) {
      setError(`Job description exceeds the ${CHARACTER_LIMIT.toLocaleString()} character limit.`);
      return;
    }

    onSubmit(jobDescription);
  };

  const characterCountColor = jobDescription.length > CHARACTER_LIMIT ? 'text-red-600' : 'text-gray-500';

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="jobDescription" className="block text-sm font-medium text-gray-700 mb-2">
          Job Description
        </label>
        <textarea
          id="jobDescription"
          value={jobDescription}
          onChange={(e) => {
            setJobDescription(e.target.value);
            setError('');
          }}
          placeholder="Paste the job description here. Include the job title, requirements, responsibilities, and any other relevant details..."
          disabled={disabled || isLoading}
          rows={10}
          className="w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-500"
          maxLength={CHARACTER_LIMIT + 500} // Soft limit in textarea, hard limit in validation
        />
        <p className={`mt-1 text-sm text-right ${characterCountColor}`}>
          {jobDescription.length.toLocaleString()} / {CHARACTER_LIMIT.toLocaleString()}
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800 text-sm">
          ✕ {error}
        </div>
      )}

      <button
        type="submit"
        disabled={disabled || isLoading}
        className="w-full inline-flex items-center justify-center px-6 py-3 border border-transparent rounded-lg shadow-sm text-base font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {isLoading ? (
          <>
            <svg className="animate-spin h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Working...
          </>
        ) : (
          <>
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            {submitLabel}
          </>
        )}
      </button>

      <p className="text-xs text-gray-500 text-center">
        {helperText || 'Your job description will be analyzed using AI to generate the best application content.'}
      </p>
    </form>
  );
};

export default JobDescriptionForm;
