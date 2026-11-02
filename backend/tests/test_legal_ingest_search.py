"""Testes da ingestão e da busca de fontes jurídicas. Apenas dados sintéticos.

O serviço br-eli é substituído por um cliente falso; nenhuma chamada de rede é feita.
As leis abaixo são inventadas ("Lei Sintética"). O armazenamento de evidências usa a
migração real sobre SQLite.
"""
import tempfile
import unittest
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from evidence import database
from evidence.database import make_engine, make_session_factory, transaction
from evidence.models import SourceVersion
from evidence.repository import open_repository, provision_tenant
from legal_sources.br_eli_client import BrEliError
from legal_sources.ingest import IngestError, ingerir_dispositivos
from legal_sources.router import build_legal_router
from security.oidc import Principal

IDP = "https://idp.example.test"
ADMIN = Principal(IDP, "admin-a")
OUTRO = Principal(IDP, "firma-b")
URN = "urn:lex:br:federal:lei:2001-01-01;1"
TEXTOS = {
    "art1": "Art. 1 A cláusula penal de atraso é fixada em percentual sobre a obrigação.",
    "art2": "Art. 2 O valor da cominação não pode exceder o da obrigação principal.",
    "art3": "Art. 3 A penalidade manifestamente excessiva poderá ser reduzida pelo juiz.",
}


class ClienteFalso:
    def __init__(self, falhar=()):
        self.chamadas = []
        self.falhar = set(falhar)

    def call_tool(self, nome, args):
        self.chamadas.append((nome, args))
        if nome == "br_get_norma":
            return {"norma_nome": "Lei Sintética 1/2001"}
        if nome == "br_get_norma_index":
            return {"urn": URN, "total": 4, "items": [
                {"suffix": "titulo1", "tipo": "titulo", "name": "Título I"},
                *[{"suffix": s, "tipo": "artigo", "name": f"Art. {s[3:]}"} for s in TEXTOS]]}
        if nome == "br_get_norma_texto":
            if args["dispositivo"] in self.falhar:
                raise BrEliError("falha simulada")
            s = args["dispositivo"]
            return {"dispositivo": s, "text": TEXTOS[s], "lex_uri": f"{URN}!{s}",
                    "human_readable_citation": f"Art. {s[3:]}",
                    "source_url": f"https://normas.leg.br/?urn={URN}!{s}"}
        raise AssertionError(nome)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.url = f"sqlite:///{self.tmp.name}/e.db"
        database.upgrade(self.url)
        self.engine = make_engine(self.url)
        self.factory = make_session_factory(self.engine)
        with transaction(self.factory) as s:
            self.tenant_a = provision_tenant(s, ADMIN, "A")
            self.tenant_b = provision_tenant(s, OUTRO, "B")

    def tearDown(self):
        self.engine.dispose()
        self.tmp.cleanup()


class IngestTests(Base):
    def _ingerir(self, cliente, **kw):
        with transaction(self.factory) as s:
            repo = open_repository(s, ADMIN)
            return ingerir_dispositivos(repo, cliente, URN, **kw)

    def test_grava_artigos_e_ignora_o_que_nao_e_artigo(self):
        r = self._ingerir(ClienteFalso())
        self.assertEqual((r.gravados, r.ja_existentes, r.falhas), (3, 0, []))

    def test_e_idempotente(self):
        self._ingerir(ClienteFalso())
        r = self._ingerir(ClienteFalso())
        self.assertEqual((r.gravados, r.ja_existentes), (0, 3))
        with transaction(self.factory) as s:
            from sqlalchemy import func, select
            self.assertEqual(s.execute(select(func.count()).select_from(SourceVersion)).scalar_one(), 3)

    def test_vigencia_fica_em_branco(self):
        self._ingerir(ClienteFalso())
        with transaction(self.factory) as s:
            from sqlalchemy import select
            for v in s.execute(select(SourceVersion)).scalars():
                self.assertEqual((v.effective_from, v.effective_to), ("", ""))
                self.assertIn("vigencia nao verificada", v.version_label)

    def test_dispositivo_fora_do_indice_e_recusado_sem_buscar_texto(self):
        c = ClienteFalso()
        with self.assertRaises(IngestError):
            self._ingerir(c, dispositivos=["art999"])
        self.assertFalse([x for x in c.chamadas if x[0] == "br_get_norma_texto"])

    def test_falha_de_um_artigo_nao_interrompe_os_demais(self):
        r = self._ingerir(ClienteFalso(falhar={"art2"}))
        self.assertEqual((r.gravados, r.falhas), (2, ["art2"]))

    def test_respeita_o_limite(self):
        r = self._ingerir(ClienteFalso(), limite=2)
        self.assertEqual(r.gravados, 2)

    def test_urn_invalida(self):
        with transaction(self.factory) as s:
            repo = open_repository(s, ADMIN)
            for ruim in ("lei:1", "urn:lex:br:" + "x" * 300, "urn:lex:br:a b"):
                with self.assertRaises(IngestError):
                    ingerir_dispositivos(repo, ClienteFalso(), ruim)


class RotasTests(Base):
    def _app(self, principal):
        cfg = SimpleNamespace(EVIDENCE_DATABASE_URL=self.url, BR_ELI_SERVICE_URL="",
                              BR_ELI_SERVICE_TOKEN="")
        app = FastAPI()
        app.include_router(build_legal_router(lambda: principal, cfg))
        return TestClient(app)

    def test_busca_devolve_evidencia_nao_verificada(self):
        with transaction(self.factory) as s:
            ingerir_dispositivos(open_repository(s, ADMIN), ClienteFalso(), URN)
        r = self._app(ADMIN).get("/api/legal/search", params={"q": "cláusula penal excessiva"})
        self.assertEqual(r.status_code, 200)
        hits = r.json()["resultados"]
        self.assertTrue(hits)
        self.assertFalse(hits[0]["authority_verified"])
        self.assertEqual(hits[0]["role"], "evidencia_nao_instrucao")
        self.assertEqual(hits[0]["vigencia_status"], "vigencia_nao_informada")

    def test_busca_nao_atravessa_locatarios(self):
        with transaction(self.factory) as s:
            ingerir_dispositivos(open_repository(s, ADMIN), ClienteFalso(), URN)
        r = self._app(OUTRO).get("/api/legal/search", params={"q": "cláusula penal"})
        self.assertEqual(r.json()["total"], 0)

    def test_busca_valida_parametros(self):
        c = self._app(ADMIN)
        self.assertEqual(c.get("/api/legal/search", params={"q": ""}).status_code, 422)
        self.assertEqual(c.get("/api/legal/search", params={"q": "x", "as_of": "ontem"}).status_code, 422)
        self.assertEqual(c.get("/api/legal/search", params={"q": "x", "top_k": 99}).status_code, 422)

    def test_ingestao_sem_servico_configurado_responde_503(self):
        r = self._app(ADMIN).post("/api/legal/ingest", json={"urn": URN})
        self.assertEqual(r.status_code, 503)

    def test_ingestao_exige_papel_admin(self):
        membro = Principal(IDP, "membro-a")
        with transaction(self.factory) as sess:
            open_repository(sess, ADMIN).grant_membership(IDP, "membro-a", "member")
        cfg = SimpleNamespace(EVIDENCE_DATABASE_URL=self.url,
                              BR_ELI_SERVICE_URL="https://brel.example.test",
                              BR_ELI_SERVICE_TOKEN="t" * 40)
        app = FastAPI()
        app.include_router(build_legal_router(lambda: membro, cfg))
        r = TestClient(app).post("/api/legal/ingest", json={"urn": URN})
        self.assertEqual(r.status_code, 403)
        with transaction(self.factory) as sess:
            from sqlalchemy import func, select
            self.assertEqual(sess.execute(select(func.count()).select_from(SourceVersion)).scalar_one(), 0)

    def test_sem_banco_configurado_responde_503(self):
        cfg = SimpleNamespace(EVIDENCE_DATABASE_URL="", BR_ELI_SERVICE_URL="", BR_ELI_SERVICE_TOKEN="")
        app = FastAPI()
        app.include_router(build_legal_router(lambda: ADMIN, cfg))
        self.assertEqual(TestClient(app).get("/api/legal/search", params={"q": "x"}).status_code, 503)


if __name__ == "__main__":
    unittest.main()
