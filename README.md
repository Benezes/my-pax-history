# Simulador de Presidência do Brasil

Simulador político e geopolítico local: você governa o Brasil a partir de janeiro de 2027. As decisões entram em linguagem natural. O **motor da simulação** aplica regras, custos, votos e indicadores. A **IA** interpreta ações, interpreta agentes e escreve narrativa — ela não define números à vontade.

Inspirado em jogos do tipo Pax Historia. Código em inglês; interface e textos gerados em português brasileiro.

## Requisitos (macOS)

- Python 3.11+ (3.12 ok)
- Node.js 20+
- (Opcional) [Ollama](https://ollama.com) para LLM local
- (Opcional) chave da API [Google Gemini](https://aistudio.google.com/apikey)

## Instalação

`make` é opcional. Sem ele:

```bash
cd my-pax-history
./install.sh
```

Com Make:

```bash
cd my-pax-history
make install
```

## Como jogar

```bash
./dev.sh
```

ou `make dev`.

Abra [http://127.0.0.1:5173](http://127.0.0.1:5173). Backend em `http://127.0.0.1:8000`.

**Configurações** na tela inicial ou no jogo: provedor padrão, modelo Gemini, URL/modelo Ollama. A chave Gemini fica só neste computador (navegador + SQLite local).

Se o globo WebGL não desenhar (GPU ausente, renderização por software, textura falha), o mapa SVG entra sozinho. Forçar: `http://127.0.0.1:5173/?globe=fallback`. Os dois modos desenham fronteiras reais (Natural Earth 110m, domínio público, arquivo local em `frontend/public/globe/countries.geojson`).

Ações longas: até 12.000 caracteres, com contador no campo. Erros de validação aparecem em português.

Na nova partida:

1. Escolha o provedor de IA
   - **Simulação offline (sem IA)** — funciona sem Ollama e sem chave
   - **Google Gemini**
   - **LLM local (Ollama)**
2. Escolha a dificuldade (Médio / Difícil / Impossível). A dificuldade muda profundidade estratégica dos agentes, antecipação e intensidade das consequências, não só os números.
3. Escreva 3 a 5 propostas de campanha e **vá às urnas**. O motor simula voto e Congresso; a IA só classifica a plataforma.
4. Na posse, o mandato das urnas barateia ações alinhadas às propostas — sobretudo no primeiro ano.

Escreva ações, use **E se?** para um ensaio do assessor (não altera o estado), **registre** a ação e **avance o tempo**. Cada ciclo mensal: ações → reações dos agentes → indicadores → eventos → relatório.

Você perde por impeachment, golpe ou derrota em outubro de 2030. O motor calcula isso.

## Recursos: orçamento e capital político

Toda ação tem custo calculado **pelo motor**:

- **Espaço fiscal (R$ bi)** — contra o espaço discricionário do Orçamento. Recompõe-se aos poucos com a arrecadação.
- **Capital político** — regenera lentamente conforme aprovação e apoio no Congresso.

A IA só estima o **escopo** (pequeno/médio/grande/massivo). Se faltar recurso, a ação é **bloqueada** ou **executada pela metade**, com recado em português no relatório.

Se o Congresso **rejeitar** a medida, o espaço fiscal não é empenhado e **metade** do capital político cobrado volta (constante `REJECTION_CAPITAL_REFUND`).

## Campanha, Congresso e mandato das urnas

Novas partidas começam na campanha de 2026, antes de janeiro de 2027. Saves antigos sem campanha continuam jogáveis como antes.

- **Urnas:** o motor calcula voto (1º turno ou 2º, se precisar), margem e o peso de cada proposta no mandato. A IA/mock só classifica e narra, em JSON validado.
- **Congresso:** a base na Câmara e no Senado cresce com a margem e o alinhamento da plataforma, com teto para não entregar supermaioria de graça.
- **Mandato das urnas:** ação alinhada a uma proposta de campanha custa menos capital e tem mais chance de passar. O bônus é maior no ano 1, cai com o tempo e com popularidade baixa (`MANDATE_*` em `backend/app/constants.py`).
- **Limites:** inconstitucional, sem orçamento ou em contradição com a própria campanha ainda bloqueia; o relatório diz o motivo em português e se o bônus chegou a valer.

## Provedores de IA

Arquitetura plugável (`backend/app/llm/`). V1: `mock`, `gemini`, `ollama`. Para OpenRouter/OpenAI, registre outra classe em `registry.py`.

### Offline / mock

Não chama rede. Serve para aprender o jogo e para desenvolvimento.

Para ver os estados de espera da IA sem Gemini, defina `MOCK_LLM_DELAY_SECONDS` (por exemplo `8`) ao subir o backend. O padrão é `0`, então os testes continuam rápidos.

Chamadas reais de Gemini/Ollama podem levar alguns minutos. O `fetch` do navegador e o proxy do Vite esperam até **3 minutos e meio**. Cada modelo Gemini tem um teto curto (`GEMINI_ATTEMPT_TIMEOUT_SECONDS`, padrão 50s); se travar, o jogo abandona e tenta o próximo da lista. O orçamento total da cadeia (`GEMINI_TOTAL_BUDGET_SECONDS`, padrão 165s) fica abaixo do timeout da interface. A UI mostra um spinner com tempo decorrido e, no relatório, qual modelo respondeu.

### Gemini

1. Crie uma chave em Google AI Studio.
2. Copie `.env.example` para `.env` e preencha:

```bash
GEMINI_API_KEY=sua_chave
GEMINI_MODEL=gemini-flash-latest
```

O padrão é o alias `gemini-flash-latest` (não um número de versão que some). Em **Configurações**, com a chave preenchida, a lista de modelos vem da API ListModels. Se um modelo responder 404/429/503, ou estourar o tempo da tentativa, o jogo cai para a lista de reserva: `gemini-3.1-flash-lite`, `gemini-3.5-flash`, `gemini-pro-latest`, e por último `gemini-3.8-flash`. Modelos flash pedem um orçamento baixo de “thinking”; se o modelo recusar o campo (HTTP 400), a chamada é refeita sem ele.

Ou cole a chave na tela de nova partida / Configurações. Ela fica só no SQLite local (`backend/data/`), nunca no repositório.

### Ollama (Mac)

Sugestão em Apple Silicon com 16 GB: **`llama3.2`** (leve) ou **`gemma2:9b`** / **`llama3.1:8b`** se houver RAM.

```bash
brew install ollama
ollama serve
ollama pull llama3.2
```

O jogo fala com `http://127.0.0.1:11434`. Se o Ollama não estiver no ar, a interface mostra o erro em português e não quebra a partida.

## Arquivos de cenário (editáveis)

- `pre_inicio_brasil.md` — YAML no topo: Selic, inflação, desemprego, dívida, PIB, Congresso, partidos, relações entre poderes, crime, saúde/educação/infra, aprovação, diplomacia, problemas, **orçamento**, ministérios automáticos, aprovação por região/renda.
- `contexto_mundial.md` — EUA, China, Rússia, UE, Índia, Oriente Médio, Argentina, órgãos internacionais.

O motor lê os números do YAML. A prosa depois do `---` é contexto para a IA. Edite e comece uma nova partida.

## Salvamento

Cada partida fica em SQLite (`backend/data/simulador.db`). Use **Salvar** para um arquivo nomeado e **Carregar** na tela inicial. A memória da IA é resumo + estado atual + eventos recentes, nunca o histórico inteiro.

## Estrutura

```
backend/app/engine/   motor (regras, custos, votos, perda)
backend/app/llm/      provedores (mock, Gemini, Ollama)
frontend/            Vite + React + TypeScript + globo
```

## Limitações da V1

- Ministérios existem no estado (modo automático); ainda não há tela para nomear ministros.
- Votos no Congresso já usam bancadas internamente; não há painel partido a partido nem plebiscito jogável.
- Há um gancho de manchetes no estado, sem feed de redes sociais nem aprovação regional na UI.
