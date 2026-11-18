---
# VALORES EDITÁVEIS — altere os números abaixo para mudar o Brasil de janeiro de 2027.
# O motor lê este YAML. A narrativa depois do segundo delimitador é só contexto.

date:
  year: 2027
  month: 1

president:
  name: "Presidente da República"
  party: "independente (coalizão heterogênea)"
  honeymoon_months: 4

indicators:
  selic: 12.25
  inflation: 4.6
  unemployment: 6.9
  public_debt_gdp: 78.4
  gdp_growth: 2.2
  fiscal_primary_result: -0.4
  exchange_rate_usd: 5.35
  poverty: 26.8
  approval: 49.0
  crime_index: 61.0
  health_index: 54.0
  education_index: 51.0
  infrastructure_index: 47.0
  political_capital: 55.0
  media_climate: 48.0
  institutional_stability: 62.0

budget:
  annual_revenue_brl_bi: 2850.0
  mandatory_share: 0.92
  fiscal_space_brl_bi: 92.0
  fiscal_space_annual_cap_brl_bi: 120.0
  monthly_replenish_brl_bi: 6.5

cabinet_mode: automatic
ministers:
  - portfolio: casa_civil
    title: "Casa Civil"
    name: "Indicação automática"
  - portfolio: fazenda
    title: "Fazenda"
    name: "Indicação automática"
  - portfolio: justica
    title: "Justiça e Segurança Pública"
    name: "Indicação automática"
  - portfolio: relacoes_exteriores
    title: "Relações Exteriores"
    name: "Indicação automática"
  - portfolio: defesa
    title: "Defesa"
    name: "Indicação automática"
  - portfolio: saude
    title: "Saúde"
    name: "Indicação automática"
  - portfolio: educacao
    title: "Educação"
    name: "Indicação automática"
  - portfolio: planejamento
    title: "Planejamento"
    name: "Indicação automática"

approval_breakdown:
  regions:
    norte: 48.0
    nordeste: 54.0
    centro_oeste: 49.0
    sudeste: 46.0
    sul: 44.0
  income:
    baixa: 53.0
    media: 48.0
    alta: 41.0

congress:
  coalition_support: 46.0
  chamber:
    seats: 513
    government: 142
    allied: 98
    opposition: 188
    independent: 85
  senate:
    seats: 81
    government: 22
    allied: 16
    opposition: 28
    independent: 15
  parties:
    - id: bloco_governo
      name: "Bloco do governo"
      chamber_seats: 142
      senate_seats: 22
      stance: 38
      bloc: government
      discipline: 78
    - id: centrao
      name: "Centrão aliado"
      chamber_seats: 98
      senate_seats: 16
      stance: 12
      bloc: allied
      discipline: 62
    - id: oposicao_direita
      name: "Oposição conservadora"
      chamber_seats: 110
      senate_seats: 16
      stance: -42
      bloc: opposition
      discipline: 74
    - id: oposicao_esquerda
      name: "Oposição progressista"
      chamber_seats: 78
      senate_seats: 12
      stance: -28
      bloc: opposition
      discipline: 70
    - id: independentes
      name: "Independentes e nanicos"
      chamber_seats: 85
      senate_seats: 15
      stance: 0
      bloc: independent
      discipline: 40


branches:
  executive_legislative: 44
  executive_judiciary: 51
  legislative_judiciary: 57

diplomacy:
  USA: 58
  CHN: 63
  RUS: 42
  EU: 61
  IND: 55
  ARG: 64
  MERCOSUL: 60
  BRICS: 58
  IMF: 52
  UN: 60

trade:
  USA: 82.0
  CHN: 158.0
  EU: 92.0
  ARG: 28.0
  IND: 15.0

main_problems:
  - id: fiscal
    title: "Pressão fiscal e dívida pública"
    severity: 7
  - id: congress
    title: "Congresso fragmentado, coalizão estreita"
    severity: 8
  - id: crime
    title: "Criminalidade organizada e segurança pública"
    severity: 7
  - id: infra
    title: "Gargalos de infraestrutura logística"
    severity: 6
  - id: health_edu
    title: "Qualidade desigual de saúde e educação"
    severity: 6
  - id: climate
    title: "Desmatamento e pressão internacional ambiental"
    severity: 5
  - id: polarization
    title: "Polarização política e desinformação"
    severity: 7

agents:
  congresso:
    name: "Congresso Nacional"
    interests:
      - emendas parlamentares
      - autonomia orçamentária
      - sobrevivência eleitoral
    influence: 88
    resources: 75
    stance: 8
  partidos:
    name: "Partidos políticos"
    interests:
      - cargos e ministérios
      - fundo partidário
      - palanques estaduais
    influence: 72
    resources: 68
    stance: 5
  governadores:
    name: "Governadores"
    interests:
      - transferências federais
      - obras nos estados
      - autonomia estadual
    influence: 64
    resources: 60
    stance: 10
  stf:
    name: "Supremo Tribunal Federal"
    interests:
      - independência judicial
      - controle de constitucionalidade
      - prestígio institucional
    influence: 80
    resources: 55
    stance: 4
  empresariado:
    name: "Setor empresarial"
    interests:
      - juros mais baixos
      - reforma tributária previsível
      - desregulamentação seletiva
    influence: 70
    resources: 82
    stance: 6
  sindicatos:
    name: "Sindicatos"
    interests:
      - emprego formal
      - salário mínimo
      - proteção trabalhista
    influence: 48
    resources: 42
    stance: -4
  forcas_armadas:
    name: "Forças Armadas"
    interests:
      - orçamento de defesa
      - não politização da tropa
      - reequipamento
    influence: 58
    resources: 70
    stance: 2
  imprensa:
    name: "Imprensa"
    interests:
      - acesso a informação
      - audiência
      - liberdade de imprensa
    influence: 66
    resources: 50
    stance: -2
  sociedade_civil:
    name: "Sociedade civil"
    interests:
      - direitos sociais
      - transparência
      - meio ambiente
    influence: 40
    resources: 35
    stance: 3
---

# Brasil em janeiro de 2027 — contexto inicial (editável)

Você acaba de tomar posse como Presidente da República. O país está polarizado,
mas institucionalmente estável. A economia cresce de forma modesta, com inflação
próxima do teto da meta e uma Selic ainda restritiva. A dívida pública limita o
espaço fiscal. O Congresso é fragmentado: a base aliada não garante maioria
sólida na Câmara nem no Senado.

A criminalidade organizada permanece como desafio estrutural. Saúde e educação
melhoraram em cobertura, mas a qualidade é desigual entre regiões. A
infraestrutura logística (portos, ferrovias, saneamento) é um gargalo ao
crescimento.

Na política externa, o Brasil tenta equilíbrio pragmático entre Estados Unidos e
China, com ênfase em Mercosul, BRICS e transição energética. Uma crise
internacional, um choque de commodities ou um impasse no Congresso podem
alterar rapidamente o cenário.

Edite os números no YAML acima para montar o Brasil com o qual você quer jogar.
