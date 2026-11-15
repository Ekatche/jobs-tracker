export { getApiBaseUrl } from "./api/client";
export { setupTokenRefresh, refreshAccessToken } from "./api/tokenRefresh";

export type {
  User,
  Application,
  JobOffer,
  OfferEvaluation,
  BlocA,
  BlocB,
  BlocG,
  BlocH,
  DraftApplicationAnswer,
  RiskSummaryItem,
  ImportanceEvidenceTier,
  RequirementMatch,
  MissingRequirement,
  UserOfferInteraction,
  UserOfferInteractionStatus,
  ScoreCalibrationBucket,
  ScoreCalibrationResponse,
  SkillGapItem,
  JdSkillGapsResponse,
  JobOfferFilter,
  JobOfferStats,
  CollectionSchedule,
} from "./api/types";

import { authApi, userApi, taskApi, applicationApi } from "./api/coreApis";
import { jobOffersApi } from "./api/offersApi";
import { coverLetterApi, resumeApi } from "./api/generationApi";
import { interviewPrepApi, starBankApi, usageApi, adminApi } from "./api/coachingUsageApi";

export {
  authApi,
  userApi,
  taskApi,
  applicationApi,
  jobOffersApi,
  coverLetterApi,
  resumeApi,
  interviewPrepApi,
  starBankApi,
  usageApi,
  adminApi,
};

const api = {
  auth: authApi,
  users: userApi,
  applications: applicationApi,
  tasks: taskApi,
  jobOffers: jobOffersApi,
  coverLetters: coverLetterApi,
  resumes: resumeApi,
  interviewPrep: interviewPrepApi,
  starBank: starBankApi,
  usage: usageApi,
  admin: adminApi,
};

export default api;
