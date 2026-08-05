/**
 * Shared input limits — mirror the backend constants
 * (backend/app/utils/constants.py) so validation is consistent.
 */
export const LIMITS = {
  MAX_FILE_SIZE_MB: 10,
  MIN_JOB_DESCRIPTION_LENGTH: 50,
  MAX_JOB_DESCRIPTION_LENGTH: 5000,
  MAX_COMPANY_LENGTH: 100,
  MAX_ROLE_LENGTH: 100,
  MAX_CHAT_MESSAGE_LENGTH: 4000,
  MAX_RESUME_TEXT_LENGTH: 100000,
} as const;

export const MAX_FILE_SIZE_BYTES = LIMITS.MAX_FILE_SIZE_MB * 1024 * 1024;
