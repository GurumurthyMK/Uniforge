"""Graph Pydantic schemas for Phase 3B-A."""

import enum
import uuid

from pydantic import BaseModel, ConfigDict


class GraphNodeType(str, enum.Enum):
    STUDENT = "STUDENT"
    UNIVERSITY = "UNIVERSITY"
    DEPARTMENT = "DEPARTMENT"
    PROGRAM = "PROGRAM"
    BATCH = "BATCH"
    CLASS = "CLASS"
    FORUM = "FORUM"
    SKILL = "SKILL"
    INTEREST = "INTEREST"


class GraphEdgeType(str, enum.Enum):
    BELONGS_TO = "BELONGS_TO"
    ENROLLED_IN = "ENROLLED_IN"
    IN_PROGRAM = "IN_PROGRAM"
    IN_BATCH = "IN_BATCH"
    IN_CLASS = "IN_CLASS"
    MEMBER_OF = "MEMBER_OF"
    PARTICIPATES_IN = "PARTICIPATES_IN"
    HAS_SKILL = "HAS_SKILL"
    HAS_INTEREST = "HAS_INTEREST"
    CONNECTED_TO = "CONNECTED_TO"


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: GraphNodeType
    label: str
    metadata: dict = {}


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source: str
    target: str
    type: GraphEdgeType
    metadata: dict = {}


class GraphResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
