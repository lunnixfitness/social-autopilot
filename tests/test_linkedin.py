import datetime as dt
import json

import pytest

from autopilot import linkedin as li
from autopilot.config import TZ, load_brand
from autopilot.guard import GuardError

BRAND = load_brand()


class Resp:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body or {}, headers or {}
        self.text = json.dumps(self._body)

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeSession:
    def __init__(self, respostas):
        self.respostas, self.chamadas = list(respostas), []

    def request(self, method, url, **kw):
        self.chamadas.append((method, url, kw))
        return self.respostas.pop(0)

    def get(self, url, **kw):
        return self.request("GET", url, **kw)


def api(respostas):
    return li.LinkedIn("tok", author="urn:li:person:abc", session=FakeSession(respostas), sleep=lambda s: None)


def item(**kw):
    base = dict(id="x1", pilar="educativo", texto="Texto de teste. " * 50, hashtags=["#Contabilidade"],
                primeiro_comentario="Link: https://velatrix-blog.pages.dev/blog/")
    base.update(kw)
    return li.Item(**base)


# ---------- fila real ----------
def test_fila_real_passa_nas_travas():
    fila = li.load_queue()
    assert len(fila) >= 5
    assert len({i.id for i in fila}) == len(fila), "id duplicado na fila"
    for i in fila:
        li.check_item(i, BRAND)
        assert "velatrix" in i.primeiro_comentario.lower() or "whatsapp" in i.primeiro_comentario


# ---------- escape ----------
def test_escape_preserva_hashtag_e_escapa_reservados():
    out = li.escape_commentary("Lei (2023) [x] *y* @z #ReformaTributaria")
    assert out == r"Lei \(2023\) \[x\] \*y\* \@z #ReformaTributaria"


# ---------- travas ----------
@pytest.mark.parametrize("texto", [
    "Ela começou com a Velatrix e ficou milionária. " * 20,
    "Veja o depoimento de quem usa. " * 30,
    "Resultado garantido para o seu cliente. " * 20,
    "Fature R$ 50.000 por mês com recuperação. " * 20,
])
def test_travas_barram_ficcao_e_promessa(texto):
    with pytest.raises(GuardError):
        li.check_item(item(texto=texto), BRAND)


def test_link_no_corpo_bloqueia():
    with pytest.raises(GuardError):
        li.check_item(item(texto="Veja https://velatrix.com.br " * 30), BRAND)


# ---------- API ----------
def test_post_e_comentario():
    a = api([Resp(201, headers={"x-restli-id": "urn:li:share:1"}), Resp(201, headers={"x-restli-id": "c1"})])
    urn = a.post_text("Olá (teste) #Tag")
    assert urn == "urn:li:share:1"
    m, url, kw = a.s.chamadas[0]
    assert url.endswith("/rest/posts") and kw["headers"]["LinkedIn-Version"] and kw["json"]["commentary"] == r"Olá \(teste\) #Tag"
    assert kw["json"]["visibility"] == "PUBLIC"
    a.comment(urn, "link")
    assert "socialActions/urn%3Ali%3Ashare%3A1/comments" in a.s.chamadas[1][1]


def test_401_vira_token_error():
    with pytest.raises(li.TokenError):
        api([Resp(401)]).post_text("x")


def test_422_pula():
    with pytest.raises(li.SkipPost):
        api([Resp(422, {"message": "bad"})]).post_text("x")


def test_429_tenta_de_novo():
    a = api([Resp(429), Resp(503), Resp(201, headers={"x-restli-id": "urn:li:share:2"})])
    assert a.post_text("x") == "urn:li:share:2"
    assert len(a.s.chamadas) == 3


# ---------- publicação ----------
def test_publica_uma_vez_e_respeita_intervalo(tmp_path):
    st = li.State(tmp_path / "s.json")
    fila = [item(id="a"), item(id="b")]
    agora = dt.datetime(2026, 11, 24, 8, 30, tzinfo=TZ)
    a = api([Resp(201, headers={"x-restli-id": "urn:li:share:9"}), Resp(201, headers={"x-restli-id": "c"})])
    assert li.publish_next(now=agora, api=a, queue=fila, state=st, brand=BRAND) == "publicado"
    assert st.posted("a") and not st.posted("b")
    # mesmo dia: intervalo de 20 h bloqueia
    assert li.publish_next(now=agora + dt.timedelta(hours=2), api=a, queue=fila, state=st, brand=BRAND) == "intervalo"


def test_fila_vazia(tmp_path):
    st = li.State(tmp_path / "s.json")
    assert li.publish_next(queue=[], state=st, brand=BRAND, api=api([])) == "vazia"


def test_idade_do_token():
    assert li.token_age_days("2026-10-01", dt.date(2026, 11, 22)) == 52
