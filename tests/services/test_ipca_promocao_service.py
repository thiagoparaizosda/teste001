"""
Testes unitários para app/services/ipca_promocao_service.py — foco em
`promover_correcao` e na exclusão do registro de `cco_edit_sessions` após
a promoção aprovada (BUG-19506).

Cenários cobertos:
1. Promoção com sucesso e presença de `session_id` → `delete_one` é chamado
   com o `session_id` correto.
2. Promoção com sucesso e ausência de `session_id` → `delete_one` **não** é
   chamado e a promoção conclui sem erro.
3. Promoção falha (validação bloqueada) → `delete_one` **não** é chamado.
4. Promoção falha (erro na atualização da CCO) → `delete_one` **não** é
   chamado.
"""

from datetime import datetime

import pytest

from app.services.ipca_promocao_service import IPCAPromocaoService


class _FakeCol:
    """Fake de coleção pymongo que guarda chamadas para inspeção."""

    def __init__(self, doc=None):
        self._doc = doc
        self.delete_one_calls = []

    def find_one(self, filtro):
        return self._doc

    def update_one(self, filtro, update):
        return None

    def delete_one(self, filtro):
        self.delete_one_calls.append(filtro)
        return None


class _FakeDb:
    """Fake do db base (DEV) com as coleções usadas por promover_correcao."""

    def __init__(self, cco_corrigida=None):
        self.conta_custo_oleo_corrigida_entity = _FakeCol(cco_corrigida)
        self.cco_edit_sessions = _FakeCol()


class _FakeDbPrd:
    """Fake do db de produção (PRD)."""

    def __init__(self, cco_original=None):
        self.conta_custo_oleo_entity = _FakeCol(cco_original)


def cco_corrigida(**overrides):
    doc = {
        "_id": "CCO01_1",
        "session_id": "sessao-123",
        "version": 0,
        "status_promocao": "PENDENTE",
    }
    doc.update(overrides)
    return doc


# ─── Cenário 1: promoção com sucesso + session_id presente ────────────────

def test_promover_correcao_exclui_sessao_apos_sucesso(monkeypatch):
    cco = cco_corrigida()
    db = _FakeDb(cco)
    db_prd = _FakeDbPrd({"version": 0})

    service = IPCAPromocaoService(db, db_prd)

    monkeypatch.setattr(
        service, "_validar_promocao",
        lambda *a, **k: {"pode_promover": True, "motivos_bloqueio": [], "avisos": []},
    )
    monkeypatch.setattr(
        service, "_atualizar_cco_e_criar_evento",
        lambda *a, **k: {"success": True, "nova_versao": 2},
    )

    resultado = service.promover_correcao("CCO01_1", "usuario")

    assert resultado["success"] is True
    assert db.cco_edit_sessions.delete_one_calls == [
        {"session_id": "sessao-123"}
    ]


# ─── Cenário 2: promoção com sucesso + session_id ausente ─────────────────

def test_promover_correcao_sem_session_id_nao_exclui(monkeypatch):
    cco = cco_corrigida()
    cco.pop("session_id", None)
    db = _FakeDb(cco)
    db_prd = _FakeDbPrd({"version": 0})

    service = IPCAPromocaoService(db, db_prd)

    monkeypatch.setattr(
        service, "_validar_promocao",
        lambda *a, **k: {"pode_promover": True, "motivos_bloqueio": [], "avisos": []},
    )
    monkeypatch.setattr(
        service, "_atualizar_cco_e_criar_evento",
        lambda *a, **k: {"success": True, "nova_versao": 2},
    )

    resultado = service.promover_correcao("CCO01_1", "usuario")

    assert resultado["success"] is True
    assert db.cco_edit_sessions.delete_one_calls == []


# ─── Cenário 3: promoção falha (validação bloqueada) ──────────────────────

def test_promover_correcao_validacao_bloqueada_nao_exclui(monkeypatch):
    cco = cco_corrigida()
    db = _FakeDb(cco)
    db_prd = _FakeDbPrd({"version": 0})

    service = IPCAPromocaoService(db, db_prd)

    monkeypatch.setattr(
        service, "_validar_promocao",
        lambda *a, **k: {
            "pode_promover": False,
            "motivos_bloqueio": ["Correção já foi promovida"],
            "avisos": [],
        },
    )

    resultado = service.promover_correcao("CCO01_1", "usuario")

    assert resultado["success"] is False
    assert resultado["error"] == "Promoção não permitida"
    assert db.cco_edit_sessions.delete_one_calls == []


# ─── Cenário 4: promoção falha (erro na atualização da CCO) ───────────────

def test_promover_correcao_falha_atualizacao_nao_exclui(monkeypatch):
    cco = cco_corrigida()
    db = _FakeDb(cco)
    db_prd = _FakeDbPrd({"version": 0})

    service = IPCAPromocaoService(db, db_prd)

    monkeypatch.setattr(
        service, "_validar_promocao",
        lambda *a, **k: {"pode_promover": True, "motivos_bloqueio": [], "avisos": []},
    )
    monkeypatch.setattr(
        service, "_atualizar_cco_e_criar_evento",
        lambda *a, **k: {"success": False, "erro": "falha na CCO"},
    )

    resultado = service.promover_correcao("CCO01_1", "usuario")

    assert resultado["success"] is False
    assert db.cco_edit_sessions.delete_one_calls == []


# ─── Filtro por tipo de correção (BUG-21030) ───────────────────────────────

class _FakeCursor:
    """Cursor fake de pymongo que guarda a query e devolve registros."""

    def __init__(self, registros, filtro):
        self._registros = registros
        self.filtro = filtro

    def sort(self, *args, **kwargs):
        return self._registros


class _FakeColBusca:
    """Fake de coleção com find capturando a query construída."""

    def __init__(self, registros=None):
        self._registros = registros or []
        self.ultima_query = None

    def find(self, query):
        self.ultima_query = query
        return _FakeCursor(self._registros, query)


class _FakeDbBusca:
    def __init__(self, registros=None, prd=False):
        self.conta_custo_oleo_corrigida_entity = _FakeColBusca(registros)
        if prd:
            self.conta_custo_oleo_entity = _FakeColBusca([])
            self.conta_custo_oleo = _FakeColBusca([])


def test_filtro_tipo_correcao_edicao_aplica_manual():
    db = _FakeDbBusca([])
    service = IPCAPromocaoService(db, _FakeDbBusca([], prd=True))

    service.pesquisar_correcoes_pendentes({"tipo_correcao": "EDICAO"})

    assert db.conta_custo_oleo_corrigida_entity.ultima_query["tipo_edicao"] == "MANUAL"


def test_filtro_tipo_correcao_ipca_igpm_aplica_ne_manual():
    db = _FakeDbBusca([])
    service = IPCAPromocaoService(db, _FakeDbBusca([], prd=True))

    service.pesquisar_correcoes_pendentes({"tipo_correcao": "IPCA_IGPM"})

    assert db.conta_custo_oleo_corrigida_entity.ultima_query["tipo_edicao"] == {"$ne": "MANUAL"}


def test_sem_filtro_tipo_preserva_filtro_status():
    db = _FakeDbBusca([])
    service = IPCAPromocaoService(db, _FakeDbBusca([], prd=True))

    service.pesquisar_correcoes_pendentes({"status_promocao": "PENDENTE"})

    assert "tipo_edicao" not in db.conta_custo_oleo_corrigida_entity.ultima_query
    assert db.conta_custo_oleo_corrigida_entity.ultima_query["status_promocao"] == "PENDENTE"


# ─── Determinação do tipo no resumo (BUG-21030) ────────────────────────────

def _resumo_db():
    db = _FakeDbBusca([])
    return IPCAPromocaoService(db, _FakeDbBusca([], prd=True))


DOC_BUG21030 = {
    "_id": "CCO01_1",
    "session_id": "sessao-123",
    "version": 0,
    "status_promocao": "PENDENTE",
    "dataReconhecimento": "2023-03-09T16:30:27-0300",
    "data_criacao_correcao": "2023-03-10T10:00:00-0300",
}


def test_resumo_tipo_correcao_edicao_quando_manual():
    service = _resumo_db()
    doc = dict(DOC_BUG21030, tipo_edicao="MANUAL")

    resumo = service._criar_resumo_correcao(doc)

    assert resumo["tipo_correcao"] == "EDICAO"


def test_resumo_tipo_correcao_ipca_igpm_quando_ausente():
    service = _resumo_db()

    resumo = service._criar_resumo_correcao(dict(DOC_BUG21030))

    assert resumo["tipo_correcao"] == "IPCA_IGPM"


def test_resumo_tipo_correcao_ipca_igpm_quando_diferente_de_manual():
    service = _resumo_db()
    doc = dict(DOC_BUG21030, tipo_edicao="AUTOMATICO")

    resumo = service._criar_resumo_correcao(doc)

    assert resumo["tipo_correcao"] == "IPCA_IGPM"
