export type Locale = "de" | "en"
export type ThemeMode = "light" | "dark"
export type PaymentProvider = "paypal" | "klarna" | "sofort"

export interface CourseSummary {
  id: number
  slug: string
  route_slug?: string
  title: string
  short_description: string
  lessons_count: number
  trial_available: boolean
  price_amount: string
  currency: string
  is_subscription: boolean
  hero_image_url?: string | null
  geo_city: string
  geo_country: string
}

export interface CourseFaqItem {
  id: number
  question: string
  answer: string
  sort_order: number
}

export interface CourseCohort {
  id: number
  name: string
  group_code: string
  capacity: number
  seats_left?: number
  start_date: string | null
  status: string
}

export interface CourseDetail extends CourseSummary {
  description: string
  faq_items: CourseFaqItem[]
  cohorts: CourseCohort[]
  seo_title: string
  seo_description: string
}

export interface SignupPayload {
  course_slug: string
  cohort_id?: number
  email: string
  password: string
  first_name: string
  last_name: string
  phone?: string
  preferred_language: Locale
  idempotency_key?: string
}

export interface CheckoutPayload extends SignupPayload {
  provider: PaymentProvider
  accept_terms: boolean
}

export type CheckoutMode = "trial" | "paid"

export interface SignupResponse {
  profile?: {
    email: string
    first_name: string
    last_name: string
    phone: string
    preferred_language: Locale
    is_trial_user: boolean
  }
  orderId: number
  enrollmentId: number
  emailSent?: boolean
  alreadyProcessed?: boolean
}

export interface PublicStudentProfile {
  email: string
  first_name: string
  last_name: string
  phone: string
  preferred_language: Locale
  is_trial_user: boolean
  gender?: string
  avatar_url?: string | null
}

export interface PublicStudentAuthResponse {
  profile: PublicStudentProfile
}

export interface StudentAccessSummary {
  isAuthenticated: boolean
  hasEnrollments: boolean
  enrollmentsCount: number
  dashboardUrl: string
}

export interface CheckoutStartResponse {
  orderId: number
  status: string
  checkoutUrl: string
  checkoutToken: string
  alreadyProcessed?: boolean
  profile?: SignupResponse["profile"]
}

export interface CheckoutStatusResponse {
  orderId: number
  status: string
  isFinal: boolean
  checkoutToken: string
  courseSlug: string
  groupCode: string
  checkoutUrl: string
  failureReason?: string
  profile?: SignupResponse["profile"]
}

export interface GoogleCheckoutPayload {
  credential: string
  mode: CheckoutMode
  course_slug: string
  cohort_id?: number
  provider?: PaymentProvider
  accept_terms?: boolean
  phone?: string
  preferred_language: Locale
  idempotency_key?: string
}

export interface GoogleCheckoutResponse {
  orderId: number
  status?: string
  checkoutUrl?: string
  checkoutToken?: string
  profile?: SignupResponse["profile"]
  enrollmentId?: number
  emailSent?: boolean
  alreadyProcessed?: boolean
}

export interface MagicLinkRequestPayload {
  email: string
  course_slug?: string
}

export interface MagicLinkRequestResponse {
  detail: string
  emailSent: boolean
  expiresAt?: string
}

export interface PortalEnrollment {
  enrollmentId: number
  status: string
  startedAt: string
  course: {
    id: number
    slug: string
    titleDe: string
    titleEn: string
    lessonsCount: number
    priceAmount: string
    currency: string
  }
  cohort: {
    id: number
    groupCode: string
    groupName: string
    timezone: string
    status: string
  }
}

export interface PublicPortalResponse {
  profile: NonNullable<SignupResponse["profile"]>
  tokenExpiresAt: string
  enrollments: PortalEnrollment[]
}

export interface PortalSession {
  enrollmentId: number
  courseSlug: string
  courseTitleDe: string
  courseTitleEn: string
  groupCode: string
  groupName: string
  id: number
  title: string
  description: string
  starts_at: string
  ends_at: string
  status: string
  join_url: string
  recording_url: string
  is_completed: boolean
  attendance_status: string
  attended_seconds: number
}

export interface PublicPortalSessionsResponse {
  results: PortalSession[]
  tokenExpiresAt: string
}

export interface FeedbackItem {
  id?: number
  avatar_url?: string
  full_name: string
  geo_city: string
  message: string
  rating: number
}

export type WorkspaceSectionKey =
  | "news"
  | "courses"
  | "assignments"
  | "recordings"
  | "materials"

export type WorkspaceKind = "group" | "shared"

export interface WorkspaceSummary {
  id: number
  slug: string
  title: string
  subtitle: string
  summary: string
  iconKey: string
  kind: WorkspaceKind
  sortOrder: number
  showOnHomepage: boolean
  isPublished: boolean
}

export interface WorkspaceListResponse {
  results: WorkspaceSummary[]
}

export interface PublicCourseFinderRecommendation {
  kind: "course" | "workspace" | "library" | string
  title: string
  description: string
  path: string
  actionLabel: string
}

export interface PublicCourseFinderResponse {
  answer: string
  recommendations: PublicCourseFinderRecommendation[]
  followUpPrompts: string[]
  provider: string
  model: string
  resolutionStatus: string
}

export interface WorkspaceCourseItem {
  id: number
  title: string
  description: string
  imageUrl: string
  duration: string
  format: string
  startsAt: string
  endsAt: string
  linkedCourseId: number | null
  linkedCourseSlug: string
  linkedCohortId: number | null
  linkedGroupCode: string
  joinEnabled: boolean
  isAccessible: boolean
  requiredAudienceLabels: string[]
  requiredAudienceSlugs: string[]
  accessMessage: string
}

export interface WorkspaceAssignmentItem {
  id: number
  title: string
  description: string
  notebookLabel: string
  difficulty: string
  isAccessible: boolean
  requiredAudienceLabels: string[]
  requiredAudienceSlugs: string[]
  accessMessage: string
}

export interface WorkspaceRecordingItem {
  id: number
  title: string
  description: string
  date: string
  duration: string
  thumbnailUrl: string
  videoUrl: string
  isAccessible: boolean
  requiredAudienceLabels: string[]
  requiredAudienceSlugs: string[]
  accessMessage: string
}

export interface WorkspaceMaterialItem {
  id: number
  title: string
  description: string
  date: string
  category: string
  documentUrl: string
  isAccessible: boolean
  requiredAudienceLabels: string[]
  requiredAudienceSlugs: string[]
  accessMessage: string
}

export interface WorkspaceRoleSummary {
  slug: string
  name: string
  shortLabel: string
  description: string
  privilegeRank: number
  isInternal: boolean
}

export interface WorkspaceOfficeDefinition {
  slug: string
  title: string
  subtitle: string
  summary: string
  iconKey: string
  kind: WorkspaceKind
  availableSections: WorkspaceSectionKey[]
  roleCatalog: WorkspaceRoleSummary[]
  activeRole: WorkspaceRoleSummary | null
  accessNotice: string
  courses: WorkspaceCourseItem[]
  assignments: WorkspaceAssignmentItem[]
  recordings: WorkspaceRecordingItem[]
  materials: WorkspaceMaterialItem[]
}

export interface WorkspaceCourseJoinResponse {
  enrollmentId: number
  courseId: number
  courseSlug: string
  courseTitle: string
  cohortId: number
  groupCode: string
  status: string
  alreadyJoined: boolean
}
