import datetime as dt
import json
import re

import pytest
from PIL import Image

from autopilot import render, writer
from autopilot.build import build_day
from autopilot.config import History, load_brand, load_topics
from autopilot.guard import GuardError, ai_text_is_safe, check_forbidden
from autopilot.planner import plan_day, plan_range

BRAND = load_brand()
TOPICS = load_topics()
MONDAY = dt.date(2026, 11, 23)


# ---------- banco de temas ----------
def test_topics_schema():
    ids = [t.id for t in TOPICS]
    assert len(ids) == len(set(ids)), "id duplicado"
    pilares = set(BRAND["rodizio_pilares"])
    for t in TOPICS:
        assert t.pilar in pilares, t.id
        assert 3 <= len(t.pontos) <= 5, t.id
        assert t.base_legal.strip(), t.id
        assert len(t.hashtags) <= 4 and all(h.startswith("#") and " " not in h for h in t.hashtags), t.id
        assert len(t.titulo_yt) <= 100, t.id
    for p in pilares:
        assert any(t.pilar == p for t in TOPICS), f"pilar sem tema: {p}"


def test_bank_has_no_forbidden_terms():
    for t in TOPICS:
        check_forbidden(t.texto_banco, BRAND["termos_proibidos"])


# ---------- travas ----------
def test_forbidden_blocks():
    with pytest.raises(GuardError):
        check_forbidden("Resultado GARANTIDO na sua ação", BRAND["termos_proibidos"])


def test_ai_text_rejects_invented_number_and_law():
    t = next(t for t in TOPICS if t.id == "tema69")
    ok, _ = ai_text_is_safe("Você recupera 20 anos de imposto!", t.texto_banco, BRAND["termos_proibidos"])
    assert not ok
    ok, _ = ai_text_is_safe("Segundo o art. 999 do CTN, dá para recuperar.", t.texto_banco, BRAND["termos_proibidos"])
    assert not ok
    ok, why = ai_text_is_safe("No Tema 69, o STF tirou o ICMS da base. Dá para recuperar 5 anos.", t.texto_banco, BRAND["termos_proibidos"])
    assert ok, why


def test_caption_without_ai_has_disclaimer_and_limits(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    for t in TOPICS:
        cap, origem = writer.caption(t, BRAND)
        assert origem == "banco"
        assert BRAND["aviso_legal"] in cap and t.base_legal in cap
        assert len(cap) <= 2200
        assert "#" not in cap  # hashtags vão no 1º comentário
        tags = writer.hashtags(t, BRAND)
        assert len(tags) <= BRAND["max_hashtags"]


def test_ai_fallback_when_unsafe(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(writer, "_gemini_rewrite", lambda *a: "Causa ganha em 30 dias!")
    cap, origem = writer.caption(TOPICS[0], BRAND)
    assert origem == "banco" and "Causa ganha" not in cap


def test_youtube_meta():
    for t in TOPICS:
        m = writer.youtube_meta(t, BRAND)
        assert len(m["title"]) <= 100 and "#shorts" in (m["title"] + m["description"]).lower()
        assert BRAND["aviso_legal"] in m["description"]


# ---------- calendário e rodízio ----------
def test_calendar():
    plans = plan_range(MONDAY, 7, [], TOPICS, BRAND)
    fmts = [p.ig_format for p in plans]
    assert fmts == ["reel", "carrossel", "reel", "carrossel", "reel", "reel", "dica_story"]
    assert [p.youtube for p in plans] == [True] * 6 + [False]


def test_velatrix_every_fifth_and_no_repeats():
    plans = plan_range(MONDAY, 30, [], TOPICS, BRAND)
    pil = [p.topic.pilar for p in plans]
    assert all(pil[i] == "velatrix" for i in range(4, 30, 5))
    assert sum(x == "velatrix" for x in pil) == 6
    ids = [p.topic.id for p in plans]
    for i in range(len(ids) - 1):
        assert ids[i] != ids[i + 1]
    assert len(set(ids[:15])) >= 12  # quase todo o banco antes de repetir


def test_rerun_same_day_keeps_topic():
    hist = [{"date": MONDAY.isoformat(), "topic": "cpc473", "channels": {"instagram": {"ok": True}}}]
    assert plan_day(MONDAY, hist, TOPICS, BRAND).topic.id == "cpc473"


def test_history_idempotency(tmp_path):
    h = History(path=tmp_path / "h.json")
    h.record("2026-11-23", "tema69", "instagram", {"ok": True, "id": "1"})
    h2 = History.load(tmp_path / "h.json")
    assert h2.done("2026-11-23", "instagram") and not h2.done("2026-11-23", "youtube")


# ---------- arte ----------
def test_render_sizes(tmp_path, monkeypatch):
    foto = tmp_path / "f.jpg"
    Image.new("RGB", (900, 1200), (120, 90, 60)).save(foto)
    monkeypatch.setattr(render, "photos", lambda: [foto])
    t = next(t for t in TOPICS if t.id == "ruido")
    slides = render.carousel(t, BRAND, tmp_path, MONDAY)
    assert 2 <= len(slides) <= 10
    assert all(Image.open(s).size == (1080, 1350) for s in slides)
    assert Image.open(render.story(t, BRAND, tmp_path, MONDAY, "chamada")).size == (1080, 1920)
    assert Image.open(render.cover(t, BRAND, tmp_path, MONDAY)).size == (1080, 1920)


@pytest.mark.skipif(not render.shutil.which("ffmpeg"), reason="sem ffmpeg")
def test_build_day_video(tmp_path):
    import subprocess

    plan = plan_day(MONDAY, [], TOPICS, BRAND)
    m = build_day(plan, BRAND, tmp_path, use_ai=False)
    day = tmp_path / MONDAY.isoformat()
    assert json.loads((day / "plan.json").read_text())["instagram"]["format"] == "reel"
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height:format=duration", "-of", "json", str(day / m["youtube"]["video"])],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(out.stdout)
    codecs = {s["codec_name"] for s in info["streams"]}
    assert codecs == {"h264", "aac"}
    v = next(s for s in info["streams"] if s["codec_name"] == "h264")
    assert (v["width"], v["height"]) == (1080, 1920)
    assert 10 <= float(info["format"]["duration"]) <= 60  # Short e Reel


def test_workflow_cron_matches_brand_time():
    import pathlib

    f = pathlib.Path(__file__).parents[1] / ".github/workflows/autopilot.yml"
    if not f.exists():
        pytest.skip("autopilot.yml ainda não instalado (entra junto com os tokens)")
    wf = f.read_text()
    h, mnt = map(int, BRAND["horario_local"].split(":"))
    cron = re.search(r'cron:\s*"(\d+) (\d+) ', wf)
    assert cron and (int(cron.group(1)), int(cron.group(2))) == (mnt, (h + 3) % 24)  # BRT = UTC-3


# ---------- publicador Instagram (API simulada) ----------
class _Resp:
    def __init__(self, body, code=200):
        self._b, self.status_code, self.text = body, code, str(body)

    def json(self):
        return self._b


class FakeIG:
    def __init__(self):
        self.calls, self.n = [], 0

    def request(self, method, url, params=None, data=None, timeout=None):
        p = params or data
        self.calls.append((method, url.split("/v")[-1].split("/", 1)[-1], {k: v for k, v in p.items() if k != "access_token"}))
        if url.endswith("/me"):
            return _Resp({"user_id": "42", "username": "x"})
        if method == "GET":
            return _Resp({"status_code": "FINISHED"})
        self.n += 1
        return _Resp({"id": f"id{self.n}"})


def test_instagram_carousel_flow():
    from autopilot.instagram import Instagram

    s = FakeIG()
    api = Instagram("tok", session=s)
    mid = api.carousel(["https://x/1.jpg", "https://x/2.jpg"], "legenda")
    api.comment(mid, "#a #b")
    posts = [c for c in s.calls if c[0] == "POST"]
    assert posts[0][2] == {"image_url": "https://x/1.jpg", "is_carousel_item": "true"}
    assert posts[2][2]["media_type"] == "CAROUSEL" and posts[2][2]["children"] == "id1,id2"
    assert posts[3][1] == "42/media_publish" and posts[3][2] == {"creation_id": "id3"}
    assert posts[4][1] == f"{mid}/comments"


def test_instagram_error_surfaces():
    from autopilot.instagram import IGError, Instagram

    class Bad(FakeIG):
        def request(self, method, url, **kw):
            if url.endswith("/me"):
                return _Resp({"user_id": "42"})
            return _Resp({"error": {"message": "Invalid OAuth access token"}}, 400)

    api = Instagram("tok", session=Bad())
    with pytest.raises(IGError, match="Invalid OAuth"):
        api.story("https://x/s.jpg")


# ---------- narração (TTS simulado) ----------
@pytest.mark.skipif(not render.shutil.which("ffmpeg"), reason="sem ffmpeg")
def test_narration_mix_extends_scenes(tmp_path, monkeypatch):
    import subprocess

    from autopilot import tts

    def fake_synth(text, dst, brand):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=440:d=5",
                        "-c:a", "aac", "-ar", "48000", str(dst)], check=True)
        return dst

    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(tts, "synth", fake_synth)
    img = Image.new("RGB", (1080, 1920), (10, 30, 60))
    out, voiced = render.encode_scenes([(img, 2.0), (img, 2.0)], tmp_path / "v.mp4", MONDAY,
                                       brand=BRAND, narration=["um", "dois"])
    assert voiced
    info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                          capture_output=True, text=True).stdout
    assert float(info) > 10  # cada cena cresceu para caber a fala de 5 s
    vol = subprocess.run(["ffmpeg", "-i", str(out), "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    assert "mean_volume: -inf" not in vol


def test_no_key_no_voice(monkeypatch):
    from autopilot import tts

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert not tts.enabled(BRAND)
    assert tts.synth("oi", __import__("pathlib").Path("/tmp/x.m4a"), BRAND) is None


def test_demo_narration_is_clean():
    from autopilot.demos import demos

    for nome, (titulo, itens) in demos().items():
        assert len(titulo) <= 100
        for _, _, fala in itens:
            check_forbidden(fala, BRAND["termos_proibidos"])


# ---------- Facebook (API simulada) ----------
def test_facebook_album_and_reel_flow():
    from autopilot.facebook import FacebookPage, fb_text

    class S:
        def __init__(self):
            self.calls, self.n = [], 0

        def request(self, method, url, params=None, data=None, headers=None, timeout=None):
            self.calls.append((method, url, dict(data or params or {}), headers))
            if method == "GET":
                return _Resp({"status": {"video_status": "ready"}})
            if (data or {}).get("upload_phase") == "start":
                return _Resp({"video_id": "v1", "upload_url": "https://rupload.facebook.com/x/v1"})
            self.n += 1
            return _Resp({"id": f"p{self.n}", "success": True})

    s = S()
    page = FacebookPage("123", "tok", session=s)
    pid = page.album(["https://x/1.jpg", "https://x/2.jpg"], "texto")
    feed = [c for c in s.calls if c[1].endswith("/123/feed")][0][2]
    assert feed["attached_media[0]"] == '{"media_fbid": "p1"}' and pid == "p3"
    s.calls.clear()
    assert page.reel("https://x/r.mp4", "desc") == "v1"
    up = [c for c in s.calls if "rupload" in c[1]][0]
    assert up[3] == {"Authorization": "OAuth tok", "file_url": "https://x/r.mp4"}
    fin = [c for c in s.calls if c[2].get("upload_phase") == "finish"][0][2]
    assert fin["video_state"] == "PUBLISHED" and fin["description"] == "desc"
    b = dict(BRAND, facebook={"grupo_url": "https://fb.com/groups/x", "convite_grupo": "Grupo:"})
    t = fb_text("legenda", ["#a", "#b", "#c", "#d"], b)
    assert "https://fb.com/groups/x" in t and "#d" not in t
