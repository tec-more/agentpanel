"""
Workflow schemas
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class WorkflowNodeBase(BaseModel):
    """Workflow node base schema"""
    name: str = Field(..., description="Node name")
    type: str = Field(..., description="Node type: agent/skill/decision/fork/join")
    config: Dict[str, Any] = Field(..., description="Node configuration")
    position: Dict[str, float] = Field(..., description="Node position in UI")
    agent_id: Optional[int] = Field(None, description="Associated agent ID")
    skill_id: Optional[int] = Field(None, description="Associated skill ID")


class WorkflowNodeCreate(WorkflowNodeBase):
    """Workflow node create schema"""
    pass


class WorkflowNodeUpdate(WorkflowNodeBase):
    """Workflow node update schema"""
    name: Optional[str] = None
    type: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    position: Optional[Dict[str, float]] = None


class WorkflowNodeResponse(WorkflowNodeBase):
    """Workflow node response schema"""
    id: int
    workflow_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkflowEdgeBase(BaseModel):
    """Workflow edge base schema"""
    source_node_id: int = Field(..., description="Source node ID")
    target_node_id: int = Field(..., description="Target node ID")
    condition: Optional[str] = Field(None, description="Edge condition")
    label: Optional[str] = Field(None, description="Edge label")


class WorkflowEdgeCreate(WorkflowEdgeBase):
    """Workflow edge create schema"""
    pass


class WorkflowEdgeUpdate(WorkflowEdgeBase):
    """Workflow edge update schema"""
    source_node_id: Optional[int] = None
    target_node_id: Optional[int] = None
    condition: Optional[str] = None
    label: Optional[str] = None


class WorkflowEdgeResponse(WorkflowEdgeBase):
    """Workflow edge response schema"""
    id: int
    workflow_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkflowBase(BaseModel):
    """Workflow base schema"""
    name: str = Field(..., description="Workflow name")
    description: Optional[str] = Field(None, description="Workflow description")
    status: str = Field("draft", description="Status: draft/active/inactive")
    definition: Dict[str, Any] = Field(..., description="Workflow definition")
    agent_ids: List[int] = Field(default_factory=list, description="Associated agent IDs")


class WorkflowCreate(WorkflowBase):
    """Workflow create schema"""
    pass


class WorkflowUpdate(WorkflowBase):
    """Workflow update schema"""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    definition: Optional[Dict[str, Any]] = None
    agent_ids: Optional[List[int]] = None


class WorkflowResponse(WorkflowBase):
    """Workflow response schema"""
    id: int
    created_at: datetime
    updated_at: datetime
    node_count: int = Field(0, description="Number of nodes")
    edge_count: int = Field(0, description="Number of edges")

    class Config:
        from_attributes = True


class WorkflowExecutionBase(BaseModel):
    """Workflow execution base schema"""
    workflow_id: int = Field(..., description="Workflow ID")
    input_data: Dict[str, Any] = Field(..., description="Input data")


class WorkflowExecutionCreate(WorkflowExecutionBase):
    """Workflow execution create schema"""
    pass


class WorkflowExecutionResponse(WorkflowExecutionBase):
    """Workflow execution response schema"""
    id: int
    status: str
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
