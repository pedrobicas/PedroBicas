#!/usr/bin/env python3
"""Gera os SVGs do README do perfil: cabeçalho e card do portfólio, nos temas claro e escuro.

Uso (na raiz do repositório):
    pip install fonttools brotli
    python ferramentas/gerar_svgs.py

Para mudar os textos, edite CABECALHO e PORTFOLIO abaixo e rode de novo.
As fontes (Anybody e Fira Code, licença OFL) ficam em ferramentas/fonts e são
embutidas em cada SVG só com os caracteres usados, então o resultado não depende
das fontes instaladas em quem visita o perfil.
"""

from __future__ import annotations

import base64
import io
import pathlib
from dataclasses import dataclass, field
from functools import lru_cache
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

RAIZ = pathlib.Path(__file__).resolve().parent.parent
FONTES = RAIZ / "ferramentas" / "fonts"
SAIDA = RAIZ / "assets"

# Mesma paleta do pedrobicas.com.
TEMAS = {
    "dark": {
        "fundo": "#050913",
        "card": "#0A0F1C",
        "borda": "#1E2B47",
        "linha": "#18233D",
        "tinta": "#E6F1FF",
        "texto": "#B4C2E0",
        "mudo": "#7A8BBD",
        "sinal": "#3D8BFF",
    },
    "light": {
        "fundo": "#F5F8FF",
        "card": "#FFFFFF",
        "borda": "#D0D7DE",
        "linha": "#E3E9F4",
        "tinta": "#0B1222",
        "texto": "#36445F",
        "mudo": "#5B6A88",
        "sinal": "#1C57AF",
    },
}

CABECALHO = {
    "nome": "PEDRO BICAS",
    "papel": "Desenvolvedor full-stack",
    "site": "pedrobicas.com",
    "local": "São Paulo · Brasil",
    "stack": "Java · Spring Boot · Angular · React · TypeScript",
}

PORTFOLIO = {
    "rotulo": "portfólio",
    "titulo": "pedrobicas.com",
    "descricao": "Cada projeto com o problema, as decisões técnicas e como avaliar, além da trajetória e do currículo.",
    "acao": "abrir o portfólio",
    # O que tem no site: (nome, detalhe). Atualize a contagem quando entrar projeto novo.
    "secoes": [
        ("Projetos", "7 projetos"),
        ("Trajetória", "SENAI · FIAP · InCor"),
        ("Stack", "onde cada uma é usada"),
        ("Currículo", "pronto para PDF"),
    ],
}


# ---------------------------------------------------------------- fontes


@dataclass(frozen=True)
class Fonte:
    familia: str  # nome usado dentro do SVG
    arquivo: str
    eixos: tuple = ()


DISPLAY = Fonte("PB Display", "Anybody-variable-latin.woff2", (("wdth", 96), ("wght", 800)))
TITULO = Fonte("PB Titulo", "Anybody-variable-latin.woff2", (("wdth", 112), ("wght", 780)))
TEXTO = Fonte("PB Texto", "Anybody-variable-latin.woff2", (("wdth", 100), ("wght", 420)))
TEXTO_MEDIO = Fonte("PB Texto Medio", "Anybody-variable-latin.woff2", (("wdth", 100), ("wght", 560)))
MONO = Fonte("PB Mono", "FiraCode-400-latin.woff2")


@lru_cache
def ttf(fonte: Fonte) -> bytes:
    """TTF estático da fonte (instância do eixo variável, quando houver)."""
    font = TTFont(FONTES / fonte.arquivo)
    if fonte.eixos:
        font = instancer.instantiateVariableFont(font, dict(fonte.eixos))
    font.flavor = None
    buffer = io.BytesIO()
    font.save(buffer)
    return buffer.getvalue()


@lru_cache
def metricas(fonte: Fonte):
    font = TTFont(io.BytesIO(ttf(fonte)))
    return font.getBestCmap(), font["hmtx"], font["head"].unitsPerEm


def largura(fonte: Fonte, texto: str, tamanho: float, espacamento: float = 0) -> float:
    cmap, hmtx, upm = metricas(fonte)
    avancos = sum(hmtx[cmap.get(ord(c), ".notdef")][0] for c in texto)
    return avancos * tamanho / upm + espacamento * max(len(texto) - 1, 0)


def quebrar(fonte: Fonte, texto: str, tamanho: float, maximo: float) -> list[str]:
    linhas, atual = [], ""
    for palavra in texto.split(' '):
        tentativa = f"{atual} {palavra}".strip()
        if largura(fonte, tentativa, tamanho) <= maximo:
            atual = tentativa
        else:
            linhas.append(atual)
            atual = palavra
    linhas.append(atual)
    return linhas


def woff2_base64(fonte: Fonte, caracteres: str) -> str:
    font = TTFont(io.BytesIO(ttf(fonte)))
    opcoes = subset.Options()
    opcoes.flavor = "woff2"
    opcoes.layout_features = ["kern"]
    opcoes.name_IDs = []
    opcoes.notdef_outline = True
    subsetter = subset.Subsetter(opcoes)
    subsetter.populate(text=caracteres + " ")
    subsetter.subset(font)
    buffer = io.BytesIO()
    font.save(buffer)
    return base64.b64encode(buffer.getvalue()).decode()


# ---------------------------------------------------------------- SVG


@dataclass
class Svg:
    largura: int
    altura: int
    titulo: str
    corpo: list[str] = field(default_factory=list)
    usados: dict = field(default_factory=dict)
    css_extra: str = ""

    def texto(self, x, y, conteudo, fonte: Fonte, tamanho, cor, ancora="start", espacamento=0, extra=""):
        self.usados.setdefault(fonte, set()).update(conteudo)
        attrs = f'x="{x:.1f}" y="{y:.1f}" font-family="{fonte.familia}" font-size="{tamanho}" fill="{cor}"'
        if ancora != "start":
            attrs += f' text-anchor="{ancora}"'
        if espacamento:
            attrs += f' letter-spacing="{espacamento}"'
        self.corpo.append(f"<text {attrs}{extra}>{escape(conteudo)}</text>")

    def add(self, elemento: str):
        self.corpo.append(elemento)

    def render(self) -> str:
        faces = "".join(
            f'@font-face{{font-family:"{fonte.familia}";src:url(data:font/woff2;base64,{woff2_base64(fonte, "".join(sorted(chars)))}) format("woff2")}}'
            for fonte, chars in self.usados.items()
        )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.largura}" height="{self.altura}" '
            f'viewBox="0 0 {self.largura} {self.altura}" role="img" aria-label="{escape(self.titulo)}">'
            f"<title>{escape(self.titulo)}</title>"
            f"<style>{faces}text{{font-kerning:normal}}{self.css_extra}</style>"
            + "".join(self.corpo)
            + "</svg>\n"
        )


def bits(texto: str) -> str:
    return "".join(f"{ord(c):08b}" for c in texto)


def sinal_pb(x0: float, x1: float, largura_bits: float, alto: float, baixo: float) -> str:
    """Traço quadrado com "PB" em binário (o mesmo desenho do favicon do site)."""
    sequencia = bits("PB")
    passo = largura_bits / len(sequencia)
    nivel, x = baixo, x0
    d = f"M{x0} {baixo}"
    for bit in sequencia:
        alvo = alto if bit == "1" else baixo
        if alvo != nivel:
            d += f"V{alvo}"
            nivel = alvo
        x += passo
        d += f"H{x:.1f}"
    if nivel != baixo:
        d += f"V{baixo}"
    return d + f"H{x1}"


ANIMACAO = (
    ".sinal{stroke-dasharray:1600;animation:desenha 2.2s cubic-bezier(.22,1,.36,1) .25s both}"
    "@keyframes desenha{from{stroke-dashoffset:1600}to{stroke-dashoffset:0}}"
    ".ponto{animation:acende .6s ease 1.9s both}@keyframes acende{from{opacity:0}to{opacity:1}}"
    "@media (prefers-reduced-motion:reduce){.sinal,.ponto{animation:none}}"
)


def rotulo_bits() -> str:
    sequencia = bits("PB")
    return " ".join(sequencia[i : i + 8] for i in range(0, len(sequencia), 8))


def cabecalho(tema: str) -> str:
    """Versão larga, para telas a partir de 769 px."""
    c = TEMAS[tema]
    w, h, m = 1200, 360, 64
    svg = Svg(w, h, f"{CABECALHO['nome'].title()}, {CABECALHO['papel'].lower()} em São Paulo")
    svg.css_extra = ANIMACAO
    svg.add(f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="20" fill="{c["fundo"]}" stroke="{c["borda"]}"/>')

    svg.texto(m, 74, CABECALHO["site"], MONO, 19, c["sinal"])
    svg.texto(w - m, 74, CABECALHO["local"], MONO, 19, c["mudo"], ancora="end")
    svg.add(f'<path d="M{m} 102H{w - m}" stroke="{c["linha"]}" stroke-width="1"/>')

    tamanho = 112
    svg.texto(m - 4, 214, CABECALHO["nome"], DISPLAY, tamanho, c["tinta"], espacamento=-1)

    alto, baixo, fim = 240, 258, w - m
    d = sinal_pb(m, fim, largura(DISPLAY, CABECALHO["nome"], tamanho, -1), alto, baixo)
    svg.add(f'<path class="sinal" d="{d}" fill="none" stroke="{c["sinal"]}" stroke-width="2.5"/>')
    svg.add(f'<circle class="ponto" cx="{fim}" cy="{baixo}" r="5" fill="{c["sinal"]}"/>')
    svg.texto(fim - 18, baixo - 12, rotulo_bits(), MONO, 13, c["mudo"], ancora="end")

    svg.texto(m, 312, CABECALHO["papel"], TEXTO_MEDIO, 32, c["tinta"])
    svg.texto(w - m, 310, CABECALHO["stack"], MONO, 19, c["mudo"], ancora="end")
    return svg.render()


def cabecalho_celular(tema: str) -> str:
    """Versão estreita, com texto maior, para telas de até 768 px."""
    c = TEMAS[tema]
    w, h, m = 720, 600, 48
    svg = Svg(w, h, f"{CABECALHO['nome'].title()}, {CABECALHO['papel'].lower()} em São Paulo")
    svg.css_extra = ANIMACAO
    svg.add(f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="24" fill="{c["fundo"]}" stroke="{c["borda"]}"/>')

    svg.texto(m, 78, CABECALHO["site"], MONO, 26, c["sinal"])
    svg.texto(w - m, 78, "São Paulo", MONO, 26, c["mudo"], ancora="end")
    svg.add(f'<path d="M{m} 110H{w - m}" stroke="{c["linha"]}" stroke-width="1.5"/>')

    tamanho = 132
    primeiro, segundo = CABECALHO["nome"].split(" ", 1)
    svg.texto(m - 5, 238, primeiro, DISPLAY, tamanho, c["tinta"], espacamento=-1)
    svg.texto(m - 5, 356, segundo, DISPLAY, tamanho, c["tinta"], espacamento=-1)

    alto, baixo, fim = 388, 410, w - m
    d = sinal_pb(m, fim, w - 2 * m - 40, alto, baixo)
    svg.add(f'<path class="sinal" d="{d}" fill="none" stroke="{c["sinal"]}" stroke-width="3.5"/>')
    svg.add(f'<circle class="ponto" cx="{fim}" cy="{baixo}" r="7" fill="{c["sinal"]}"/>')

    svg.texto(m, 480, CABECALHO["papel"], TEXTO_MEDIO, 44, c["tinta"])
    partes = CABECALHO["stack"].split(" · ")
    meio = (len(partes) + 1) // 2
    svg.texto(m, 530, " · ".join(partes[:meio]), MONO, 25, c["mudo"])
    svg.texto(m, 566, " · ".join(partes[meio:]), MONO, 25, c["mudo"])
    return svg.render()


def seta(x: float, y: float, cor: str, tamanho: float = 10) -> str:
    t = tamanho
    return (
        f'<path d="M{x} {y}L{x + t} {y - t}M{x + t * 0.25:.1f} {y - t}H{x + t}V{y - t * 0.75:.1f}" '
        f'fill="none" stroke="{cor}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def portfolio(tema: str) -> str:
    """Card largo que leva ao site, com o que há nele à direita."""
    c = TEMAS[tema]
    w, h, m = 1200, 300, 64
    svg = Svg(w, h, f"Portfólio em {PORTFOLIO['titulo']}: {PORTFOLIO['descricao']}")
    svg.add(f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="20" fill="{c["card"]}" stroke="{c["borda"]}"/>')

    coluna = 700
    svg.texto(m, 78, PORTFOLIO["rotulo"], MONO, 19, c["sinal"])
    tamanho = 62
    svg.texto(m, 156, PORTFOLIO["titulo"], TITULO, tamanho, c["tinta"], espacamento=-0.6)
    x_seta = m + largura(TITULO, PORTFOLIO["titulo"], tamanho, -0.6) + 18
    svg.add(seta(x_seta, 146, c["sinal"], 22).replace('stroke-width="2"', 'stroke-width="3.5"'))

    linhas = quebrar(TEXTO, PORTFOLIO["descricao"], 23, coluna - m - 40)
    if len(linhas) > 2:
        raise SystemExit(f"Descrição do portfólio longa demais: {linhas}")
    for i, linha in enumerate(linhas):
        svg.texto(m, 206 + i * 32, linha, TEXTO, 23, c["texto"])

    # Índice do site, no mesmo estilo das seções do portfólio.
    x0, x1, topo, passo = 760, w - m, 56, 48
    for i, (nome, detalhe) in enumerate(PORTFOLIO["secoes"]):
        y = topo + i * passo
        svg.add(f'<path d="M{x0} {y}H{x1}" stroke="{c["linha"]}" stroke-width="1"/>')
        svg.texto(x0, y + 32, f"{i + 1:02d}", MONO, 15, c["sinal"] if i == 0 else c["mudo"])
        svg.texto(x0 + 40, y + 33, nome, TEXTO_MEDIO, 22, c["tinta"])
        svg.texto(x1, y + 32, detalhe, MONO, 15, c["mudo"], ancora="end")
        if 40 + largura(TEXTO_MEDIO, nome, 22) + 24 + largura(MONO, detalhe, 15) > x1 - x0:
            raise SystemExit(f"Seção longa demais no card do portfólio: {nome}")
    y = topo + len(PORTFOLIO["secoes"]) * passo
    svg.add(f'<path d="M{x0} {y}H{x1}" stroke="{c["linha"]}" stroke-width="1"/>')
    return svg.render()


def portfolio_celular(tema: str) -> str:
    """Versão estreita para telas de até 768 px: sem o índice, com texto maior."""
    c = TEMAS[tema]
    w, h, m = 720, 440, 48
    svg = Svg(w, h, f"Portfólio em {PORTFOLIO['titulo']}: {PORTFOLIO['descricao']}")
    svg.add(f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="24" fill="{c["card"]}" stroke="{c["borda"]}"/>')

    svg.texto(m, 82, PORTFOLIO["rotulo"], MONO, 26, c["sinal"])
    tamanho = min(76, 76 * (w - 2 * m) / largura(TITULO, PORTFOLIO["titulo"], 76, -0.6))
    svg.texto(m, 178, PORTFOLIO["titulo"], TITULO, round(tamanho, 1), c["tinta"], espacamento=-0.6)

    linhas = quebrar(TEXTO, PORTFOLIO["descricao"], 31, w - 2 * m)
    for i, linha in enumerate(linhas[:3]):
        svg.texto(m, 246 + i * 42, linha, TEXTO, 31, c["texto"])

    y = 246 + min(len(linhas), 3) * 42 + 34
    svg.texto(m, y, PORTFOLIO["acao"], MONO, 26, c["sinal"])
    svg.add(seta(m + largura(MONO, PORTFOLIO["acao"], 26) + 14, y - 3, c["sinal"], 16).replace('stroke-width="2"', 'stroke-width="2.6"'))
    return svg.render()


def main():
    SAIDA.mkdir(exist_ok=True)
    gerados = []
    for tema in TEMAS:
        for nome, conteudo in (
            (f"header-{tema}.svg", cabecalho(tema)),
            (f"header-celular-{tema}.svg", cabecalho_celular(tema)),
            (f"portfolio-{tema}.svg", portfolio(tema)),
            (f"portfolio-celular-{tema}.svg", portfolio_celular(tema)),
        ):
            (SAIDA / nome).write_text(conteudo, encoding="utf-8")
            gerados.append(SAIDA / nome)
    for arquivo in gerados:
        print(f"{arquivo.relative_to(RAIZ)}  {arquivo.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
