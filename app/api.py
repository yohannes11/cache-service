"""HTTP endpoints. Thin on purpose: validate, delegate to services, shape the response."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session

from app import services
from app.db import get_session
from app.schemas import PayloadCreated, PayloadOut, PayloadRequest
from app.transformer import Transformer, get_transformer

router = APIRouter(prefix="/payload", tags=["payload"])

SessionDep = Annotated[Session, Depends(get_session)]
TransformerDep = Annotated[Transformer, Depends(get_transformer)]


@router.post(
    "",
    response_model=PayloadCreated,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"model": PayloadCreated, "description": "Identical payload already existed"}},
)
def create_payload(
    body: PayloadRequest, response: Response, session: SessionDep, transformer: TransformerDep
) -> PayloadCreated:
    payload, created = services.create_payload(session, body, transformer)
    if not created:
        # 200 instead of 201: nothing new was created, the old id is reused.
        response.status_code = status.HTTP_200_OK
    message = "Payload created" if created else "Payload already existed; identifier reused"
    return PayloadCreated(id=payload.id, created=created, message=message)


@router.get("/{payload_id}", response_model=PayloadOut)
def read_payload(payload_id: int, session: SessionDep) -> PayloadOut:
    payload = services.get_payload(session, payload_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payload not found")
    return PayloadOut(output=payload.output)
"""HTTP endpoints. Thin on purpose: validate, delegate to services, shape the response."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session

from app import services
from app.db import get_session
from app.schemas import PayloadCreated, PayloadOut, PayloadRequest
from app.transformer import Transformer, get_transformer

router = APIRouter(prefix="/payload", tags=["payload"])

SessionDep = Annotated[Session, Depends(get_session)]
TransformerDep = Annotated[Transformer, Depends(get_transformer)]


@router.post(
    "",
    response_model=PayloadCreated,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"model": PayloadCreated, "description": "Identical payload already existed"}},
)
def create_payload(
    body: PayloadRequest, response: Response, session: SessionDep, transformer: TransformerDep
) -> PayloadCreated:
    payload, created = services.create_payload(session, body, transformer)
    if not created:
        # 200 instead of 201: nothing new was created, the old id is reused.
        response.status_code = status.HTTP_200_OK
    message = "Payload created" if created else "Payload already existed; identifier reused"
    return PayloadCreated(id=payload.id, created=created, message=message)


@router.get("/{payload_id}", response_model=PayloadOut)
def read_payload(payload_id: int, session: SessionDep) -> PayloadOut:
    payload = services.get_payload(session, payload_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payload not found")
    return PayloadOut(output=payload.output)
