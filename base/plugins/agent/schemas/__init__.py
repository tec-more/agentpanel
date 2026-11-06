"""
Agent plugin schemas
"""
from base.plugins.agent.schemas.agent import AgentCreate, AgentUpdate, AgentResponse
from base.plugins.agent.schemas.skill import SkillCreate, SkillUpdate, SkillResponse
from base.plugins.agent.schemas.memory import MemoryCreate, MemoryUpdate, MemoryResponse
from base.plugins.agent.schemas.workflow import (
    WorkflowCreate, WorkflowUpdate, WorkflowResponse,
    WorkflowNodeCreate, WorkflowNodeUpdate, WorkflowNodeResponse,
    WorkflowEdgeCreate, WorkflowEdgeUpdate, WorkflowEdgeResponse,
    WorkflowExecutionCreate, WorkflowExecutionResponse
)
from base.plugins.agent.schemas.rag import (
    RAGKnowledgeBaseCreate, RAGKnowledgeBaseUpdate, RAGKnowledgeBaseResponse,
    RAGDocumentCreate, RAGDocumentUpdate, RAGDocumentResponse,
    RAGDocumentChunkCreate, RAGDocumentChunkResponse,
    RAGSearchRequest, RAGSearchResponse
)

__all__ = [
    "AgentCreate", "AgentUpdate", "AgentResponse",
    "SkillCreate", "SkillUpdate", "SkillResponse",
    "MemoryCreate", "MemoryUpdate", "MemoryResponse",
    "WorkflowCreate", "WorkflowUpdate", "WorkflowResponse",
    "WorkflowNodeCreate", "WorkflowNodeUpdate", "WorkflowNodeResponse",
    "WorkflowEdgeCreate", "WorkflowEdgeUpdate", "WorkflowEdgeResponse",
    "WorkflowExecutionCreate", "WorkflowExecutionResponse",
    "RAGKnowledgeBaseCreate", "RAGKnowledgeBaseUpdate", "RAGKnowledgeBaseResponse",
    "RAGDocumentCreate", "RAGDocumentUpdate", "RAGDocumentResponse",
    "RAGDocumentChunkCreate", "RAGDocumentChunkResponse",
    "RAGSearchRequest", "RAGSearchResponse"
]