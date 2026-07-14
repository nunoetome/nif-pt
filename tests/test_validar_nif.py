import pytest
from nif_pt.validar_nif import validar_nif, _calcular_digito_controlo


# ── NIFs válidos conhecidos ──────────────────────────────────────────

CASOS_VALIDOS = [
    ("503504564", "Pessoa coletiva (empresa)"),
    ("509442013", "Pessoa coletiva (empresa)"),
    ("501964843", "Pessoa coletiva (empresa)"),
    ("999999990", "Outras entidades"),
    ("123456789", "Pessoa singular (residente)"),
]


# ── NIFs com prefixo PT ─────────────────────────────────────────────

CASOS_VALIDOS_COM_PT = [
    ("PT503504564", "Pessoa coletiva (empresa)"),
    ("pt503504564", "Pessoa coletiva (empresa)"),
    ("Pt503504564", "Pessoa coletiva (empresa)"),
    ("PT 503504564", "Pessoa coletiva (empresa)"),
    ("pt 503504564", "Pessoa coletiva (empresa)"),
    ("  PT503504564  ", "Pessoa coletiva (empresa)"),
]


# ── NIFs inválidos conhecidos ────────────────────────────────────────

CASOS_INVALIDOS = [
    "503504565",
    "503504560",
    "509442010",
    "501964840",
]


# ── Input com caracteres errados (9 chars, mas não só dígitos) ───────

CASOS_CARACTERES_ERRADOS = [
    "abcdefghi",
    "12345abc9",
    "ABC123456",
    "PTabcdefghi",
]


# ── Input com comprimento errado ─────────────────────────────────────

CASOS_COMPRIMENTO_ERRADO = [
    "",
    "123",
    "12345678",
    "1234567890",
    "12-3456789",
    "12.345.678",
    "PT123",
]


# ── Testes ───────────────────────────────────────────────────────────

class TestValidarNIF:
    @pytest.mark.parametrize("nif,tipo_esperado", CASOS_VALIDOS)
    def test_nifs_validos(self, nif, tipo_esperado):
        r = validar_nif(nif)
        assert r.valido is True
        assert r.digito_fornecido == r.digito_esperado
        assert r.tipo_entidade == tipo_esperado
        assert r.erro is None

    @pytest.mark.parametrize("nif,tipo_esperado", CASOS_VALIDOS_COM_PT)
    def test_nifs_validos_com_pt(self, nif, tipo_esperado):
        r = validar_nif(nif)
        assert r.valido is True
        assert r.nif == "503504564"
        assert r.tipo_entidade == tipo_esperado
        assert r.erro is None

    @pytest.mark.parametrize("nif", CASOS_INVALIDOS)
    def test_nifs_invalidos(self, nif):
        r = validar_nif(nif)
        assert r.valido is False
        assert r.digito_fornecido != r.digito_esperado
        assert r.erro is None

    @pytest.mark.parametrize("nif", CASOS_CARACTERES_ERRADOS)
    def test_caracteres_errados(self, nif):
        r = validar_nif(nif)
        assert r.valido is False
        assert r.erro is not None
        assert "Caracteres inválidos" in r.erro

    @pytest.mark.parametrize("nif", CASOS_COMPRIMENTO_ERRADO)
    def test_comprimento_errado(self, nif):
        r = validar_nif(nif)
        assert r.valido is False
        assert r.erro is not None
        assert "Comprimento inválido" in r.erro

    def test_resultado_e_dataclass(self):
        r = validar_nif("503504564")
        assert hasattr(r, "nif")
        assert hasattr(r, "valido")
        assert hasattr(r, "digito_fornecido")
        assert hasattr(r, "digito_esperado")
        assert hasattr(r, "primeiro_digito")
        assert hasattr(r, "tipo_entidade")
        assert hasattr(r, "erro")

    def test_primeiro_digito_reflectido(self):
        r = validar_nif("503504564")
        assert r.primeiro_digito == 5

    def test_stripping_espacos(self):
        r = validar_nif("  503504564  ")
        assert r.valido is True
        assert r.nif == "503504564"

    def test_erro_none_quando_valido(self):
        r = validar_nif("503504564")
        assert r.erro is None


class TestCalcularDigitoControlo:
    @pytest.mark.parametrize("nif,digito_esperado", [
        ("50350456", 4),
        ("50944201", 3),
        ("50196484", 3),
        ("12345678", 9),
    ])
    def test_calculo_correto(self, nif, digito_esperado):
        assert _calcular_digito_controlo(nif) == digito_esperado
