/**
 * Server-side API client.
 *
 * The web service holds no secrets, touches no database and makes no
 * authorisation decisions — every piece of data comes from the API over HTTP.
 * Keeping that boundary strict is what makes the frontend replaceable.
 */

const INTERNAL_BASE = process.env.API_INTERNAL_URL ?? "http://api:8000";

export type CurrentUser = {
  id: string;
  email: string;
  display_name: string;
  role: string;
};

export type DashboardTopic = {
  slug: string;
  title: string;
  course: string;
  estimated_minutes: number;
};

export type Dashboard = {
  display_name: string;
  completed: DashboardTopic[];
  in_progress: DashboardTopic[];
  available: DashboardTopic[];
  next_topic: DashboardTopic | null;
  recent_attempts: { score: number; passed: boolean; submitted_at: string }[];
  weak_objectives: { code: string; statement: string; wrong: number; total: number }[];
  totals: { topics_completed: number; topics_total: number; quizzes_passed: number };
};

export type QuizQuestion = {
  id: string;
  type: string;
  level: string;
  stem: string;
  options: { id: string; text: string }[];
};

export type QuizPaper = {
  topic_slug: string;
  pass_score: number;
  question_count: number;
  questions: QuizQuestion[];
};

export type Scenario = {
  id: string;
  title: string;
  level: string;
  reveal_policy: string;
  situation: string;
  symptoms: string[];
  artifacts: { type: string; label: string; content: string }[];
  diagnostic_questions: string[];
};

export type LabDetail = {
  slug: string;
  title: string;
  type: string;
  tier: number;
  image: string;
  duration_minutes: number;
  objectives: string[];
  intro: string;
  steps: { id: string; instruction: string; hint: string | null }[];
};

export type OutlineStep = {
  slug: string;
  kind: string;
  title: string;
  subtitle: string | null;
  entity_type: string;
  entity_id: string;
  estimated_minutes: number | null;
  level: string | null;
};

export type TopicOutline = {
  topic_slug: string;
  topic_title: string;
  course: TopicNav;
  module: TopicNav;
  estimated_minutes: number;
  steps: OutlineStep[];
};

export type Exercise = {
  id: string;
  title: string;
  level: string;
  kind: string;
  prompt: string;
};

export type InterviewQuestion = {
  id: string;
  level: string;
  question: string;
  follow_ups: string[];
};

export type AssessmentPart = {
  id: string;
  title: string;
  kind: string;
  prompt: string;
};

export type ProgressRow = {
  entity_type: string;
  entity_id: string;
  status: string;
  score: number | null;
  attempts: number;
  completed_at: string | null;
};

export type PlatformInfo = {
  name: string;
  environment: string;
  api_version: string;
  content_versions_ingested: number;
  database: string;
};

export type RoadmapTopic = {
  slug: string;
  title: string;
  levels: string[];
  estimated_minutes: number;
  status: string;
};

export type RoadmapModule = {
  slug: string;
  title: string;
  topics: RoadmapTopic[];
};

export type RoadmapCourse = {
  slug: string;
  code: string;
  title: string;
  summary: string;
  track: string;
  levels: string[];
  estimated_hours: number;
  modules: RoadmapModule[];
  topic_count: number;
  published_topic_count: number;
};

export type Roadmap = {
  path_slug: string;
  title: string;
  summary: string;
  courses: RoadmapCourse[];
  total_topics: number;
  published_topics: number;
  content_version: string | null;
  ingested_at: string | null;
};

export type CourseTopic = {
  slug: string;
  title: string;
  summary: string;
  order: number;
  levels: string[];
  estimated_minutes: number;
  status: string;
  tags: string[];
};

export type CourseModule = {
  slug: string;
  title: string;
  summary: string;
  order: number;
  topics: CourseTopic[];
};

export type CourseDetail = {
  slug: string;
  code: string;
  title: string;
  summary: string;
  track: string;
  levels: string[];
  estimated_hours: number;
  order: number;
  topic_count: number;
  modules: CourseModule[];
};

export type Lesson = {
  section: string;
  title: string;
  mode: string;
  order: number;
  body_md: string;
};

export type Objective = {
  code: string;
  level: string;
  verb: string;
  statement: string;
};

export type LabSummary = {
  slug: string;
  title: string;
  type: string;
  tier: number;
  duration_minutes: number;
  objectives: string[];
};

export type TopicNav = { slug: string; title: string };

export type TopicDetail = {
  slug: string;
  title: string;
  summary: string;
  levels: string[];
  estimated_minutes: number;
  status: string;
  tags: string[];
  terminology: { term: string; definition: string }[];
  foreshadows: string[];
  course: TopicNav;
  module: TopicNav;
  previous: TopicNav | null;
  next: TopicNav | null;
  objectives: Objective[];
  prerequisites: { slug: string; title: string; hardness: string }[];
  lessons: Lesson[];
  labs: LabSummary[];
  has_quiz: boolean;
  exercise_count: number;
  troubleshooting_count: number;
  interview_count: number;
  assessment_part_count: number;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
    options?: { cause?: unknown },
  ) {
    // Preserving the cause matters: without it, a DNS failure and a refused
    // connection produce the same useless message in the logs.
    super(message, options);
    this.name = "ApiError";
  }
}

async function apiGet<T>(
  path: string,
  revalidateSeconds = 0,
  headers: Record<string, string> = {},
): Promise<T> {
  const url = `${INTERNAL_BASE}/v1${path}`;
  let response: Response;

  try {
    response = await fetch(url, {
      headers: { accept: "application/json", ...headers },
      // Anything carrying a session cookie must never be cached — a cached
      // dashboard is one user's progress served to another.
      cache: Object.keys(headers).length > 0 ? "no-store" : undefined,
      next: Object.keys(headers).length > 0 ? undefined : { revalidate: revalidateSeconds },
    });
  } catch (cause) {
    throw new ApiError(`Could not reach the API at ${url}`, undefined, { cause });
  }

  if (!response.ok) {
    throw new ApiError(`API responded ${response.status} for ${path}`, response.status);
  }

  return (await response.json()) as T;
}

export function getPlatformInfo(): Promise<PlatformInfo> {
  return apiGet<PlatformInfo>("/meta", 10);
}

export type SearchHit = {
  entity_type: string;
  title: string;
  subtitle: string | null;
  url: string;
  topic_slug: string | null;
  topic_title: string | null;
  snippet: string | null;
};

export type SearchResults = { query: string; total: number; hits: SearchHit[] };

export function search(query: string, type?: string): Promise<SearchResults> {
  const params = new URLSearchParams({ q: query });
  if (type) params.set("type", type);
  // No cache: a search result should reflect the corpus as it is now, and the
  // query space is unbounded so caching buys nothing anyway.
  return apiGet<SearchResults>(`/search?${params}`, 0);
}

export type CertificateVerification = {
  code: string;
  valid: boolean;
  holder_name: string;
  course_code: string;
  course_title: string;
  topics_completed: number;
  weakest_objective_score: number;
  issued_at: string;
};

export type Achievement = {
  code: string;
  scope: string;
  title: string;
  detail: string;
  earned_at: string | null;
};

/** Public — no session required, which is the point of a verifiable credential. */
export function verifyCertificate(code: string): Promise<CertificateVerification> {
  return apiGet<CertificateVerification>(`/certificates/${encodeURIComponent(code)}`, 0);
}

export function getMyAchievements(): Promise<Achievement[] | null> {
  return apiGetAuthed<Achievement[]>("/achievements");
}

export type RubricCriterion = {
  id: string;
  criterion: string;
  excellent: string;
  adequate: string;
  inadequate: string;
  evidence: string;
  weight: number;
};

export type ProjectSummary = {
  slug: string;
  title: string;
  level: string;
  estimated_hours: number;
  summary: string;
  requires_topics: string[];
  unlocked: boolean;
};

export type ProjectDetail = ProjectSummary & {
  brief: string;
  constraints: string[];
  deliverables: string[];
  rubric: RubricCriterion[];
  going_further: string[];
  missing_topics: string[];
};

export function getProjects(): Promise<ProjectSummary[]> {
  return apiGet<ProjectSummary[]>("/projects", 0);
}

/** Authenticated so the lock state and brief reflect this learner's progress. */
export function getProject(slug: string): Promise<ProjectDetail | null> {
  return apiGetAuthed<ProjectDetail>(`/projects/${encodeURIComponent(slug)}`);
}

export function getRoadmap(): Promise<Roadmap> {
  return apiGet<Roadmap>("/roadmap", 10);
}

export function getTopic(slug: string): Promise<TopicDetail> {
  return apiGet<TopicDetail>(`/topics/${encodeURIComponent(slug)}`, 10);
}

export function getCourse(slug: string): Promise<CourseDetail> {
  return apiGet<CourseDetail>(`/courses/${encodeURIComponent(slug)}`, 10);
}

/** Authenticated reads. Return null when the caller is not signed in. */
async function apiGetAuthed<T>(path: string): Promise<T | null> {
  const { sessionHeader } = await import("./session");
  const headers = await sessionHeader();
  if (!headers.cookie) return null;

  try {
    return await apiGet<T>(path, 0, headers);
  } catch (cause) {
    if (cause instanceof ApiError && (cause.status === 401 || cause.status === 403)) return null;
    throw cause;
  }
}

export function getCurrentUser(): Promise<CurrentUser | null> {
  return apiGetAuthed<CurrentUser>("/auth/me");
}

export function getDashboard(): Promise<Dashboard | null> {
  return apiGetAuthed<Dashboard>("/dashboard");
}

export function getMyProgress(): Promise<ProgressRow[] | null> {
  return apiGetAuthed<ProgressRow[]>("/progress/me");
}

export function getQuiz(slug: string): Promise<QuizPaper> {
  return apiGet<QuizPaper>(`/topics/${encodeURIComponent(slug)}/quiz`, 10);
}

export function getScenarios(slug: string): Promise<Scenario[]> {
  return apiGet<Scenario[]>(`/topics/${encodeURIComponent(slug)}/troubleshooting`, 10);
}

export function getLab(topicSlug: string, labSlug: string): Promise<LabDetail> {
  return apiGet<LabDetail>(
    `/topics/${encodeURIComponent(topicSlug)}/labs/${encodeURIComponent(labSlug)}`,
    10,
  );
}

export function getOutline(slug: string): Promise<TopicOutline> {
  return apiGet<TopicOutline>(`/topics/${encodeURIComponent(slug)}/outline`, 10);
}

export function getExercises(slug: string): Promise<Exercise[]> {
  return apiGet<Exercise[]>(`/topics/${encodeURIComponent(slug)}/exercises`, 10);
}

export function getInterview(slug: string): Promise<InterviewQuestion[]> {
  return apiGet<InterviewQuestion[]>(`/topics/${encodeURIComponent(slug)}/interview`, 10);
}

export function getAssessment(slug: string): Promise<AssessmentPart[]> {
  return apiGet<AssessmentPart[]>(`/topics/${encodeURIComponent(slug)}/assessment`, 10);
}

/* ------------------------------------------------------------------ authoring
 *
 * Admin-only. These read the content tree on disk and report on it; the one
 * mutation is a re-ingest. Content itself stays in files under version control
 * — see services/api/app/api/v1/authoring.py for why that boundary is where it
 * is.
 */

export type DoneState = {
  present: Record<string, number>;
  missing: string[];
  warnings: string[];
  blocking: boolean;
};

export type InventoryTopic = {
  id: string;
  slug: string;
  title: string;
  status: string;
  levels: string[];
  objectives: number;
  done: DoneState;
};

export type InventoryModule = {
  id: string;
  slug: string;
  title: string;
  order: number;
  topics: InventoryTopic[];
};

export type InventoryCourse = {
  id: string;
  code: string;
  slug: string;
  title: string;
  order: number;
  modules: InventoryModule[];
};

export type Inventory = {
  courses: InventoryCourse[];
  projects: { id: string; slug: string; title: string; level: string }[];
  // Concrete rather than Record<string, number>: with noUncheckedIndexedAccess
  // an index into a Record is `number | undefined`, and these are always present.
  totals: {
    courses: number;
    modules: number;
    topics: number;
    lessons: number;
    labs: number;
    projects: number;
    incomplete: number;
  };
};

export type LintFinding = { rule: string; where: string; message: string };

export type LintReport = {
  ok: boolean;
  parse_errors: { where: string; message: string }[];
  errors: LintFinding[];
  warnings: LintFinding[];
  counts: { parse_errors: number; errors: number; warnings: number };
};

export function getInventory(headers: Record<string, string>): Promise<Inventory> {
  return apiGet<Inventory>("/authoring/inventory", 0, headers);
}

export function getLintReport(headers: Record<string, string>): Promise<LintReport> {
  return apiGet<LintReport>("/authoring/lint", 0, headers);
}
