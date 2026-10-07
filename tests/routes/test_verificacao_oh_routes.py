"""
Testes de rota para o blueprint de Verificação de OH (FEAT-001).

Cobre:
  Cenário 6  - acesso negado sem permissão CCO_VIEW (FR-012)
  Cenário 10 - exportação CSV de faixas é gerada no client-side, sem chamada ao backend (FR-011)
  + fluxo básico de sucesso das APIs /api/verificar, /api/analise-exp e /download-csv
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.config import Config


def _definir_roles(client, roles):
    """Redefine a sessão de teste com as roles informadas.

    Recria a sessão inteira (em vez de só mesclar) porque o fixture `mock_api_gateway`
    congela o relógio (freeze_time); reabrir um cookie assinado com o tempo real sob o
    tempo congelado faz o itsdangerous invalidar a sessão anterior (idade negativa).
    """
    with client.session_transaction() as sess:
        sess["token"] = "fake-test-token"
        sess["token_exp"] = 9999999999
        sess["user_data"] = {
            "id": "user123",
            "email": "test@ppsa.com",
            "roles": roles,
        }


@pytest.fixture(autouse=True)
def _habilitar_verificacao_de_permissao(monkeypatch):
    """Garante que os decorators de permissão realmente sejam avaliados nos testes de rota
    (independentemente do valor de DISABLE_AUTH no .env local)."""
    monkeypatch.setattr(Config, "DISABLE_AUTH", "False")


class TestPermissoesRotas:
    def test_index_sem_permissao_cco_view_e_redirecionado(self, client, mock_api_gateway):
        _definir_roles(client, [])  # nenhuma role -> sem CCO_VIEW

        response = client.get("/verificacao-oh/")

        assert response.status_code == 302

    def test_api_verificar_sem_permissao_cco_view_retorna_403_json(self, client, mock_api_gateway):
        _definir_roles(client, [])

        response = client.post("/verificacao-oh/api/verificar", json={})

        assert response.status_code == 403
        payload = response.get_json()
        assert payload["success"] is False

    def test_api_verificar_bloqueado_para_role_client(self, client, mock_api_gateway):
        # CLIENT combinado com VIEWER: tem CCO_VIEW (via VIEWER) mas é bloqueado por deny_client()
        _definir_roles(client, ["VIEWER", "CLIENT"])

        response = client.post("/verificacao-oh/api/verificar", json={})

        assert response.status_code == 403
        payload = response.get_json()
        assert payload["success"] is False

    def test_api_verificar_permitido_para_viewer_sem_client(self, client, mock_api_gateway):
        _definir_roles(client, ["VIEWER"])

        with patch("app.routes.verificacao_oh_routes._get_service") as mock_get_service:
            svc = MagicMock()
            svc.buscar_ccos.return_value = []
            mock_get_service.return_value = svc

            response = client.post("/verificacao-oh/api/verificar", json={})

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["success"] is True


class TestApiVerificar:
    def test_retorna_resultados_e_estatisticas(self, client, mock_api_gateway):
        _definir_roles(client, ["VIEWER"])

        with patch("app.routes.verificacao_oh_routes._get_service") as mock_get_service:
            svc = MagicMock()
            svc.buscar_ccos.return_value = [{"_id": "CCO-001"}]
            svc.verificar_oh.return_value = [{"cco_id": "CCO-001", "status_geral": "OK"}]
            svc.calcular_estatisticas.return_value = {"total_linhas": 1, "total_ok": 1}
            mock_get_service.return_value = svc

            response = client.post(
                "/verificacao-oh/api/verificar",
                json={"contratoCpp": "CONTRATO-A"},
            )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["total_encontrados"] == 1
        assert payload["resultados"][0]["status_geral"] == "OK"
        assert payload["estatisticas"]["total_ok"] == 1

    def test_retorna_vazio_quando_nenhuma_cco_encontrada(self, client, mock_api_gateway):
        _definir_roles(client, ["VIEWER"])

        with patch("app.routes.verificacao_oh_routes._get_service") as mock_get_service:
            svc = MagicMock()
            svc.buscar_ccos.return_value = []
            mock_get_service.return_value = svc

            response = client.post("/verificacao-oh/api/verificar", json={})

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["resultados"] == []
        assert payload["total_encontrados"] == 0


class TestApiAnaliseExp:
    def test_exige_cco_id(self, client, mock_api_gateway):
        _definir_roles(client, ["VIEWER"])

        response = client.get("/verificacao-oh/api/analise-exp")

        assert response.status_code == 400

    def test_retorna_404_quando_cco_nao_encontrada(self, client, mock_api_gateway):
        _definir_roles(client, ["VIEWER"])

        with patch("app.routes.verificacao_oh_routes._get_service") as mock_get_service:
            svc = MagicMock()
            svc.analisar_faixas_exploracao.side_effect = ValueError("CCO não encontrada")
            mock_get_service.return_value = svc

            response = client.get("/verificacao-oh/api/analise-exp?cco_id=INEXISTENTE")

        assert response.status_code == 404

    def test_retorna_analise_com_sucesso(self, client, mock_api_gateway):
        _definir_roles(client, ["VIEWER"])

        with patch("app.routes.verificacao_oh_routes._get_service") as mock_get_service:
            svc = MagicMock()
            svc.analisar_faixas_exploracao.return_value = {
                "contrato": "CONTRATO-A", "ano": 2026, "linhas": []
            }
            mock_get_service.return_value = svc

            response = client.get("/verificacao-oh/api/analise-exp?cco_id=CCO-001")

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["contrato"] == "CONTRATO-A"


class TestDownloadCsv:
    def test_sem_resultado_na_sessao_retorna_400(self, client, mock_api_gateway):
        _definir_roles(client, ["VIEWER"])

        response = client.get("/verificacao-oh/download-csv")

        assert response.status_code == 400

    def test_com_resultado_na_sessao_retorna_csv(self, client, mock_api_gateway):
        _definir_roles(client, ["VIEWER"])

        with patch("app.routes.verificacao_oh_routes._get_service") as mock_get_service:
            svc = MagicMock()
            svc.buscar_ccos.return_value = [{"_id": "CCO-001"}]
            svc.verificar_oh.return_value = [{"cco_id": "CCO-001", "status_geral": "OK"}]
            svc.calcular_estatisticas.return_value = {}
            svc.gerar_csv.return_value = "\ufeffID CCO;...\nCCO-001;...\n"
            mock_get_service.return_value = svc

            resp_verificar = client.post("/verificacao-oh/api/verificar", json={})
            assert resp_verificar.status_code == 200

            response = client.get("/verificacao-oh/download-csv")

        assert response.status_code == 200
        assert response.mimetype == "text/csv"
        assert "attachment" in response.headers["Content-Disposition"]


class TestExportacaoClientSidePorFaixas:
    """Cenário 10 (FR-011): a exportação de faixas é feita inteiramente no navegador."""

    def test_template_analise_exp_exporta_via_blob_sem_chamar_backend(self):
        from pathlib import Path

        template_path = (
            Path(__file__).resolve().parents[2]
            / "app" / "templates" / "verificacao_oh" / "analise_exp.html"
        )
        html = template_path.read_text(encoding="utf-8")

        assert "function exportarCSV()" in html
        assert "new Blob(" in html
        # A rota download-csv (backend) é do módulo de resultados em lote, não da análise de faixas
        assert "fetch(" not in html.split("function exportarCSV()")[1].split("function ")[0]
