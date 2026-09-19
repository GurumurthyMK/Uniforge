const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ApiErrorEnvelope = {
  error: { code: string; message: string; details: unknown };
};

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(code: string, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

type FetchOptions = {
  token?: string | null;
  method?: string;
  body?: unknown;
};

async function request<T>(path: string, opts: FetchOptions = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (opts.token) headers["Authorization"] = `Bearer ${opts.token}`;
  const res = await fetch(`${API_BASE}${path}`, {
    method: opts.method ?? (opts.body !== undefined ? "POST" : "GET"),
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    cache: "no-store",
  });
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      body = null;
    }
    if (typeof body === "object" && body !== null && "error" in body) {
      const err = (body as ApiErrorEnvelope).error;
      throw new ApiError(String(err.code), String(err.message), res.status);
    }
    throw new ApiError("HTTP_ERROR", `API request failed: ${res.status}`, res.status);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export type HealthResponse = { status: string; service: string; version: string };
export type ReadyResponse = { status: string; database: string };

export function getApiHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/v1/health");
}

export function getApiReady(): Promise<ReadyResponse> {
  return request<ReadyResponse>("/api/v1/ready");
}

export function apiBaseUrl(): string {
  return API_BASE;
}

// ---- Identity types ----

export type Role =
  | "UNIVERSITY_ADMIN"
  | "DEPARTMENT_ADMIN"
  | "FACULTY"
  | "STAFF"
  | "CLASS_REP"
  | "STUDENT";

export type IdentityStatus = "PENDING" | "VERIFIED" | "REJECTED";

export type University = {
  id: string;
  name: string;
  code: string;
  email_domain: string;
  city: string | null;
  country: string | null;
};

export type ClassInfo = {
  id: string;
  batch_id: string;
  name: string;
  code: string;
  batch_name: string | null;
  program_name: string | null;
  department_name: string | null;
};

export type Identity = {
  id: string;
  university_id: string;
  university_name: string | null;
  role: Role;
  status: IdentityStatus;
  student_no: string | null;
  class_id: string | null;
  class_name: string | null;
  photo_url: string | null;
  verified_at: string | null;
};

export type Profile = {
  display_name: string | null;
  bio: string | null;
  headline?: string | null;
  avatar_url?: string | null;
};

export type Me = {
  id: string;
  email: string;
  profile: Profile;
  identities: Identity[];
};

export type AuthResponse = { token: string; expires_at: string; user: Me };

export type RegisterInput = {
  email: string;
  password: string;
  display_name: string;
  university_id: string;
  class_id: string;
  student_no: string;
  enrollment_code: string;
};

// ---- Identity API ----

export function listUniversities(): Promise<University[]> {
  return request<University[]>("/api/v1/universities");
}

export function listClasses(universityId: string): Promise<ClassInfo[]> {
  return request<ClassInfo[]>(`/api/v1/universities/${universityId}/classes`);
}

export function register(input: RegisterInput): Promise<AuthResponse> {
  return request<AuthResponse>("/api/v1/auth/register", { body: input });
}

export function login(email: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>("/api/v1/auth/login", { body: { email, password } });
}

export function logout(token: string): Promise<void> {
  return request<void>("/api/v1/auth/logout", { token });
}

export function fetchMe(token: string): Promise<Me> {
  return request<Me>("/api/v1/auth/me", { token });
}

export function updateProfile(token: string, input: { display_name?: string; bio?: string }): Promise<Profile> {
  return request<Profile>("/api/v1/auth/profile", { token, method: "PATCH", body: input });
}

// ---- Profile & directory types ----

export type AcademicNode = { id: string; name: string };

export type AcademicContext = {
  university: AcademicNode;
  department: AcademicNode | null;
  program: AcademicNode | null;
  batch: AcademicNode | null;
  class: AcademicNode | null;
};

export type InterestTag = { name: string; kind: "INTEREST" | "HOBBY" };

export type FullProfile = {
  user_id: string;
  display_name: string | null;
  headline: string | null;
  bio: string | null;
  avatar_url: string | null;
  github_url: string | null;
  linkedin_url: string | null;
  portfolio_url: string | null;
  website_url: string | null;
  career_interests: string | null;
  research_interests: string | null;
  skills: string[];
  interests: InterestTag[];
  academic_context: AcademicContext | null;
  role: Role | null;
  verification_status: IdentityStatus | null;
  photo_url: string | null;
};

export type PublicProfile = Omit<FullProfile, "role" | "verification_status" | "photo_url"> & {
  role: Role;
  verification_status: IdentityStatus;
};

export type ProfileEdit = {
  display_name?: string;
  headline?: string;
  bio?: string;
  avatar_url?: string;
  github_url?: string;
  linkedin_url?: string;
  portfolio_url?: string;
  website_url?: string;
  career_interests?: string;
  research_interests?: string;
  skills?: string[];
  interests?: string[];
  hobbies?: string[];
};

export type ClassMember = {
  user_id: string;
  display_name: string | null;
  role: Role;
  verification_status: IdentityStatus;
};

export type ClassDetail = {
  class: AcademicNode;
  batch: AcademicNode;
  program: AcademicNode;
  department: AcademicNode;
  university: AcademicNode;
  member_count: number;
  class_rep: ClassMember | null;
};

export type ClassMembersPage = {
  items: ClassMember[];
  total: number;
  limit: number;
  offset: number;
};

export type StructureClass = { id: string; name: string; code: string; member_count: number };
export type StructureBatch = { id: string; name: string; start_year: number | null; classes: StructureClass[] };
export type StructureProgram = {
  id: string;
  name: string;
  code: string;
  degree_level: string | null;
  batches: StructureBatch[];
};
export type StructureDepartment = { id: string; name: string; code: string; programs: StructureProgram[] };
export type Structure = { university_id: string; university_name: string; departments: StructureDepartment[] };

// ---- Profile & directory API ----

export function fetchMyProfile(token: string): Promise<FullProfile> {
  return request<FullProfile>("/api/v1/profile/me", { token });
}

export function saveMyProfile(token: string, input: ProfileEdit): Promise<FullProfile> {
  return request<FullProfile>("/api/v1/profile/me", { token, method: "PATCH", body: input });
}

export function fetchPublicProfile(token: string, userId: string): Promise<PublicProfile> {
  return request<PublicProfile>(`/api/v1/profile/users/${userId}`, { token });
}

export function fetchClassDetail(token: string, classId: string): Promise<ClassDetail> {
  return request<ClassDetail>(`/api/v1/directory/classes/${classId}`, { token });
}

export function fetchClassMembers(
  token: string,
  classId: string,
  limit = 30,
  offset = 0
): Promise<ClassMembersPage> {
  return request<ClassMembersPage>(
    `/api/v1/directory/classes/${classId}/members?limit=${limit}&offset=${offset}`,
    { token }
  );
}

export function fetchStructure(token: string, universityId: string): Promise<Structure> {
  return request<Structure>(`/api/v1/directory/universities/${universityId}/structure`, { token });
}

export function adminCreateDepartment(
  token: string,
  universityId: string,
  input: { name: string; code: string }
): Promise<{ id: string; name: string; code: string }> {
  return request(`/api/v1/admin/structure/universities/${universityId}/departments`, {
    token,
    body: input,
  });
}

export function adminCreateProgram(
  token: string,
  departmentId: string,
  input: { name: string; code: string; degree_level?: string }
): Promise<{ id: string; name: string; code: string }> {
  return request(`/api/v1/admin/structure/departments/${departmentId}/programs`, {
    token,
    body: input,
  });
}

export function adminCreateBatch(
  token: string,
  programId: string,
  input: { name: string; start_year?: number }
): Promise<{ id: string; name: string }> {
  return request(`/api/v1/admin/structure/programs/${programId}/batches`, { token, body: input });
}

export function adminCreateClass(
  token: string,
  batchId: string,
  input: { name: string; code: string }
): Promise<{ id: string; name: string; code: string }> {
  return request(`/api/v1/admin/structure/batches/${batchId}/classes`, { token, body: input });
}

export function adminRename(
  token: string,
  kind: "department" | "program" | "batch" | "class",
  itemId: string,
  input: { name?: string; code?: string }
): Promise<{ id: string; name: string }> {
  return request(`/api/v1/admin/structure/${kind}/${itemId}`, { token, method: "PATCH", body: input });
}

// ---- Forum types & API ----

export type ForumStatus = "PENDING" | "APPROVED" | "REJECTED";

export type Forum = {
  id: string;
  class_id: string;
  name: string;
  description: string | null;
  status: ForumStatus;
  created_by: string | null;
  approved_by: string | null;
  created_at: string;
  updated_at: string;
  member_count: number;
  is_member: boolean;
};

export function listClassForums(token: string, classId: string, includePending = false): Promise<Forum[]> {
  const qs = includePending ? "?include_pending=true" : "";
  return request<Forum[]>(`/api/v1/classes/${classId}/forums${qs}`, { token });
}

export function listForumProposals(token: string, classId: string): Promise<Forum[]> {
  return request<Forum[]>(`/api/v1/classes/${classId}/forums/proposals`, { token });
}

export function proposeForum(token: string, classId: string, input: { name: string; description?: string | null }): Promise<Forum> {
  return request<Forum>(`/api/v1/classes/${classId}/forums`, { token, body: input });
}

export function fetchForum(token: string, forumId: string): Promise<Forum> {
  return request<Forum>(`/api/v1/forums/${forumId}`, { token });
}

export function reviewForum(token: string, forumId: string, status: ForumStatus): Promise<Forum> {
  return request<Forum>(`/api/v1/forums/${forumId}/review`, { token, method: "PATCH", body: { status } });
}

export function joinForum(token: string, forumId: string): Promise<Forum> {
  return request<Forum>(`/api/v1/forums/${forumId}/join`, { token, method: "POST", body: {} });
}

export function leaveForum(token: string, forumId: string): Promise<void> {
  return request<void>(`/api/v1/forums/${forumId}/members/me`, { token, method: "DELETE" });
}

export function listJoinedForums(token: string): Promise<Forum[]> {
  return request<Forum[]>(`/api/v1/forums/joined`, { token });
}

// ---- Discussion types & API ----

export type Post = {
  id: string;
  forum_id: string;
  author_id: string | null;
  author_display_name: string | null;
  content: string;
  created_at: string;
  updated_at: string;
  like_count: number;
  comment_count: number;
  liked_by_me: boolean;
  is_own: boolean;
};

export type PostList = { items: Post[]; total: number; limit: number; offset: number };

export type Comment = {
  id: string;
  post_id: string;
  author_id: string | null;
  author_display_name: string | null;
  content: string;
  created_at: string;
  updated_at: string;
  is_own: boolean;
};

export type CommentList = { items: Comment[]; total: number; limit: number; offset: number };

export type Notification = {
  id: string;
  user_id: string;
  actor_id: string | null;
  type: string;
  post_id: string | null;
  forum_id: string | null;
  comment_id: string | null;
  message: string;
  is_read: boolean;
  created_at: string;
};

export function createPost(token: string, forumId: string, content: string): Promise<Post> {
  return request<Post>(`/api/v1/forums/${forumId}/posts`, { token, method: "POST", body: { content } });
}

export function listPosts(token: string, forumId: string, limit = 20, offset = 0): Promise<PostList> {
  return request<PostList>(`/api/v1/forums/${forumId}/posts?limit=${limit}&offset=${offset}`, { token });
}

export function fetchPost(token: string, forumId: string, postId: string): Promise<Post> {
  return request<Post>(`/api/v1/forums/${forumId}/posts/${postId}`, { token });
}

export function deletePost(token: string, forumId: string, postId: string): Promise<void> {
  return request<void>(`/api/v1/forums/${forumId}/posts/${postId}`, { token, method: "DELETE" });
}

export function createComment(token: string, forumId: string, postId: string, content: string): Promise<Comment> {
  return request<Comment>(`/api/v1/forums/${forumId}/posts/${postId}/comments`, { token, method: "POST", body: { content } });
}

export function listComments(token: string, forumId: string, postId: string, limit = 50, offset = 0): Promise<CommentList> {
  return request<CommentList>(`/api/v1/forums/${forumId}/posts/${postId}/comments?limit=${limit}&offset=${offset}`, { token });
}

export function deleteComment(token: string, forumId: string, postId: string, commentId: string): Promise<void> {
  return request<void>(`/api/v1/forums/${forumId}/posts/${postId}/comments/${commentId}`, { token, method: "DELETE" });
}

export function likePost(token: string, forumId: string, postId: string): Promise<{ like_count: number; liked: boolean }> {
  return request<{ like_count: number; liked: boolean }>(`/api/v1/forums/${forumId}/posts/${postId}/like`, { token, method: "POST", body: {} });
}

export function unlikePost(token: string, forumId: string, postId: string): Promise<{ like_count: number; liked: boolean }> {
  return request<{ like_count: number; liked: boolean }>(`/api/v1/forums/${forumId}/posts/${postId}/like`, { token, method: "DELETE" });
}

export function listNotifications(token: string, limit = 20, offset = 0): Promise<Notification[]> {
  return request<Notification[]>(`/api/v1/notifications?limit=${limit}&offset=${offset}`, { token });
}

export function markNotificationRead(token: string, notificationId: string): Promise<Notification> {
  return request<Notification>(`/api/v1/notifications/${notificationId}/read`, { token, method: "PATCH", body: {} });
}

// ---- Connections types & API ----

export type ConnectionStatusState = "NONE" | "PENDING_OUTGOING" | "PENDING_INCOMING" | "CONNECTED" | "REJECTED" | "SELF";
export type ConnectionRowStatus = "PENDING" | "ACCEPTED" | "REJECTED";

export type ConnectionRow = {
  id: string;
  requester_id: string;
  recipient_id: string;
  status: ConnectionRowStatus;
  created_at: string;
  updated_at: string;
};

export type ConnectionUser = {
  user_id: string;
  display_name: string | null;
  headline: string | null;
  avatar_url: string | null;
  role: string | null;
  verification_status: string | null;
  connection_id: string | null;
  status: ConnectionRowStatus | null;
  created_at: string | null;
  updated_at: string | null;
};

export type ConnectionStatusResp = {
  status: ConnectionStatusState;
  connection: ConnectionRow | null;
};

export type MutualsResp = {
  count: number;
  users: ConnectionUser[];
};

export function listMyConnections(token: string): Promise<ConnectionUser[]> {
  return request<ConnectionUser[]>(`/api/v1/connections`, { token });
}
export function listIncomingRequests(token: string): Promise<ConnectionUser[]> {
  return request<ConnectionUser[]>(`/api/v1/connections/requests/incoming`, { token });
}
export function listOutgoingRequests(token: string): Promise<ConnectionUser[]> {
  return request<ConnectionUser[]>(`/api/v1/connections/requests/outgoing`, { token });
}
export function fetchConnectionStatus(token: string, userId: string): Promise<ConnectionStatusResp> {
  return request<ConnectionStatusResp>(`/api/v1/connections/${userId}/status`, { token });
}
export function fetchMutuals(token: string, userId: string): Promise<MutualsResp> {
  return request<MutualsResp>(`/api/v1/connections/${userId}/mutuals`, { token });
}
export function sendConnectionRequest(token: string, userId: string): Promise<ConnectionRow> {
  return request<ConnectionRow>(`/api/v1/connections/${userId}/request`, { token, method: "POST", body: {} });
}
export function acceptConnection(token: string, userId: string): Promise<ConnectionRow> {
  return request<ConnectionRow>(`/api/v1/connections/${userId}/accept`, { token, method: "POST", body: {} });
}
export function rejectConnection(token: string, userId: string): Promise<ConnectionRow> {
  return request<ConnectionRow>(`/api/v1/connections/${userId}/reject`, { token, method: "POST", body: {} });
}
export function cancelConnectionRequest(token: string, userId: string): Promise<void> {
  return request<void>(`/api/v1/connections/${userId}/request`, { token, method: "DELETE" });
}
export function removeConnection(token: string, userId: string): Promise<void> {
  return request<void>(`/api/v1/connections/${userId}`, { token, method: "DELETE" });
}

// ---- Graph types & API ----

export type GraphNodeType =
  | "STUDENT"
  | "UNIVERSITY"
  | "DEPARTMENT"
  | "PROGRAM"
  | "BATCH"
  | "CLASS"
  | "FORUM"
  | "SKILL"
  | "INTEREST";

export type GraphEdgeType =
  | "BELONGS_TO"
  | "ENROLLED_IN"
  | "IN_PROGRAM"
  | "IN_BATCH"
  | "IN_CLASS"
  | "MEMBER_OF"
  | "PARTICIPATES_IN"
  | "HAS_SKILL"
  | "HAS_INTEREST"
  | "CONNECTED_TO";

export type GraphNode = {
  id: string;
  type: GraphNodeType;
  label: string;
  metadata: Record<string, unknown>;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  type: GraphEdgeType;
  metadata: Record<string, unknown>;
};

export type GraphResponse = {
  root_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export function fetchGraph(token: string): Promise<GraphResponse> {
  return request<GraphResponse>(`/api/v1/graph/me`, { token });
}
