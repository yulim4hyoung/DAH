"""결계(結界) 결과 대시보드(HTML) 생성 — 자체 완결형(그림 base64 임베드).

python src/make_report.py            → docs/dashboard.html (브라우저로 열기)
python src/make_report.py --fragment <경로>   → Artifact용 조각(head/body 래퍼 없이)

터미널 로그를 넘어, 아키텍처·3개 시나리오(공격→탐지→대응)·지표를 한 화면에 정리한다.
먼저 `python src/train.py --scenario all` 로 그림·지표를 생성해 두어야 한다.
"""
from __future__ import annotations
import os
import sys
import json
import base64
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.paths import REPO_ROOT, results_dir
from src import mapping
from src.scenarios import a2_gnss, b2_satcom, b3_can

MODS = {"a2_gnss": a2_gnss, "b2_satcom": b2_satcom, "b3_can": b3_can}
DET = {"a2_gnss": "1D-CNN · 다특징 시계열", "b2_satcom": "오토인코더 · 비지도 이상탐지",
       "b3_can": "경량 MLP · 윈도 특징"}
DATA = {"a2_gnss": "합성", "b2_satcom": "합성", "b3_can": "합성(실 Car-Hacking 로더 포함)"}
CHARTS = {
    "a2_gnss": [("roc_attack.png", "공격탐지 ROC"), ("confusion_matrix.png", "혼동행렬"),
                ("detection_latency.png", "탐지지연 분포"), ("timeseries_example.png", "점진 표류 vs 탐지시점"),
                ("sla_tradeoff.png", "SLA 트레이드오프"), ("adaptive_robustness.png", "적응형 공격 강건성")],
    "b2_satcom": [("roc.png", "이상탐지 ROC"), ("recon_error_hist.png", "재구성오차 분포"),
                  ("timeline_example.png", "AcidRain형 전개 vs 탐지"), ("sla_tradeoff.png", "SLA 트레이드오프")],
    "b3_can": [("confusion_matrix.png", "혼동행렬"), ("per_class_f1.png", "클래스별 F1"),
               ("roc_attack.png", "공격탐지 ROC"), ("sla_tradeoff.png", "SLA 트레이드오프")],
}
LAYER_TONE = {"a2_gnss": "pnt", "b2_satcom": "sat", "b3_can": "bus"}


def _img(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def _meta(key: str) -> dict:
    p = os.path.join(results_dir(), key, "run_meta.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def _headline(key: str, m: dict):
    try:
        if key == "a2_gnss":
            return [("공격탐지 AUC", f"{m['auc_attack']:.3f}"), ("정확도", f"{m['test_accuracy']:.3f}"),
                    ("스푸핑 탐지지연", f"{m['median_latency_spoof_s']:.0f}s")]
        if key == "b2_satcom":
            return [("이상탐지 AUC", f"{m['auc']:.3f}"), ("F1", f"{m['f1']:.3f}"),
                    ("탐지지연", f"{m['median_latency_buckets']:.0f} 버킷")]
        if key == "b3_can":
            return [("macro-F1", f"{m['macro_f1']:.3f}"), ("정확도", f"{m['test_accuracy']:.3f}"),
                    ("공격탐지 AUC", f"{m['auc_attack']:.3f}")]
    except KeyError:
        return []
    return []


CSS = r"""
<style>
:root{
  --bg:#f5f8fa; --panel:#ffffff; --panel2:#eef3f7; --border:#dde5ec;
  --text:#17232e; --muted:#5b6a77; --accent:#0e8ea3;
  --threat:#c8362f; --defend:#1f8a53; --warn:#b5730a;
  --pnt:#0e8ea3; --sat:#6d4bd6; --bus:#b5730a;
  --mono:"Cascadia Code","Consolas",ui-monospace,monospace;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI","Malgun Gothic","Apple SD Gothic Neo",Roboto,sans-serif;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#0d151d; --panel:#15212c; --panel2:#1b2836; --border:#26333f;
  --text:#cdd8e1; --muted:#8595a2; --accent:#2bb6c8;
  --threat:#e5605b; --defend:#41b877; --warn:#e0a53a;
  --pnt:#2bb6c8; --sat:#a58bf0; --bus:#e0a53a;
}}
:root[data-theme="light"]{--bg:#f5f8fa;--panel:#fff;--panel2:#eef3f7;--border:#dde5ec;--text:#17232e;--muted:#5b6a77;--accent:#0e8ea3;--threat:#c8362f;--defend:#1f8a53;--warn:#b5730a;--pnt:#0e8ea3;--sat:#6d4bd6;--bus:#b5730a;}
:root[data-theme="dark"]{--bg:#0d151d;--panel:#15212c;--panel2:#1b2836;--border:#26333f;--text:#cdd8e1;--muted:#8595a2;--accent:#2bb6c8;--threat:#e5605b;--defend:#41b877;--warn:#e0a53a;--pnt:#2bb6c8;--sat:#a58bf0;--bus:#e0a53a;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);line-height:1.55;
  -webkit-font-smoothing:antialiased;font-size:15px}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
header.top{position:sticky;top:0;z-index:10;background:color-mix(in srgb,var(--bg) 88%,transparent);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--border)}
.top .wrap{display:flex;align-items:center;gap:14px;height:56px}
.brand{font-weight:800;letter-spacing:.02em;font-size:17px}
.brand small{color:var(--muted);font-weight:600;font-size:12px;margin-left:8px}
.top .sp{flex:1}
.pill{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;
  font-size:12px;font-weight:600;border:1px solid var(--border);background:var(--panel2);color:var(--muted)}
.pill.dot::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--defend)}
.hero{padding:46px 0 24px}
.eyebrow{font-family:var(--mono);font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}
h1{font-size:36px;line-height:1.15;margin:.35em 0 .2em;text-wrap:balance;letter-spacing:-.01em}
.lead{color:var(--muted);max-width:60ch;font-size:16px}
.concepts{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}
.concept{border:1px solid var(--border);border-radius:12px;padding:12px 14px;background:var(--panel);min-width:180px;flex:1}
.concept b{display:block;font-size:13px}
.concept span{color:var(--muted);font-size:12.5px}
section{padding:26px 0;border-top:1px solid var(--border)}
.h2{font-size:13px;font-family:var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:0 0 16px}
.arch{width:100%;border:1px solid var(--border);border-radius:var(--radius,14px);background:var(--panel);border-radius:14px}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.stat{border:1px solid var(--border);border-radius:14px;background:var(--panel);padding:16px;position:relative;overflow:hidden}
.stat::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--tone)}
.stat .k{font-family:var(--mono);font-size:11.5px;color:var(--muted);letter-spacing:.06em}
.stat .big{font-size:30px;font-weight:800;font-variant-numeric:tabular-nums;margin:2px 0}
.stat .sub{font-size:12.5px;color:var(--muted)}
.stat .lab{margin-top:8px;font-size:12px}
.card{border:1px solid var(--border);border-radius:16px;background:var(--panel);overflow:hidden;margin-bottom:18px}
.card .head{display:flex;align-items:center;gap:12px;padding:16px 18px;border-bottom:1px solid var(--border);flex-wrap:wrap}
.badge{font-family:var(--mono);font-size:12px;font-weight:700;padding:3px 9px;border-radius:8px;
  color:#fff;background:var(--tone)}
.card h3{font-size:18px;margin:0}
.tag{margin-left:auto;display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:700;
  color:var(--threat);border:1px solid color-mix(in srgb,var(--threat) 40%,var(--border));
  background:color-mix(in srgb,var(--threat) 10%,transparent);padding:3px 10px;border-radius:999px}
.card .body{padding:18px}
.meta{display:flex;flex-wrap:wrap;gap:8px 18px;font-size:13px;color:var(--muted);margin-bottom:16px}
.meta b{color:var(--text);font-weight:600}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.kc{list-style:none;margin:0;padding:0;counter-reset:s}
.kc li{display:flex;gap:10px;padding:7px 0;border-bottom:1px dashed var(--border);font-size:13.5px}
.kc li:last-child{border-bottom:0}
.kc .n{font-family:var(--mono);font-weight:700;color:var(--threat);min-width:18px}
.kc .act{flex:1}
.kc .tool{font-family:var(--mono);font-size:11.5px;color:var(--muted)}
.charts{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.charts figure{margin:0;border:1px solid var(--border);border-radius:12px;overflow:hidden;background:var(--panel2)}
.charts img{width:100%;display:block}
.charts figcaption{font-size:11.5px;color:var(--muted);padding:6px 10px;font-family:var(--mono)}
.pb{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:18px;padding-top:16px;border-top:1px solid var(--border)}
.pb h4{margin:0 0 8px;font-size:12px;font-family:var(--mono);letter-spacing:.06em;text-transform:uppercase}
.pb .col.respond h4{color:var(--threat)} .pb .col.recover h4{color:var(--warn)} .pb .col.protect h4{color:var(--defend)}
.pb .col ul{margin:0;padding-left:16px;font-size:12.5px;color:var(--text)}
.pb .col li{margin:3px 0}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:14px}
.chip{font-family:var(--mono);font-size:11px;padding:3px 8px;border-radius:6px;border:1px solid var(--border);
  background:var(--panel2);color:var(--muted)}
.note{font-size:12.5px;color:var(--muted);border:1px solid var(--border);border-left:3px solid var(--warn);
  border-radius:8px;padding:12px 14px;background:var(--panel)}
footer{padding:30px 0 50px;color:var(--muted);font-size:12.5px;border-top:1px solid var(--border)}
@media (max-width:760px){.stats,.grid2,.charts,.pb{grid-template-columns:1fr}h1{font-size:28px}}
</style>
"""


def build_content() -> str:
    p = []
    arch = _img(os.path.join(results_dir(), "overview", "architecture.png"))
    # 헤더 + 히어로
    p.append('<header class="top"><div class="wrap">'
             '<div class="brand">결계<small>結界 · 팀 백공검(白空劍)</small></div>'
             '<div class="sp"></div>'
             '<span class="pill dot">DNN 상시 · LLM/규칙 하이브리드</span>'
             '<a class="pill" href="https://github.com/yulim4hyoung/DAH" target="_blank" rel="noopener">GitHub ↗</a>'
             '</div></header>')
    p.append('<main class="wrap">')
    p.append('<div class="hero"><div class="eyebrow">DAH 2026 · UAV/UGV 통신보안</div>'
             '<h1>결계(結界) — 공격을 탐지하고 스스로 대응하는 멀티에이전트 방어</h1>'
             '<p class="lead">통합본 서베이의 6개 위협 시나리오를 관통하는 하나의 프레임워크. '
             '🔴공격 에이전트가 6단계 킬체인을 구동하면 🧠DNN 탐지기가 이상을 잡고 '
             '🔵LLM(Claude) 방어 에이전트가 위협을 분류해 NIST CSF 플레이북으로 대응한다.</p>'
             '<div class="concepts">'
             '<div class="concept"><b>🧠 DNN = 감각(탐지)</b><span>1D-CNN·오토인코더·MLP로 신호/트래픽 이상을 점수화</span></div>'
             '<div class="concept"><b>🔵 LLM = 두뇌(판단)</b><span>Claude가 경보를 통합·위협분류·플레이북 선택. 키 없으면 규칙 폴백</span></div>'
             '<div class="concept"><b>📏 규칙 = 설명가능</b><span>RAIM·화이트리스트로 "왜 이상인지" 근거 제시</span></div>'
             '</div></div>')
    # 아키텍처
    if arch:
        p.append(f'<section><div class="h2">시스템 아키텍처</div>'
                 f'<img class="arch" src="{arch}" alt="결계 아키텍처"></section>')
    # 성능 요약
    p.append('<section><div class="h2">탐지 성능 요약 (합성데이터 PoC · 시드 42)</div><div class="stats">')
    for key in MODS:
        m = _meta(key); hl = _headline(key, m); tone = LAYER_TONE[key]
        big = hl[0] if hl else ("-", "-")
        subs = " · ".join(f"{k} {v}" for k, v in hl[1:]) if len(hl) > 1 else ""
        p.append(f'<div class="stat" style="--tone:var(--{tone})">'
                 f'<div class="k">{MODS[key].LAYER} · {big[0]}</div>'
                 f'<div class="big">{big[1]}</div>'
                 f'<div class="sub">{subs}</div>'
                 f'<div class="lab">{MODS[key].TITLE}</div></div>')
    p.append('</div></section>')
    # 시나리오 패널
    p.append('<section><div class="h2">시나리오별 공격 → 탐지 → 대응</div>')
    for key, mod in MODS.items():
        tone = LAYER_TONE[key]; info = mapping.threat_info(mod.THREAT); pb = mapping.playbook(mod.THREAT)
        kc = "".join(f'<li><span class="n">{s.split()[0]}</span>'
                     f'<span class="act">{" ".join(s.split()[1:])} — {act}</span>'
                     f'<span class="tool">{tool}</span></li>' for s, act, tool in mod.KILLCHAIN)
        figs = ""
        for fn, cap in CHARTS[key]:
            d = _img(os.path.join(results_dir(), key, fn))
            if d:
                figs += f'<figure><img src="{d}" alt="{cap}"><figcaption>{cap}</figcaption></figure>'
        mitre = "".join(f'<span class="chip">{x}</span>' for x in info["mitre"])
        sparta = "".join(f'<span class="chip">{x}</span>' for x in info["sparta"]) or '<span class="chip">SPARTA -</span>'
        def col(cls, title, phase):
            items = "".join(f"<li>{a}</li>" for a in pb.get(phase, []))
            return f'<div class="col {cls}"><h4>{title}</h4><ul>{items}</ul></div>'
        pbh = ('<div class="pb">' + col("respond", "🔴 대응(Respond)", "respond")
               + col("recover", "🟠 복구(Recover)", "recover")
               + col("protect", "🟢 예방·파훼(Protect)", "protect") + '</div>')
        p.append(
            f'<div class="card" style="--tone:var(--{tone})"><div class="head">'
            f'<span class="badge">{mod.LAYER}</span><h3>{mod.TITLE}</h3>'
            f'<span class="tag">🚨 {info["name"]}</span></div><div class="body">'
            f'<div class="meta"><span>대상 <b>{mod.TARGET}</b></span>'
            f'<span>탐지기 <b>{DET[key]}</b></span><span>데이터 <b>{DATA[key]}</b></span></div>'
            f'<div class="grid2"><div><div class="h2" style="margin-bottom:8px">🔴 공격 킬체인(6단계·시뮬레이션)</div>'
            f'<ul class="kc">{kc}</ul></div>'
            f'<div><div class="h2" style="margin-bottom:8px">🧠 탐지 지표</div><div class="charts">{figs}</div></div></div>'
            f'{pbh}<div class="chips">{mitre}{sparta}</div></div></div>')
    p.append('</section>')
    # 고지 + 푸터
    p.append('<section><div class="note">⚖️ 모든 "공격"은 합성 시뮬레이터/공개 데이터셋 내부에서만 수행되며, '
             '실제 RF 송신·실장비 공격은 없다(차폐환경 연구 전제). 지표는 합성/통제 데이터 기준 PoC이며 '
             '문헌값(GNSS 스푸핑 F1≈0.97, CAN IDS F1≈0.99)과 정합.</div></section>')
    p.append('<footer>결계(結界) · 팀 백공검(白空劍) · DAH 2026 · '
             '<a href="https://github.com/yulim4hyoung/DAH" target="_blank" rel="noopener">github.com/yulim4hyoung/DAH</a>'
             '</footer>')
    p.append('</main>')
    return "".join(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fragment", default=None, help="Artifact용 조각 파일 경로(head/body 래퍼 없이)")
    args = ap.parse_args()

    content = build_content()
    title = "결계(結界) — 백공검 방어 대시보드 (DAH 2026)"
    # 레포용 완결형 문서
    full = (f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{title}</title>{CSS}</head><body>{content}</body></html>')
    out = os.path.join(REPO_ROOT, "docs", "dashboard.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(full)
    print(f"docs/dashboard.html 생성 ({os.path.getsize(out)//1024} KB)")

    if args.fragment:
        # Artifact는 <head>/<body>를 자동 래핑하므로 title+style+content만
        frag = f"<title>{title}</title>{CSS}{content}"
        os.makedirs(os.path.dirname(args.fragment), exist_ok=True)
        open(args.fragment, "w", encoding="utf-8").write(frag)
        print(f"fragment 생성: {args.fragment} ({os.path.getsize(args.fragment)//1024} KB)")


if __name__ == "__main__":
    main()
