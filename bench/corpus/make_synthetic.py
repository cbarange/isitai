"""Build a labelled synthetic QA corpus for isitai. Standard library only, deterministic, no network.

Usage: python3 -I make_synthetic.py <out dir> [--small]

Writes a flat directory of files plus `expected.json`:

    { "<file name>": { "verdict": "...",        # expected verdict (ground truth, from the spec)
                       "generator": "...",      # optional, expected `generator`
                       "media": "...",          # optional, expected `media`
                       "category": "...",       # text-human, text-ai, text-path, png, xmp, hostile, perf
                       "human": true|false,     # true = content written by a human (criterion 1)
                       "note": "..." } }

Labels say what the file IS, not what the tool answers today. They are frozen before the
first run: a mismatch is a finding, never a reason to relabel.

Labels changed after the 2026-11-12 QA report, because a design decision changed the
correct answer (not because a case failed):
- `xmp_algorithmicMedia.*`: ai-signal -> no-signal. IPTC defines `algorithmicMedia` as media
  made by an algorithm without training data; it left the AI list of the spec.
- `ai_two_weak_*_markdown.txt`, `ai_two_weak_midbom_bold.txt`: ai-signal -> no-signal. The rule
  `text.markdown-residue` was removed (it matched 81 % of real Markdown files), so these
  files carry one weak signal only.
- `ai_utm_chatgpt.txt`, `ai_utm_openai.txt`: ai-signal -> no-signal. `text.utm-ai` is now weak:
  the tag describes a link, not the text.
- `tp_latin1.txt`, `tp_utf16le_bom.txt`: verdict kept (ai-signal), `media` added (text/plain).
  UTF-16 with a byte order mark and Windows-1252 text are now decoded, so the file must be
  reported as text.
Content changed, label kept: `perf_png_300k_parameters.png` now carries `Steps: 1` in each
chunk, because a `parameters` key without an A1111 field is no longer evidence.

`--small` skips every file above 1 MB (quick runs).

Nothing here comes from a real generator: PNG chunks, XMP packets and text artifacts are
written by hand after the public formats. Signed C2PA files come from `make_signed.py`.
"""
import json
import os
import random
import struct
import sys
import zlib

OUT = sys.argv[1]
SMALL = "--small" in sys.argv[2:]
os.makedirs(OUT, exist_ok=True)
EXPECTED = {}

# Constants mirrored from crates/isitai-core/src (xmp.rs, lib.rs, png.rs).
CHUNK = 4 * 1024 * 1024
OVERLAP = 256 * 1024
SNIFF_LEN = 8192
MAX_TEXT_BYTES = 16 * 1024 * 1024
MAX_TEXT_CHUNK = 16 * 1024 * 1024

A1111 = "Stable Diffusion WebUI (A1111/Forge)"


def add(name, data, verdict, category, human=False, generator=None, media=None, note=""):
    if isinstance(data, str):
        data = data.encode("utf-8")
    if SMALL and len(data) > 1_000_000:
        return
    assert name not in EXPECTED, name
    with open(os.path.join(OUT, name), "wb") as f:
        f.write(data)
    e = {"verdict": verdict, "category": category, "human": human}
    if generator:
        e["generator"] = generator
    if media:
        e["media"] = media
    if note:
        e["note"] = note
    EXPECTED[name] = e


# --------------------------------------------------------------------------- text

FR = (
    "Hier soir, nous avons pris le dernier train pour Lyon. Le wagon était presque vide, "
    "et la contrôleuse nous a laissé nous installer près de la fenêtre. Ma sœur lisait, "
    "moi je regardais défiler les champs gelés en pensant au repas de dimanche.\n\n"
    "À l'arrivée, il pleuvait. On a couru jusqu'au tramway, les valises cognant sur les pavés. "
    "Grand-mère nous attendait avec une soupe à l'oignon et des questions sur tout le monde.\n\n"
)
EN = (
    "We left the harbour a little after six. The tide was against us and the engine coughed "
    "twice before it settled, so Tom stayed aft with one hand on the cover, listening.\n\n"
    "By noon the fog had lifted. You could see the lighthouse and, behind it, the grey line "
    "of the cliffs where we used to pick blackberries. Nobody said much. It was that kind of day.\n\n"
)
NNBSP, NBSP, ZWSP, WJ, BOM, ZWJ = " ", " ", "​", "⁠", "﻿", "‍"

H = dict(category="text-human", human=True)

add("h_fr_prose.txt", FR * 3, "no-signal", **H)
add("h_en_prose.txt", EN * 3, "no-signal", **H)
add("h_fr_typography.txt",
    f"Il a dit{NNBSP}: «{NBSP}Tu viens{NNBSP}?{NBSP}» — et elle a répondu{NNBSP}: «{NBSP}Non{NNBSP}!{NBSP}»\n"
    f"Prix{NBSP}: 12{NBSP}000{NBSP}€ ; délai{NNBSP}: 3{NBSP}semaines ; voir p.{NBSP}42.\n",
    "no-signal", note="U+202F, U+00A0, guillemets, em dash", **H)
add("h_emoji_zwj.txt",
    f"Famille \U0001F468{ZWJ}\U0001F469{ZWJ}\U0001F467{ZWJ}\U0001F466 au parc, "
    f"\U0001F469{ZWJ}\U0001F4BB au bureau, \U0001F3F3️{ZWJ}\U0001F308 partout, "
    f"\U0001F9D1\U0001F3FD{ZWJ}\U0001F680 un jour. Thumbs \U0001F44D\U0001F3FF!\n",
    "no-signal", note="ZWJ emoji sequences", **H)
add("h_bom_leading.txt", BOM + FR, "no-signal", note="leading UTF-8 BOM (Windows Notepad)", **H)
add("h_bom_leading_crlf.txt", BOM + EN.replace("\n", "\r\n"), "no-signal", **H)
add("h_very_short_ok.txt", "ok", "no-signal", **H)
add("h_very_short_1char.txt", "a", "no-signal", **H)
add("h_one_emoji.txt", "\U0001F600", "no-signal", **H)

README_EN = """# tinycsv

A **small** CSV reader for people who do not want a dependency tree.

## Install

```bash
pip install tinycsv
```

## Usage

1. Open the file.
2. Call `tinycsv.read(path)`.

### Options

- **delimiter**: one character, default `,`
- **strict**: fail on ragged rows

## License

MIT
"""
README_FR = """# Recettes de la maison

Ce dépôt garde les **recettes de famille**, écrites à la main puis recopiées ici.

## Tarte aux pommes

- 4 pommes **reinettes**
- 150 g de beurre

### Cuisson

Four à 180 °C, 35 minutes. Ne **jamais** ouvrir avant 25 minutes.

## Soupe à l'oignon

Voir le carnet de Mamie, page 12.
"""
add("h_readme_en.md", README_EN, "no-signal", note="human Markdown: headings + bold, one weak rule only", **H)
add("h_readme_fr.md", README_FR, "no-signal", note="human Markdown, French", **H)

PY = '''#!/usr/bin/env python3
"""Merge keyword arguments from several sources."""

## Helpers ------------------------------------------------------------

def merge(*args, **kwargs):
    out = {}
    for a in args:
        out.update(**a)
    return dict(**out, **kwargs)


def power(x):
    return 2 ** x + x ** 2


if __name__ == "__main__":
    print(merge({"a": 1}, **{"b": 2}), power(3))
'''
add("h_code_python.py", PY, "no-signal", note="shebang, `## ` comment, **kwargs", **H)
add("h_code_python_noshebang.py", PY.split("\n", 1)[1], "no-signal", **H)
add("h_code_c.c",
    "/** Adds two ints. **/\n#include <stdio.h>\n#define CAT(a, b) a ## b\n"
    "int add(int a, int b) { return a + b; }\nint main(int argc, char **argv) { char **p = argv; return add(1, 2); }\n",
    "no-signal", **H)
add("h_code_rust.rs",
    "//! Tiny example.\nfn main() {\n    let v: Vec<u32> = (1..4).map(|x| x.pow(2)).collect();\n"
    "    println!(\"{v:?}\"); // prints [1, 4, 9]\n}\n", "no-signal", **H)
add("h_code_js.js",
    "// Returns the turn number.\nexport const turn = (n) => `turn${n}`;\n"
    "const opts = { ...defaults, ...user };\nconsole.log(turn(3), 2 ** 8);\n", "no-signal", **H)
add("h_code_shell.sh",
    "#!/bin/sh\n## Backup script\nset -eu\ntar czf \"backup-$(date +%F).tgz\" \"$HOME/docs\"\n", "no-signal", **H)
add("h_data.csv", "id;nom;ville\n1;Durand;Lyon\n2;Martin;Nantes\n3;O'Neil;Brest\n", "no-signal", **H)
add("h_data.json", json.dumps({"name": "tinycsv", "version": "1.2.0", "tags": ["csv", "parser"], "stars": 42}, indent=2),
    "no-signal", **H)
add("h_data.yaml", "## Site settings\ntitle: Mon blog\nlang: fr\nplugins:\n  - feed\n  - sitemap\n", "no-signal", **H)
add("h_page.html",
    "<!DOCTYPE html>\n<html lang=\"fr\"><head><meta charset=\"utf-8\"><title>Accueil</title></head>\n"
    "<body><h1>Bienvenue</h1><p>Ouvert du lundi au samedi.</p></body></html>\n", "no-signal", **H)
add("h_snippet.html", "<div class=\"card\"><p>Ouvert du <b>lundi</b> au samedi.</p></div>\n", "no-signal", **H)
add("h_long_prose_10mb.txt", (FR + EN) * (10 * 1024 * 1024 // len((FR + EN).encode()) + 1), "no-signal",
    note="about 10 MB of prose", **H)
add("h_long_markdown_10mb.md", (README_EN + README_FR) * (10 * 1024 * 1024 // len((README_EN + README_FR).encode()) + 1),
    "no-signal", note="about 10 MB of Markdown: one weak rule, many hits", **H)

# Human content that sits on a rule. Still human: expected no-signal.
add("h_zwsp_from_web.txt", f"Copié depuis une page web{ZWSP}: horaires d'ouverture{ZWSP} 9 h – 18 h.\n", "no-signal",
    note="ZWSP alone (web copy): one weak", **H)
add("h_notion_export_zwsp.md", README_FR.replace("Tarte aux pommes", f"Tarte aux{ZWSP} pommes"), "no-signal",
    note="human Markdown + one ZWSP left by an editor export: two weak rules", **H)
add("h_thai_markdown.md", f"## สวัสดี\n\nสวัสดี{ZWSP}ครับ{ZWSP}ทุกคน\n",
    "no-signal", note="Thai uses U+200B as a legitimate word break; with a heading: two weak rules", **H)
add("h_sanitizer_zwsp.py",
    f"def clean(s, **kwargs):\n    return strip(s.replace(\"{ZWSP}\", \"\"), **kwargs)\n", "no-signal",
    note="source code with a literal ZWSP and `**kwargs, ... **kwargs`: two weak rules", **H)
add("h_concat_bom.md", "## Notes A\nun" + BOM + "## Notes B\ndeux\n", "no-signal",
    note="two BOM-led files concatenated, first one without final newline: BOM mid-text + heading", **H)
add("h_article_ai_model_en.txt",
    "As an AI model grows, its training bill grows faster. Engineers at the lab told us that, "
    "as an AI language model gets deployed to millions of users, inference becomes the main cost.\n",
    "no-signal", note="journalism using the words of text.self-disclosure in another sense", **H)
add("h_article_ia_fr.txt",
    "En tant qu'intelligence artificielle générative, ChatGPT ne « comprend » pas ce qu'il écrit, "
    "rappelle la chercheuse. En tant qu'IA dite « de confiance », le système doit pourtant être audité.\n",
    "no-signal", note="French journalism, same words as text.self-disclosure", **H)
add("h_analytics_utm.csv",
    "source;visites\nutm_source=newsletter;1820\nutm_source=chatgpt.com;412\nutm_source=openai;37\n",
    "no-signal", note="marketing report listing traffic sources", **H)
add("h_shared_link.txt",
    "Salut, voilà le lien dont je te parlais pour les billets : "
    "https://www.example.com/billets?utm_source=chatgpt.com\nÀ samedi !\n",
    "no-signal", note="human message; only the URL came from an assistant. Debatable label, see report", **H)
add("h_js_strip_utm.js",
    "// Remove assistant tracking from pasted links.\n"
    "export const clean = (u) => u.replace(/[?&]utm_source=chatgpt\\.com/, '').replace('utm_source=openai', '');\n",
    "no-signal", note="code that mentions the tracking parameter", **H)
add("h_doc_quotes_oaicite.md",
    "# Detecting pasted answers\n\nChatGPT sometimes leaves `:contentReference[oaicite:0]{index=0}` in copied text.\n",
    "no-signal", note="documentation quoting the artifact (the isitai README does the same)", **H)
add("h_doc_quotes_tokens.txt",
    "Bug report: the export shows raw tokens such as turn0search0 and turn2view1 instead of links. "
    "The old model also said \"as an AI language model\" a lot; we filter that phrase now.\n",
    "no-signal", note="text that discusses the artifacts", **H)
add("h_doc_quotes_xmp.md",
    "Exemple de paquet XMP :\n\n```xml\n<x:xmpmeta xmlns:x=\"adobe:ns:meta/\"><rdf:Description "
    "Iptc4xmpExt:DigitalSourceType=\"http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia\"/></x:xmpmeta>\n```\n",
    "no-signal", note="Markdown doc quoting an XMP packet (text path)", **H)
add("h_doc_xmp_in_script.html",
    "<!DOCTYPE html>\n<html><body><h1>XMP writer demo</h1><script>\nconst TEMPLATE = `<x:xmpmeta xmlns:x=\"adobe:ns:meta/\">"
    "<rdf:Description Iptc4xmpExt:DigitalSourceType=\"http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia\"/>"
    "</x:xmpmeta>`;\n</script></body></html>\n",
    "no-signal", note="HTML page whose script holds an XMP template (binary path, XMP scan)", **H)

# AI positives: one file per rule alternative of rules/text.toml.
A = dict(category="text-ai", human=False)
P = "Paris est la capitale de la France"
add("ai_oaicite_ref.txt", f"{P} :contentReference[oaicite:0]{{index=0}}.\n", "ai-signal", **A)
add("ai_oaicite_brackets.txt", f"{P} 【oaicite:12】.\n", "ai-signal", **A)
for kind in ("search", "news", "view", "fetch", "file", "image"):
    add(f"ai_citeturn_{kind}.txt", f"{P} citeturn0{kind}3.\n", "ai-signal",
        note="`cite` glued to the token, as in pasted text", **A)
add("ai_citeturn_spaced.txt", f"{P} cite turn0search1 turn0news2.\n", "ai-signal", **A)
add("ai_citeturn_private_use.txt", f"{P} citeturn0search0turn1view0.\n", "ai-signal",
    note="private-use delimiters around the tokens", **A)
add("ai_utm_chatgpt.txt", "Source : https://example.org/article?utm_source=chatgpt.com\n", "no-signal",
    note="one weak only: the tag describes the link, not the text", **A)
add("ai_utm_openai.txt", "Source: https://example.org/article?id=3&utm_source=openai\n", "no-signal",
    note="one weak only", **A)
add("ai_self_en_language_model.txt", "As an AI language model, I cannot browse the internet.\n", "ai-signal", **A)
add("ai_self_en_model.txt", "I'm sorry, but as an AI model I do not have opinions.\n", "ai-signal", **A)
add("ai_self_en_knowledge_update.txt", "As of my last knowledge update, the record stood at 9.58 s.\n", "ai-signal", **A)
add("ai_self_en_knowledge_cutoff.txt", "As of my knowledge cutoff, no such law existed.\n", "ai-signal", **A)
add("ai_self_fr_modele.txt", "En tant que modèle de langage, je ne peux pas donner d'avis médical.\n", "ai-signal", **A)
add("ai_self_fr_ia_apostrophe.txt", "En tant qu'IA, je n'ai pas d'opinion personnelle.\n", "ai-signal", **A)
add("ai_self_fr_ia_typographic.txt", "En tant qu’IA, je n'ai pas d'opinion personnelle.\n", "ai-signal", **A)
add("ai_self_fr_intelligence.txt", "En tant qu'intelligence artificielle, je ne ressens rien.\n", "ai-signal", **A)
add("ai_self_fr_uppercase.txt", "EN TANT QUE MODÈLE DE LANGAGE, JE NE PEUX PAS.\n", "ai-signal",
    note="case-insensitive match on a non-ASCII letter", **A)
add("ai_two_weak_zwsp_markdown.txt", f"## Résumé\n\nVoici **les points clés**{ZWSP} du rapport.\n", "no-signal",
    note="zero-width + Markdown: Markdown is no longer a rule, one weak only", **A)
add("ai_two_weak_wj_markdown.txt", f"### Plan\n\nPremière{WJ} partie.\n", "no-signal",
    note="U+2060 + heading: one weak only", **A)
add("ai_two_weak_midbom_bold.txt", f"Voici **le plan**{BOM} détaillé.\n", "no-signal",
    note="BOM mid-text + bold: one weak only", **A)
add("ai_two_weak_zwsp_utm.txt", f"Voici le plan{ZWSP} : https://example.org/article?utm_source=chatgpt.com\n", "ai-signal",
    note="zero-width + utm-ai: two distinct weak rules", **A)
add("ai_one_weak_zwsp.txt", f"Voici le plan{ZWSP} détaillé.\n", "no-signal", note="one weak only: below the threshold", **A)
add("ai_one_weak_markdown.txt", "## Résumé\n\nVoici **les points clés** du rapport.\n", "no-signal", note="one weak only", **A)
add("ai_oaicite_end_of_10mb.txt", EN * (10 * 1024 * 1024 // len(EN.encode())) + f"{P} :contentReference[oaicite:3]{{index=3}}\n",
    "ai-signal", note="artifact at the end of a 10 MB text", **A)

# Same positive, different container: does the text path still run?
T = dict(category="text-path", human=False)
POS = f"{P} :contentReference[oaicite:0]{{index=0}}.\n"
add("tp_html_doctype.html", f"<!DOCTYPE html>\n<html><body><p>{POS}</p></body></html>\n", "ai-signal", **T)
add("tp_html_fragment.html", f"<p>{POS}</p>\n", "ai-signal", **T)
add("tp_xml_decl.xml", f"<?xml version=\"1.0\"?>\n<note>{POS}</note>\n", "ai-signal", **T)
add("tp_shebang.sh", f"#!/bin/sh\n# {POS}echo ok\n", "ai-signal", **T)
add("tp_starts_BM.txt", f"BMW a annoncé ses résultats. {POS}", "ai-signal", note="`BM` is the BMP magic", **T)
add("tp_starts_MZ.txt", f"MZ est le sigle du Mozambique. {POS}", "ai-signal", note="`MZ` is the EXE magic", **T)
add("tp_starts_ID3.txt", f"ID3 est un format d'étiquettes audio. {POS}", "ai-signal", note="`ID3` is the MP3 tag magic", **T)
add("tp_starts_pdf_magic.txt", f"%PDF est la signature des fichiers PDF. {POS}", "ai-signal", **T)
add("tp_starts_GIF8.txt", f"GIF89a est la version animée du format. {POS}", "ai-signal", **T)
add("tp_starts_rtf.rtf", "{\\rtf1\\ansi " + POS + "}", "ai-signal", **T)
add("tp_mentions_svg.md", f"Pour le logo, utilisez `<svg width=\"16\">`.\n\n{POS}", "ai-signal",
    note="`<svg` in the first 8 KB switches the file to image/svg+xml", **T)
add("tp_jsx_svg.jsx", f"export const Icon = () => <svg viewBox=\"0 0 1 1\"/>;\n// {POS}", "ai-signal", **T)
add("tp_latin1.txt", f"{POS}Très bien, à bientôt.\n".encode("latin-1"), "ai-signal", media="text/plain",
    note="ISO-8859-1 French text, decoded as Windows-1252", **T)
add("tp_utf16le_bom.txt", b"\xff\xfe" + POS.encode("utf-16-le"), "ai-signal", media="text/plain",
    note="UTF-16 LE with BOM (Windows)", **T)
add("tp_crlf.txt", POS.replace("\n", "\r\n") * 2, "ai-signal", **T)
add("tp_nul_bytes.txt", "abc\x00\x00" + POS, "ai-signal", note="text with NUL bytes", **T)
fill = "x" * 79 + "\n"
n_over = SNIFF_LEN + MAX_TEXT_BYTES
add("tp_over_text_limit.txt", fill * (n_over // 80 + 2) + POS, "ai-signal",
    note="artifact after the 16 MiB + 8192 text limit", **T)
body = fill * (n_over // 80 + 2)
body = body[: n_over - 1] + "é" + "\n" + FR  # 2-byte char straddles the read limit
add("h_over_text_limit_multibyte.txt", body, "no-signal", media="text/plain",
    note="valid UTF-8 human text; a 2-byte char sits exactly on the 16 MiB + 8192 cut", **H)
add("tp_text_just_under_limit.txt", (fill * (n_over // 80 + 2))[: n_over - len(POS.encode())] + POS, "ai-signal",
    note="artifact ends exactly at the text limit", **T)

# --------------------------------------------------------------------------- PNG


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


PNG_SIG = b"\x89PNG\r\n\x1a\n"
IHDR = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
IDAT = chunk(b"IDAT", zlib.compress(b"\x00\x80", 9))
IEND = chunk(b"IEND", b"")


def png(*extra, after_idat=()):
    return PNG_SIG + IHDR + b"".join(extra) + IDAT + b"".join(after_idat) + IEND


def text_chunk(key, value):
    return chunk(b"tEXt", key.encode("latin-1") + b"\0" + value.encode("latin-1"))


def ztxt_chunk(key, value):
    return chunk(b"zTXt", key.encode("latin-1") + b"\0\0" + zlib.compress(value.encode("latin-1"), 9))


def itxt_chunk(key, value, compressed=False):
    v = value.encode("utf-8") if isinstance(value, str) else value
    body = zlib.compress(v, 9) if compressed else v
    return chunk(b"iTXt", key.encode("latin-1") + b"\0" + (b"\1" if compressed else b"\0") + b"\0\0\0" + body)


COMFY_PROMPT = json.dumps({"3": {"class_type": "KSampler", "inputs": {"seed": 1, "steps": 20}},
                           "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "a red fox"}}})
COMFY_WORKFLOW = json.dumps({"last_node_id": 9, "nodes": [{"id": 3, "type": "KSampler"}], "version": 0.4})
A1111_PARAMS = ("a red fox in the snow\nNegative prompt: blurry\nSteps: 20, Sampler: Euler a, CFG scale: 7, "
                "Seed: 1, Size: 512x512, Model hash: 6ce0161689")
INVOKE = json.dumps({"app_version": "4.2.0", "generation_mode": "txt2img", "positive_prompt": "a red fox"})

G = dict(category="png", human=False)
add("png_minimal.png", png(), "no-signal", media="image/png", category="png", human=True)
add("png_parameters_text.png", png(text_chunk("parameters", A1111_PARAMS)), "ai-signal", generator=A1111, **G)
add("png_parameters_after_idat.png", png(after_idat=[text_chunk("parameters", A1111_PARAMS)]), "ai-signal", generator=A1111, **G)
add("png_parameters_ztxt.png", png(ztxt_chunk("parameters", A1111_PARAMS)), "ai-signal", generator=A1111, **G)
add("png_parameters_itxt.png", png(itxt_chunk("parameters", A1111_PARAMS)), "ai-signal", generator=A1111, **G)
add("png_prompt_comfy.png", png(text_chunk("prompt", COMFY_PROMPT)), "ai-signal", generator="ComfyUI", **G)
add("png_workflow_comfy.png", png(text_chunk("workflow", COMFY_WORKFLOW)), "ai-signal", generator="ComfyUI", **G)
add("png_prompt_workflow_comfy.png", png(text_chunk("prompt", COMFY_PROMPT), text_chunk("workflow", COMFY_WORKFLOW)),
    "ai-signal", generator="ComfyUI", **G)
add("png_invokeai_itxt.png", png(itxt_chunk("invokeai_metadata", INVOKE)), "ai-signal", generator="InvokeAI", **G)
add("png_invokeai_text.png", png(text_chunk("invokeai_metadata", INVOKE)), "ai-signal", generator="InvokeAI", **G)
add("png_software_novelai_text.png", png(text_chunk("Software", "NovelAI")), "ai-signal", generator="NovelAI", **G)
add("png_software_novelai_itxt.png", png(itxt_chunk("Software", "NovelAI")), "ai-signal", generator="NovelAI",
    note="same key and value, iTXt instead of tEXt", **G)
add("png_software_novelai_ztxt.png", png(ztxt_chunk("Software", "NovelAI")), "ai-signal", generator="NovelAI",
    note="same key and value, zTXt (compressed value)", **G)

HP = dict(category="png", human=True)
add("png_h_comment.png", png(text_chunk("Comment", "Vacances 2019, plage de Wimereux")), "no-signal", **HP)
add("png_h_software_gimp.png", png(text_chunk("Software", "GIMP 2.10.36")), "no-signal", **HP)
add("png_h_software_photoshop.png", png(text_chunk("Software", "Adobe Photoshop 25.0 (Macintosh)"),
                                        text_chunk("Creation Time", "2024-05-01T10:00:00")), "no-signal", **HP)
add("png_h_prompt_not_comfy.png", png(text_chunk("prompt", "Daily photo challenge #212: 'something blue'")), "no-signal",
    note="`prompt` key, content is not a ComfyUI graph", **HP)
add("png_h_prompt_empty.png", png(text_chunk("prompt", "")), "no-signal", note="empty `prompt` value", **HP)
add("png_h_parameters_camera.png", png(text_chunk("parameters", "ISO 100, f/2.8, 1/250 s, 35 mm")), "no-signal",
    note="`parameters` key written by a scanner/plot tool, no Stable Diffusion fields", **HP)
add("png_h_workflow_note.png", png(text_chunk("workflow", "RAW > Lightroom > export sRGB")), "no-signal",
    note="`workflow` key, plain note", **HP)
add("png_h_software_mentions_novelai.png", png(text_chunk("Software", "viewer 1.0 (not NovelAI)")), "no-signal",
    note="Software value merely contains the word", **HP)

# --------------------------------------------------------------------------- XMP

DST = "http://cv.iptc.org/newscodes/digitalsourcetype/"


def xmp(value, form="element", pad=0, uri=DST):
    if form == "element":
        inner = f"<rdf:Description rdf:about=\"\" xmlns:Iptc4xmpExt=\"http://iptc.org/std/Iptc4xmpExt/2008-02-29/\">" \
                f"<Iptc4xmpExt:DigitalSourceType>{uri}{value}</Iptc4xmpExt:DigitalSourceType></rdf:Description>"
    else:
        inner = f"<rdf:Description rdf:about=\"\" xmlns:Iptc4xmpExt=\"http://iptc.org/std/Iptc4xmpExt/2008-02-29/\" " \
                f"Iptc4xmpExt:DigitalSourceType=\"{uri}{value}\"/>"
    return ("<?xpacket begin=\"﻿\" id=\"W5M0MpCehiHzreSzNTczkc9d\"?>\n<x:xmpmeta xmlns:x=\"adobe:ns:meta/\">"
            "<rdf:RDF xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\">" + " " * pad + inner +
            "</rdf:RDF></x:xmpmeta>\n<?xpacket end=\"w\"?>").encode("utf-8")


def png_xmp(packet, **kw):
    return png(itxt_chunk("XML:com.adobe.xmp", packet, **kw))


# Minimal baseline JPEG, 1x1 grey: one 1-bit Huffman code per table, one MCU.
def seg(marker, data):
    return b"\xff" + bytes([marker]) + struct.pack(">H", len(data) + 2) + data


JPEG_HEAD = b"\xff\xd8" + seg(0xE0, b"JFIF\0\x01\x01\0\0\x01\0\x01\0\0")
JPEG_TAIL = (seg(0xDB, b"\0" + b"\x01" * 64) + seg(0xC0, b"\x08\0\x01\0\x01\x01\x01\x11\0") +
             seg(0xC4, b"\x00" + b"\x01" + b"\0" * 15 + b"\0") + seg(0xC4, b"\x10" + b"\x01" + b"\0" * 15 + b"\0") +
             seg(0xDA, b"\x01\x01\0\0\x3f\0") + b"\x3f" + b"\xff\xd9")


def jpeg(*segments):
    return JPEG_HEAD + b"".join(segments) + JPEG_TAIL


def jpeg_xmp(packet):
    return jpeg(seg(0xE1, b"http://ns.adobe.com/xap/1.0/\0" + packet))


# Minimal lossless WebP 1x1, wrapped in the extended (VP8X) layout so that it can carry XMP.
VP8L = b"\x2f\x00\x00\x00\x10\x07\x10\x11\x11\x88\x88\xfe\x07\x00"


def riff_chunk(fourcc, data):
    return fourcc + struct.pack("<I", len(data)) + data + (b"\0" if len(data) % 2 else b"")


def webp(packet=None):
    if packet is None:
        body = riff_chunk(b"VP8L", VP8L)
    else:
        body = riff_chunk(b"VP8X", bytes([0x04, 0, 0, 0, 0, 0, 0, 0, 0, 0])) + riff_chunk(b"VP8L", VP8L) + riff_chunk(b"XMP ", packet)
    return b"RIFF" + struct.pack("<I", len(body) + 4) + b"WEBP" + body


def box(kind, data):
    return struct.pack(">I", len(data) + 8) + kind + data


XMP_UUID = bytes.fromhex("BE7ACFCB97A942E89C71999491E3AFAC")
FTYP = box(b"ftyp", b"isom\0\0\x02\0isomiso2mp41")


def mp4(packet=None, mdat=b"\0" * 64):
    return FTYP + box(b"free", b"") + box(b"mdat", mdat) + (box(b"uuid", XMP_UUID + packet) if packet else b"")


def pdf(packet=None):
    objs = [b"<< /Type /Catalog /Pages 2 0 R" + (b" /Metadata 4 0 R" if packet else b"") + b" >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 10 10] >>"]
    if packet:
        objs.append(b"<< /Type /Metadata /Subtype /XML /Length %d >>\nstream\n" % len(packet) + packet + b"\nendstream")
    out, offs = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)


def svg(packet=None):
    meta = b"<metadata>" + packet.split(b"?>\n", 1)[1].rsplit(b"\n<?xpacket", 1)[0] + b"</metadata>" if packet else b""
    return b"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"1\" height=\"1\">" + meta + b"<rect width=\"1\" height=\"1\"/></svg>\n"


GIF = b"GIF89a\x01\0\x01\0\x80\0\0\0\0\0\xff\xff\xff,\0\0\0\0\x01\0\x01\0\0\x02\x02D\x01\0;"

X = dict(category="xmp", human=False)
add("jpeg_minimal.jpg", jpeg(), "no-signal", media="image/jpeg", category="xmp", human=True)
add("webp_minimal.webp", webp(), "no-signal", media="image/webp", category="xmp", human=True)
add("gif_minimal.gif", GIF, "no-signal", media="image/gif", category="xmp", human=True)
add("mp4_minimal.mp4", mp4(), "no-signal", category="xmp", human=True, note="ftyp+free+mdat only, not playable")
add("pdf_minimal.pdf", pdf(), "no-signal", media="application/pdf", category="xmp", human=True)
add("svg_minimal.svg", svg(), "no-signal", media="image/svg+xml", category="xmp", human=True)

DST_CASES = [
    ("trainedAlgorithmicMedia", "ai-signal", False, "IPTC: AI"),
    ("compositeWithTrainedAlgorithmicMedia", "ai-signal", False, "IPTC: AI composite"),
    ("algorithmicMedia", "no-signal", False, "IPTC: made by an algorithm without training data; not in the AI list"),
    ("digitalCapture", "no-signal", True, "unsigned capture claim"),
    ("computationalCapture", "no-signal", True, "unsigned capture claim"),
    ("digitalArt", "no-signal", True, "neutral (retired IPTC value)"),
    ("digitalCreation", "no-signal", True, "neutral: made by a human with software"),
    ("humanEdits", "no-signal", True, "neutral"),
    ("composite", "no-signal", True, "neutral"),
    ("screenCapture", "no-signal", True, "neutral"),
    ("someFutureValue", "no-signal", True, "unknown value"),
]
for value, verdict, human, note in DST_CASES:
    for fmt, make in (("jpg", jpeg_xmp), ("png", png_xmp), ("webp", webp)):
        add(f"xmp_{value}.{fmt}", make(xmp(value)), verdict, category="xmp", human=human, note=note)
AI = "trainedAlgorithmicMedia"
add("xmp_ai_attribute_form.jpg", jpeg_xmp(xmp(AI, form="attr")), "ai-signal", note="RDF attribute form", **X)
add("xmp_ai_https_uri.jpg", jpeg_xmp(xmp(AI, uri="https://cv.iptc.org/newscodes/digitalsourcetype/")), "ai-signal", **X)
add("xmp_ai_mp4_uuid.mp4", mp4(xmp(AI)), "ai-signal", **X)
add("xmp_ai_pdf_metadata.pdf", pdf(xmp(AI)), "ai-signal", **X)
add("xmp_ai_svg_metadata.svg", svg(xmp(AI)), "ai-signal", **X)
add("xmp_ai_sidecar.xmp", xmp(AI), "ai-signal", note="standalone XMP sidecar file", **X)
add("xmp_ai_png_itxt_compressed.png", png_xmp(xmp(AI), compressed=True), "ai-signal",
    note="iTXt with the compression flag: allowed by PNG, packet not visible in clear", **X)
add("xmp_ai_utf16.xmp", b"\xff\xfe" + xmp(AI).decode("utf-8").encode("utf-16-le"), "ai-signal",
    note="UTF-16 LE packet, allowed by the XMP spec outside JPEG/PNG", **X)
add("xmp_ai_and_capture.jpg", jpeg(seg(0xE1, b"http://ns.adobe.com/xap/1.0/\0" + xmp(AI)),
                                    seg(0xE1, b"http://ns.adobe.com/xap/1.0/\0" + xmp("digitalCapture"))),
    "inconsistent", note="two packets that contradict each other", **X)
add("xmp_capture_plus_png_parameters.png", png(itxt_chunk("XML:com.adobe.xmp", xmp("digitalCapture")),
                                               text_chunk("parameters", A1111_PARAMS)),
    "inconsistent", generator=A1111, note="XMP capture claim + A1111 chunk", **X)
add("xmp_uri_outside_packet.jpg", jpeg(seg(0xFE, (DST + AI).encode())), "no-signal", category="xmp", human=True,
    note="the IPTC URI in a JPEG comment, no XMP packet")
add("xmp_ai_bare_value.jpg", jpeg_xmp(xmp(AI, uri="")), "no-signal", category="xmp", human=False,
    note="value without the IPTC URI: non-conforming, not counted")
add("xmp_ai_repeated_2000.png", png(*[itxt_chunk("XML:com.adobe.xmp", xmp(AI)) for _ in range(2000)]), "ai-signal",
    note="2000 identical packets", **X)
add("xmp_nested_open_50000.png",
    png(itxt_chunk("XML:com.adobe.xmp", b"<x:xmpmeta>" * 50000 + xmp(AI) + b"</x:xmpmeta>" * 50000)), "ai-signal",
    note="50 000 nested x:xmpmeta elements around one AI packet", **X)
add("xmp_unclosed_100000.png", png(itxt_chunk("XML:com.adobe.xmp", (b"<x:xmpmeta " + (DST + AI).encode() + b" ") * 100000)),
    "no-signal", category="hostile", human=False, note="100 000 opening tags, never closed")


def png_with_packet_at(offset, packet, total=None):
    """PNG whose XMP packet starts at byte `offset` (padding in an ancillary private chunk)."""
    head = PNG_SIG + IHDR
    itxt_prefix = 8 + len(b"XML:com.adobe.xmp\0\0\0\0\0")
    pad = offset - len(head) - 12 - itxt_prefix
    assert pad >= 0
    out = head + chunk(b"juNk", b"." * pad) + itxt_chunk("XML:com.adobe.xmp", packet)
    assert out.find(b"<?xpacket") == offset, (out.find(b"<?xpacket"), offset)
    tail = IDAT + IEND
    if total is not None:
        extra = total - len(out) - len(tail) - 12
        assert extra >= 0
        out += chunk(b"juNk", b"." * extra)
    out += tail
    assert total is None or len(out) == total
    return out


pk = xmp(AI)
start_in_packet = pk.find(b"<x:xmpmeta")
for label, off in (("chunk_minus_20", CHUNK - 20), ("chunk_minus_1", CHUNK - 1), ("chunk_exact", CHUNK),
                   ("chunk_plus_1", CHUNK + 1), ("2chunk_minus_overlap", 2 * CHUNK - OVERLAP - 10),
                   ("2chunk_minus_100", 2 * CHUNK - 100), ("9mb", 9 * 1024 * 1024)):
    add(f"xmp_at_{label}.png", png_with_packet_at(off - start_in_packet, pk), "ai-signal",
        note=f"`<x:xmpmeta` starts at byte {off}", **X)
for label, total in (("size_chunk", CHUNK), ("size_chunk_plus_1", CHUNK + 1), ("size_2chunk", 2 * CHUNK)):
    add(f"xmp_end_{label}.png", png_with_packet_at(total - len(pk) - 60, pk, total=total), "ai-signal",
        note=f"file size exactly {total}, packet at the end", **X)
big = xmp(AI, pad=OVERLAP + 40_000)  # opening tag and value are more than OVERLAP apart
# Opening tag just before the tail kept from window 2, value just after the 8 MiB boundary.
add("xmp_packet_300k_straddles_chunk.png", png_with_packet_at(2 * CHUNK - OVERLAP - 1000, big), "ai-signal",
    note="packet larger than the 256 KiB overlap: opens before (8 MiB - 256 KiB), value after 8 MiB", **X)
add("xmp_packet_300k_inside_chunk.png", png_with_packet_at(1000, big), "ai-signal",
    note="same large packet, fully inside the first window", **X)
add("xmp_ai_mp4_after_9mb.mp4", mp4(pk, mdat=b"\0" * (9 * 1024 * 1024)), "ai-signal", **X)
add("xmp_ai_jpeg_after_9mb.jpg", jpeg(*([seg(0xFE, b"." * 65533)] * 138), seg(0xE1, b"http://ns.adobe.com/xap/1.0/\0" + pk)),
    "ai-signal", note="XMP APP1 after 9 MB of COM segments", **X)

# --------------------------------------------------------------------------- hostile and odd

Z = dict(category="hostile", human=False)
rnd = random.Random(20261112)
add("odd_empty.bin", b"", "no-signal", **Z)
add("odd_empty.png", b"", "no-signal", note="empty file with an image extension", **Z)
add("odd_1byte_nul.bin", b"\0", "no-signal", **Z)
add("odd_1byte_ff.bin", b"\xff", "no-signal", **Z)
add("odd_random_64k.bin", rnd.randbytes(65536), "no-signal", **Z)
add("odd_random_1mb.bin", rnd.randbytes(1 << 20), "no-signal", **Z)
add("odd_zeros_10mb.bin", b"\0" * (10 << 20), "no-signal", note="10 MB of NUL bytes (valid UTF-8)", **Z)
add("odd_png_named.jpg", png(), "no-signal", note="PNG content, .jpg name", **Z)
add("odd_jpeg_named.txt", jpeg(), "no-signal", note="JPEG content, .txt name", **Z)
add("odd_text_named.png", FR, "no-signal", note="French text, .png name", category="hostile", human=True)
add("odd_ai_png_named.txt", png(text_chunk("parameters", A1111_PARAMS)), "ai-signal", generator=A1111,
    note="A1111 PNG renamed .txt", **Z)
add("odd_ai_text_named.jpg", POS, "ai-signal", note="pasted text renamed .jpg", **Z)

full = png(text_chunk("parameters", A1111_PARAMS))
add("trunc_png_signature_only.png", PNG_SIG, "no-signal", **Z)
add("trunc_png_mid_ihdr.png", (PNG_SIG + IHDR)[:20], "no-signal", **Z)
add("trunc_png_mid_text_value.png", full[: full.find(b"Negative")], "no-signal",
    note="cut inside the value of the `parameters` chunk", **Z)
add("trunc_png_no_iend.png", full[: -len(IEND)], "ai-signal", generator=A1111, note="complete chunk, IEND missing", **Z)
jx = jpeg_xmp(xmp(AI))
add("trunc_jpeg_soi_only.jpg", b"\xff\xd8", "no-signal", **Z)
add("trunc_jpeg_mid_app1.jpg", jx[: jx.find(b"<rdf:RDF")], "no-signal", **Z)
add("trunc_jpeg_no_eoi.jpg", jx[:-2], "ai-signal", note="complete XMP, EOI missing", **Z)
add("trunc_mp4_mid_ftyp.mp4", FTYP[:12], "no-signal", **Z)
add("trunc_mp4_mdat_short.mp4", FTYP + struct.pack(">I", 1 << 20) + b"mdat" + b"\0" * 16, "no-signal", **Z)
add("trunc_webp_riff_only.webp", b"RIFF\x10\0\0\0WEBP", "no-signal", **Z)
add("trunc_gif_header.gif", GIF[:10], "no-signal", **Z)
add("trunc_pdf_header.pdf", b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog", "no-signal", **Z)


def raw_chunk(kind, declared, data):
    return struct.pack(">I", declared) + kind + data


for label, n in (("at_cap", MAX_TEXT_CHUNK), ("cap_plus_1", MAX_TEXT_CHUNK + 1), ("2g", 0x7FFFFFFF), ("4g", 0xFFFFFFFF)):
    add(f"len_png_text_{label}.png", PNG_SIG + IHDR + raw_chunk(b"tEXt", n, b"parameters\0x") + IDAT + IEND, "no-signal",
        note=f"tEXt chunk declares {n} bytes, file holds 12", **Z)
add("len_png_text_16m_x40.png", PNG_SIG + IHDR + raw_chunk(b"tEXt", MAX_TEXT_CHUNK, b"k\0v") * 40, "no-signal",
    note="40 text chunks each declaring 16 MiB", **Z)
add("len_png_cabx_4g.png", PNG_SIG + IHDR + raw_chunk(b"caBX", 0xFFFFFFF0, b"\0\0\0\x20jumb\0\0\0\x18jumdc2pa") + IDAT + IEND,
    "no-signal", note="C2PA chunk declares 4 GiB", **Z)
add("len_png_idat_4g.png", PNG_SIG + IHDR + raw_chunk(b"IDAT", 0xFFFFFFFF, b"\0" * 8), "no-signal", **Z)
add("len_mp4_box_4g.mp4", FTYP + struct.pack(">I", 0xFFFFFFFF) + b"moov" + b"\0" * 16, "no-signal", **Z)
add("len_mp4_largesize.mp4", FTYP + struct.pack(">I", 1) + b"moov" + struct.pack(">Q", 0x7FFFFFFFFFFFFFFF) + b"\0" * 16,
    "no-signal", note="64-bit box size of 8 EiB", **Z)
add("len_mp4_uuid_c2pa_4g.mp4",
    FTYP + struct.pack(">I", 0xFFFFFFF0) + b"uuid" + bytes.fromhex("d8fec3d61b0e483c92975828877ec481") + b"\0\0\0\0manifest\0" + b"\0" * 32,
    "no-signal", note="C2PA uuid box declares 4 GiB", **Z)
add("len_mp4_size_zero_boxes.mp4", FTYP + (struct.pack(">I", 8) + b"free") * 100000, "no-signal", note="100 000 empty boxes", **Z)
depth = 100000
nested = b"".join(struct.pack(">I", 8 * (depth - i)) + b"moov" for i in range(depth))
add("len_mp4_nested_moov_100000.mp4", FTYP + nested, "no-signal", note="moov nested 100 000 deep", **Z)
add("len_riff_wav_4g.wav", b"RIFF\xff\xff\xff\xffWAVEfmt \xff\xff\xff\xff" + b"\0" * 16, "no-signal", **Z)
add("len_riff_webp_4g.webp", b"RIFF\xff\xff\xff\xffWEBPVP8X\xff\xff\xff\xff" + b"\0" * 16, "no-signal", **Z)
add("len_jpeg_app11_short.jpg", b"\xff\xd8" + b"\xff\xeb\xff\xffJP\0\x01\0\0\0\x01\xff\xff\xff\xffjumb" + b"\0" * 16, "no-signal",
    note="APP11 JUMBF segment declares 65535 bytes and a 4 GiB box, then ends", **Z)
add("len_jpeg_app11_x5000.jpg", b"\xff\xd8" + (seg(0xEB, b"JP\0\x01\0\0\0\x01\0\0\x04\0jumb" + b"\0" * 8)) * 5000 + JPEG_TAIL[2:],
    "no-signal", note="5000 bogus JUMBF segments", **Z)
add("len_tiff_ifd_ffff.tif", b"II*\0\x08\0\0\0\xff\xff" + b"\x01\x01\x04\0\xff\xff\xff\x7f\xff\xff\xff\x7f" * 4, "no-signal",
    note="IFD declares 65535 entries with 2 GiB counts", **Z)
add("len_gif_ext_loop.gif", GIF[:13] + b"\x21\xff\x0bXMP DataXMP" + b"\xff" * 300, "no-signal", **Z)
add("len_pdf_length_huge.pdf", b"%PDF-1.7\n1 0 obj\n<< /Length 99999999999 >>\nstream\nabc\nendstream\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n",
    "no-signal", **Z)
add("len_mp3_id3_huge.mp3", b"ID3\x03\0\0\x7f\x7f\x7f\x7f" + b"TSSE\x7f\xff\xff\xff\0\0" + b"\0" * 16, "no-signal", **Z)

PERF = dict(category="perf", human=False)
add("perf_png_1m_tiny_chunks.png", PNG_SIG + IHDR + chunk(b"juNk", b"") * 1_000_000 + IDAT + IEND, "no-signal",
    note="one million empty ancillary chunks (12 MB)", **PERF)
add("perf_png_300k_parameters.png", PNG_SIG + IHDR + text_chunk("parameters", "Steps: 1") * 300_000 + IDAT + IEND, "ai-signal",
    generator=A1111, note="300 000 `parameters` chunks (7 MB)", **PERF)
add("perf_text_bold_openers_10mb.txt", "**ab" * (10 * 1024 * 1024 // 4), "no-signal", note="10 MB of `**ab`", **PERF)
add("perf_text_zwsp_10mb.txt", (ZWSP * 1000 + "\n") * (10 * 1024 * 1024 // 3001), "no-signal", note="10 MB of U+200B", **PERF)
add("perf_text_one_line_10mb.txt", "a" * (10 * 1024 * 1024), "no-signal", note="10 MB, single line", **PERF)
add("perf_text_as_an_ai_prefix_10mb.txt", "as an AI " * (10 * 1024 * 1024 // 9), "no-signal",
    note="10 MB of a rule prefix that never completes", **PERF)

with open(os.path.join(OUT, "expected.json"), "w", encoding="utf-8") as f:
    json.dump(EXPECTED, f, indent=1, sort_keys=True, ensure_ascii=False)

by_cat = {}
for e in EXPECTED.values():
    by_cat[e["category"]] = by_cat.get(e["category"], 0) + 1
print(f"{len(EXPECTED)} files in {OUT}: " + ", ".join(f"{k}={v}" for k, v in sorted(by_cat.items())))
