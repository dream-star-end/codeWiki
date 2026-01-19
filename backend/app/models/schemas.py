from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Literal, Dict


# ==================== Auth Schemas ====================

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    username: str = Field(..., description="Username or email")
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class PasswordReset(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)


class AdminUserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


class LLMConfigUpdate(BaseModel):
    base_url: str
    api_key: str
    model_name: str
    timeout_s: int = 60
    max_tokens: int = 4096


class EmbeddingConfigUpdate(BaseModel):
    base_url: str
    api_key: str
    model_name: str


# ==================== Model Config ====================

class ModelConfig(BaseModel):
    base_url: str = Field(..., description="OpenAI-compatible base URL")
    api_key: str = Field(..., description="API key")
    model_name: str = Field(..., description="Model identifier")
    timeout_s: int = Field(60, description="Request timeout in seconds")
    max_tokens: int = Field(1024, description="Max output tokens")


class IngestRequest(BaseModel):
    url: Optional[str] = None
    local_path: Optional[str] = None
    branch: Optional[str] = None
    commit: Optional[str] = None
    include: Optional[List[str]] = None
    exclude: Optional[List[str]] = None
    model: Optional[ModelConfig] = None


class IngestResponse(BaseModel):
    repo_id: str
    job_id: str


class JobStatus(BaseModel):
    status: Literal["queued", "running", "success", "failed", "canceled"]
    progress: int = Field(0, ge=0, le=100)
    error: Optional[str] = None
    stage: Optional[str] = None  # Current processing stage description
    detail: Optional[str] = None  # Additional detail about current operation


class RepoSummary(BaseModel):
    repo_id: str
    languages: List[str]
    module_tree: Dict
    entry_points: List[Dict]


class ModuleDetails(BaseModel):
    module_id: str
    name: str
    path_prefix: str
    files: List[str]
    symbols: List[str]
    dependencies_in: List[str]
    dependencies_out: List[str]


class DependencyGraph(BaseModel):
    nodes: List[Dict] = []
    edges: List[Dict] = []
    file_deps: List[Dict] = []
    symbol_deps: List[Dict] = []
    module_deps: List[Dict] = []


class DocArtifact(BaseModel):
    module_id: str
    doc_type: str
    content: str
    meta: Optional[Dict] = None


class SearchRequest(BaseModel):
    query: str
    module_scope: Optional[List[str]] = None
    top_k: int = Field(8, ge=1, le=50)


class Citation(BaseModel):
    file_path: str
    symbol: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None


class SearchResult(BaseModel):
    chunk_id: str
    text: str
    score: float
    citations: List[Citation]


class SearchResponse(BaseModel):
    results: List[SearchResult]


class AnswerRequest(BaseModel):
    query: str
    module_scope: Optional[List[str]] = None
    max_evidence: int = Field(6, ge=1, le=20)
    model: ModelConfig


class AnswerResponse(BaseModel):
    answer: str
    citations: List[Citation]


class AIDocRequest(BaseModel):
    model: ModelConfig
    max_modules: int = Field(10, ge=1, le=50)


TrustedDocType = Literal["ai_repo", "ai_module"]


class AIDocResponse(BaseModel):
    doc_type: TrustedDocType
    module_id: Optional[str] = None
    content: str


class AIModuleDocsResponse(BaseModel):
    doc_type: TrustedDocType
    modules: List[Dict]


# ============== 代码浏览器模型 ==============

class FileNode(BaseModel):
    name: str
    path: str
    is_dir: bool
    children: List["FileNode"] = []
    language: Optional[str] = None
    size: Optional[int] = None


class FileTreeResponse(BaseModel):
    repo_id: str
    tree: FileNode


class SymbolInfo(BaseModel):
    id: str
    name: str
    kind: str
    file_path: str
    line_start: int
    line_end: int
    signature: Optional[str] = None
    container: Optional[str] = None


class FileContentResponse(BaseModel):
    path: str
    content: str
    language: str
    lines: int
    size: int
    symbols: List[SymbolInfo]


# ============== 符号导航模型 ==============

class SymbolSearchRequest(BaseModel):
    query: str
    kind: Optional[str] = None
    limit: int = Field(50, ge=1, le=200)


class SymbolSearchResponse(BaseModel):
    results: List[SymbolInfo]


class SymbolReference(BaseModel):
    file_path: str
    line: int
    context: str
    edge_type: str


class SymbolDetailResponse(BaseModel):
    symbol_id: str
    name: str
    kind: str
    file_path: str
    line_start: int
    line_end: int
    signature: Optional[str] = None
    references: List[SymbolReference]
    callers: List[SymbolInfo]
    callees: List[SymbolInfo]


# ============== Codebase 导出模型 ==============

ExportFormat = Literal["cursor", "markdown", "json", "xml"]
ExportScope = Literal["full", "module", "files"]


class CodebaseExportRequest(BaseModel):
    format: ExportFormat = "cursor"
    scope: ExportScope = "full"
    module_ids: Optional[List[str]] = None
    file_paths: Optional[List[str]] = None
    include_deps: bool = True
    max_tokens: int = Field(100000, ge=1000, le=500000)
    include_summary: bool = True


class CodebaseExportResponse(BaseModel):
    content: str
    token_count: int
    files_included: List[str]
    format: str


class SmartContextRequest(BaseModel):
    query: str
    max_tokens: int = Field(8000, ge=1000, le=50000)


class SmartContextResponse(BaseModel):
    content: str
    token_count: int
    files_included: List[str]


class CodebaseStatsResponse(BaseModel):
    total_files: int
    total_size: int
    total_symbols: int
    total_modules: int
    languages: Dict[str, int]
    estimated_tokens: int


# Pydantic v2 需要重建模型以解决前向引用
FileNode.model_rebuild()
