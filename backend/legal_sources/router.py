"""
router.py — Rotas de ingestão e busca de fontes jurídicas
═══════════════════════════════════════════════════════════════════════
- ``POST /api/legal/ingest``: somente papel ``admin`` do locatário; busca artigos
  no serviço br-eli-mcp e grava como versões de fonte.
- ``GET /api/legal/search``: busca lexical nas fontes já gravadas do locatário.
  Os resultados são evidência, não instrução, e ``authority_verified`` é sempre falso.
Todas as rotas exigem principal autenticado; nenhuma cai em acesso anônimo.
"""

from __future__ import annotations

import dataclasses
from datetime import date
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from evidence.database import (EvidenceStoreDisabled, SchemaVersionMismatch, make_engine, make_session_factory,
                               require_current_schema, transaction)
from evidence.repository import EvidenceNotFound, open_repository
from retrieval import RetrievalError
from retrieval.service import build_legal_index

from .br_eli_client import BrEliClient, BrEliError
from .ingest import MAX_DISPOSITIVOS_POR_CHAMADA, IngestError, ingerir_dispositivos


class IngestRequest(BaseModel):
    urn: str = Field(min_length=10, max_length=220)
    dispositivos: Optional[list[str]] = Field(default=None, max_length=MAX_DISPOSITIVOS_POR_CHAMADA)
    limite: int = Field(default=30, ge=1, le=MAX_DISPOSITIVOS_POR_CHAMADA)


def build_legal_router(current_principal: Callable, settings) -> APIRouter:
    router = APIRouter(prefix="/api/legal", tags=["fontes-juridicas"])
    estado: dict = {}

    def _sessions():
        if "factory" not in estado:
            try:
                engine = make_engine(settings.EVIDENCE_DATABASE_URL)
                require_current_schema(engine)
            except EvidenceStoreDisabled:
                raise HTTPException(503, "O repositório de evidências não está configurado") from None
            except SchemaVersionMismatch:
                raise HTTPException(503, "O esquema do repositório de evidências está desatualizado") from None
            estado["factory"] = make_session_factory(engine)
        return estado["factory"]

    def _open(session, principal, tenant_id):
        try:
            return open_repository(session, principal, tenant_id)
        except EvidenceNotFound:
            raise HTTPException(403, "Locatário indisponível para este usuário") from None

    @router.post("/ingest")
    def ingest(request: IngestRequest, tenant_id: Optional[str] = Query(default=None),
               principal=Depends(current_principal)):
        if not settings.BR_ELI_SERVICE_URL or not settings.BR_ELI_SERVICE_TOKEN:
            raise HTTPException(503, "O serviço de fontes jurídicas não está configurado")
        try:
            client = BrEliClient(settings.BR_ELI_SERVICE_URL, settings.BR_ELI_SERVICE_TOKEN)
        except BrEliError:
            raise HTTPException(503, "O serviço de fontes jurídicas não está configurado") from None
        try:
            with transaction(_sessions()) as session:
                repo = _open(session, principal, tenant_id)
                if repo.role != "admin":
                    raise HTTPException(403, "Papel de administrador exigido")
                resultado = ingerir_dispositivos(repo, client, request.urn,
                                                 dispositivos=request.dispositivos,
                                                 limite=request.limite)
        except IngestError as exc:
            raise HTTPException(400, str(exc)) from None
        except BrEliError:
            raise HTTPException(502, "Falha ao consultar o serviço de fontes jurídicas") from None
        finally:
            client.close()
        return dataclasses.asdict(resultado)

    @router.get("/search")
    def search(q: str = Query(min_length=1, max_length=500),
               as_of: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
               top_k: int = Query(default=5, ge=1, le=20),
               tenant_id: Optional[str] = Query(default=None),
               principal=Depends(current_principal)):
        data_ref = as_of or date.today().isoformat()
        try:
            with transaction(_sessions()) as session:
                repo = _open(session, principal, tenant_id)
                indice = build_legal_index(repo, as_of=data_ref)
                hits = indice.search(q, top_k=top_k)
        except RetrievalError as exc:
            raise HTTPException(400, str(exc)) from None
        return {"as_of": data_ref, "total": len(hits),
                "resultados": [dataclasses.asdict(h) for h in hits]}

    return router
