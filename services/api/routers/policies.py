from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

from services.api.dependencies import TenantContext, get_current_tenant_context
from database.postgres.connection import get_db_session
from database.postgres.models import Policy, PolicyVersion, PolicyClause, Control
from services.graph.client import get_graph_client
from services.graph.ontology import GraphNode, GraphRelationship

router = APIRouter(prefix="/policies", tags=["Bank Policies & Controls"])


class PolicyClauseCreate(BaseModel):
    clause_number: str
    title: Optional[str] = None
    text: str


class ControlCreate(BaseModel):
    control_code: str
    name: str
    description: str
    frequency: str = "CONTINUOUS"
    control_type: str = "PREVENTIVE"
    responsible_role: Optional[str] = None


class PolicyCreate(BaseModel):
    policy_code: str
    title: str
    category: str
    jurisdiction: str = "IN"
    owner_department: str = "Information Security"
    clauses: List[PolicyClauseCreate] = []
    controls: List[ControlCreate] = []


class PolicyClauseResponse(BaseModel):
    id: str
    clause_number: str
    title: Optional[str]
    text: str


class ControlResponse(BaseModel):
    id: str
    control_code: str
    name: str
    description: str
    frequency: str
    control_type: str


class PolicyResponse(BaseModel):
    id: str
    tenant_id: str
    policy_code: str
    title: str
    category: str
    jurisdiction: str
    current_version: str
    status: str
    owner_department: Optional[str]
    clauses: List[PolicyClauseResponse] = []
    controls: List[ControlResponse] = []


@router.get("", response_model=List[PolicyResponse])
async def list_policies(
    ctx: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    query = select(Policy).where(Policy.tenant_id == ctx.tenant_id)
    result = await db.execute(query)
    policies = result.scalars().all()

    response = []
    for pol in policies:
        # Load clauses
        cl_res = await db.execute(select(PolicyClause).where(PolicyClause.policy_id == pol.id))
        clauses = cl_res.scalars().all()

        # Load controls
        ctl_res = await db.execute(select(Control).where(Control.policy_id == pol.id))
        controls = ctl_res.scalars().all()

        response.append(
            PolicyResponse(
                id=pol.id,
                tenant_id=pol.tenant_id,
                policy_code=pol.policy_code,
                title=pol.title,
                category=pol.category,
                jurisdiction=pol.jurisdiction,
                current_version=pol.current_version,
                status=pol.status,
                owner_department=pol.owner_department,
                clauses=[
                    PolicyClauseResponse(
                        id=c.id, clause_number=c.clause_number, title=c.title, text=c.text
                    )
                    for c in clauses
                ],
                controls=[
                    ControlResponse(
                        id=c.id,
                        control_code=c.control_code,
                        name=c.name,
                        description=c.description,
                        frequency=c.frequency,
                        control_type=c.control_type,
                    )
                    for c in controls
                ],
            )
        )
    return response


@router.post("", response_model=PolicyResponse)
async def create_policy(
    payload: PolicyCreate,
    ctx: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    # Check if policy already exists
    existing_query = select(Policy).where(
        Policy.tenant_id == ctx.tenant_id,
        Policy.policy_code == payload.policy_code,
    )
    existing_res = await db.execute(existing_query)
    policy = existing_res.scalar_one_or_none()

    if not policy:
        # Create Policy
        policy = Policy(
            tenant_id=ctx.tenant_id,
            policy_code=payload.policy_code,
            title=payload.title,
            category=payload.category,
            jurisdiction=payload.jurisdiction,
            current_version="1.0.0",
            status="APPROVED",
            owner_department=payload.owner_department,
        )
        db.add(policy)
        await db.flush()
    else:
        policy.title = payload.title
        policy.category = payload.category
        policy.owner_department = payload.owner_department

    # Initial Version
    policy_version = PolicyVersion(
        policy_id=policy.id,
        tenant_id=ctx.tenant_id,
        version_number="1.0.0",
        status="APPROVED",
        content_full="\n\n".join([f"{c.clause_number}: {c.text}" for c in payload.clauses]),
        changelog="Initial baseline policy version.",
        approved_by=ctx.user_id,
        approved_at=datetime.utcnow(),
    )
    db.add(policy_version)

    # Clauses
    clause_objs = []
    for c in payload.clauses:
        clause = PolicyClause(
            policy_id=policy.id,
            tenant_id=ctx.tenant_id,
            clause_number=c.clause_number,
            title=c.title,
            text=c.text,
        )
        db.add(clause)
        clause_objs.append(clause)

    # Controls
    control_objs = []
    for ctl in payload.controls:
        control = Control(
            policy_id=policy.id,
            tenant_id=ctx.tenant_id,
            control_code=ctl.control_code,
            name=ctl.name,
            description=ctl.description,
            frequency=ctl.frequency,
            control_type=ctl.control_type,
            responsible_role=ctl.responsible_role,
        )
        db.add(control)
        control_objs.append(control)

    await db.flush()

    # Sync to Neo4j Knowledge Graph with tenant_id isolation
    graph_client = get_graph_client()
    pol_node = GraphNode(
        id=policy.id,
        label="Policy",
        properties={
            "tenant_id": ctx.tenant_id,
            "policy_code": policy.policy_code,
            "title": policy.title,
            "category": policy.category,
            "jurisdiction": policy.jurisdiction,
            "owner_department": policy.owner_department,
        },
    )
    graph_client.sync_node(pol_node)

    for cl in clause_objs:
        cl_node = GraphNode(
            id=cl.id,
            label="PolicyClause",
            properties={
                "tenant_id": ctx.tenant_id,
                "clause_number": cl.clause_number,
                "text": cl.text,
            },
        )
        graph_client.sync_node(cl_node)
        graph_client.sync_relationship(
            GraphRelationship(
                source_id=policy.id,
                target_id=cl.id,
                rel_type="CONTAINS",
                properties={"tenant_id": ctx.tenant_id},
            )
        )

    for ctl in control_objs:
        ctl_node = GraphNode(
            id=ctl.id,
            label="Control",
            properties={
                "tenant_id": ctx.tenant_id,
                "control_code": ctl.control_code,
                "name": ctl.name,
            },
        )
        graph_client.sync_node(ctl_node)
        graph_client.sync_relationship(
            GraphRelationship(
                source_id=policy.id,
                target_id=ctl.id,
                rel_type="IMPLEMENTED_BY",
                properties={"tenant_id": ctx.tenant_id},
            )
        )

    await db.commit()

    return PolicyResponse(
        id=policy.id,
        tenant_id=policy.tenant_id,
        policy_code=policy.policy_code,
        title=policy.title,
        category=policy.category,
        jurisdiction=policy.jurisdiction,
        current_version=policy.current_version,
        status=policy.status,
        owner_department=policy.owner_department,
        clauses=[
            PolicyClauseResponse(
                id=c.id, clause_number=c.clause_number, title=c.title, text=c.text
            )
            for c in clause_objs
        ],
        controls=[
            ControlResponse(
                id=c.id,
                control_code=c.control_code,
                name=c.name,
                description=c.description,
                frequency=c.frequency,
                control_type=c.control_type,
            )
            for c in control_objs
        ],
    )
