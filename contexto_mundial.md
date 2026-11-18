---
# VALORES EDITÁVEIS: cenário geopolítico em janeiro de 2027.
# iso: código ISO-3 usado no globo. relation_brazil: 0–100.

powers:
  USA:
    name: "Estados Unidos"
    iso: USA
    lat: 39.8
    lng: -98.6
    gdp_growth: 1.9
    inflation: 2.5
    stability: 71
    military_posture: 82
    relation_brazil: 58
    trade_with_brazil_usd_bi: 82.0
    alignment: "ocidente"
    interests:
      - conter influência chinesa na América do Sul
      - nearshoring e minerais críticos
      - cooperação em defesa e Amazônia
    tensions:
      - rivalidade estratégica com a China
      - polarização doméstica
  CHN:
    name: "China"
    iso: CHN
    lat: 35.9
    lng: 104.2
    gdp_growth: 4.4
    inflation: 1.2
    stability: 76
    military_posture: 78
    relation_brazil: 63
    trade_with_brazil_usd_bi: 158.0
    alignment: "brics+"
    interests:
      - soja, minério e petróleo brasileiros
      - Nova Rota da Seda e 5G
      - votos no Sul Global
    tensions:
      - disputa tecnológica e comercial com os EUA
      - excesso de capacidade industrial
  RUS:
    name: "Rússia"
    iso: RUS
    lat: 61.5
    lng: 105.3
    gdp_growth: 1.1
    inflation: 6.8
    stability: 54
    military_posture: 88
    relation_brazil: 42
    trade_with_brazil_usd_bi: 8.5
    alignment: "revisionista"
    interests:
      - fertilizantes e energia
      - BRICS como palco diplomático
      - aliviar isolamento ocidental
    tensions:
      - guerra na Ucrânia e sanções
      - dependência da China
  EU:
    name: "União Europeia"
    iso: EU
    lat: 50.1
    lng: 10.4
    gdp_growth: 1.2
    inflation: 2.3
    stability: 68
    military_posture: 48
    relation_brazil: 61
    trade_with_brazil_usd_bi: 92.0
    alignment: "ocidente"
    interests:
      - acordo Mercosul-UE
      - desmatamento zero e CBAM
      - transição verde
    tensions:
      - protecionismo agrícola
      - fragmentação política interna
  IND:
    name: "Índia"
    iso: IND
    lat: 21.1
    lng: 78.9
    gdp_growth: 6.5
    inflation: 4.4
    stability: 66
    military_posture: 70
    relation_brazil: 55
    trade_with_brazil_usd_bi: 15.0
    alignment: "multialinhada"
    interests:
      - petróleo, açúcar e defesa
      - reforma da ONU
      - BRICS seletivo
    tensions:
      - rivalidade com a China
      - proteção da indústria doméstica
  ARG:
    name: "Argentina"
    iso: ARG
    lat: -38.4
    lng: -63.6
    gdp_growth: 1.4
    inflation: 28.0
    stability: 42
    military_posture: 28
    relation_brazil: 64
    trade_with_brazil_usd_bi: 28.0
    alignment: "america_sul"
    interests:
      - Mercosul
      - energia e automotivo
      - crédito e estabilidade
    tensions:
      - instabilidade macroeconômica
  ME:
    name: "Oriente Médio"
    iso: SAU
    lat: 25.0
    lng: 45.0
    gdp_growth: 2.8
    inflation: 2.9
    stability: 48
    military_posture: 74
    relation_brazil: 57
    trade_with_brazil_usd_bi: 22.0
    alignment: "misto"
    interests:
      - petróleo e fertilizantes
      - diáspora e alimentos brasileiros
      - equilíbrio Irã–Israel–Golfo
    tensions:
      - risco de escalada regional
      - volatilidade do petróleo

orgs:
  UN:
    name: "ONU"
    relation_brazil: 60
    notes: "Brasil busca assento permanente no Conselho de Segurança."
  IMF:
    name: "FMI"
    relation_brazil: 52
    notes: "Sem programa; monitoramento de dívida e meta fiscal."
  WTO:
    name: "OMC"
    relation_brazil: 58
    notes: "Agronegócio brasileiro pressiona contra protecionismo."
  BRICS:
    name: "BRICS"
    relation_brazil: 58
    notes: "Expansão do grupo; Brasil evita alinhamento automático."
  MERCOSUL:
    name: "Mercosul"
    relation_brazil: 60
    notes: "Agenda de revisão tarifária e acordo com a UE."
  G20:
    name: "G20"
    relation_brazil: 64
    notes: "Capital diplomático residual da presidência recente."
  OAS:
    name: "OEA"
    relation_brazil: 55
    notes: "Democracia regional e crises hemisféricas."

flashpoints:
  - id: us_china
    title: "Rivalidade EUA–China"
    severity: 8
    countries: [USA, CHN]
  - id: ukraine
    title: "Guerra na Ucrânia e sanções à Rússia"
    severity: 7
    countries: [RUS, EU, USA]
  - id: middle_east
    title: "Instabilidade no Oriente Médio"
    severity: 7
    countries: [SAU, IRN, ISR]
  - id: mercosur_eu
    title: "Acordo Mercosul–União Europeia"
    severity: 5
    countries: [BRA, EU, ARG]
  - id: amazon
    title: "Pressão ambiental sobre a Amazônia"
    severity: 5
    countries: [BRA, EU, USA]
---

# Contexto mundial em janeiro de 2027 (editável)

O sistema internacional permanece marcado pela competição entre Estados Unidos
e China. Cadeias de suprimento estão sendo redesenhadas (friendshoring /
nearshoring). A Europa combina transição verde com insegurança energética. A
Rússia segue militarizada e sancionada. A Índia cresce e recusa alinhamentos
exclusivos. O Oriente Médio oscila entre distensão diplomática e risco de
escalada, o que afeta petróleo e fertilizantes — ambos críticos para o Brasil.

Para o Brasil, o tabuleiro exige equilíbrio: China é o principal parceiro
comercial; os EUA são centrais em finanças, tecnologia e defesa; a UE condiciona
comércio a cláusulas ambientais; o Mercosul é a base regional, mas a Argentina
está frágil. Choques externos (petróleo, soja, juros americanos, sanções) devem
entrar na simulação mesmo quando o presidente não age sobre eles.

Edite o YAML para recalibrar o mundo. O motor usa os números; a narrativa
abaixo é contexto para a IA.
