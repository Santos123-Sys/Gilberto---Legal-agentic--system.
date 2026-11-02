# Gilberto — Sistema agêntico de análise jurídica

**Português** · [English](README.en.md)

> *"A tecnologia como ferramenta de fortalecimento do raciocínio — não como substituta do cérebro."*

Gilberto é um sistema de múltiplos agentes de IA para a análise de contratos regidos pelo direito brasileiro. Equipes de agentes especializados examinam o documento, revisam as conclusões umas das outras, são contestadas por um revisor adversarial e consolidadas por um coordenador. Em seguida, o resultado passa por etapas obrigatórias de revisão humana.

> **Situação atual.** O Gilberto produz **minutas geradas por IA para revisão jurídica**, e não pareceres. As fontes jurídicas citadas pelos agentes **não são verificadas automaticamente**, e ainda não existe um benchmark jurídico revisado por advogados que comprove a precisão do sistema. Toda conclusão exige verificação humana antes de qualquer uso.

---

## A filosofia por trás do Gilberto

Criei o Gilberto para jovens advogados que querem usar a tecnologia com inteligência: não para substituir o julgamento jurídico, mas para aprimorá-lo.

A advocacia exige algo que nenhum sistema de IA reproduz: compreender o contexto, exercer discernimento, assumir responsabilidade profissional e aplicar a ética diante da incerteza. O Gilberto não finge o contrário. O que ele oferece é uma segunda opinião estruturada e rigorosa, produzida por agentes orientados por roteiros de análise contratual brasileira, para que nada passe despercebido.

**A convicção central:** um advogado que usa a IA de forma crítica é mais forte do que qualquer sistema de IA sozinho.

## Duas formas de usar o Gilberto

### Forma 1 — A IA como camada de verificação (recomendada para contratos complexos)

```
VOCÊ analisa o contrato primeiro
        ↓
Envia o documento ao Gilberto
        ↓
O Gilberto executa a análise com as equipes de agentes
        ↓
VOCÊ compara o resultado com a sua própria análise
        ↓
O Gilberto encontrou algo que você não viu?
Você encontrou algo que o Gilberto não viu?
        ↓
O julgamento final é SEU
```

É a abordagem que recomendo para contratos complexos — acordos de acionistas, documentos de M&A, contratos de prestação de serviços de longo prazo —, em que o julgamento humano é insubstituível, mas o volume de cláusulas é grande o bastante para que algo sempre possa escapar. Use o Gilberto como um mecanismo de checklist com profundidade jurídica, e não como seu analista principal.

### Forma 2 — A IA como analista de primeira leitura (útil para grandes volumes)

```
Envie o contrato diretamente
        ↓
O Gilberto executa o ciclo completo de análise
        ↓
VOCÊ avalia criticamente cada resultado
Questione cada conclusão. Discorde quando souber mais.
        ↓
Envie comentários → o Gilberto os encaminha à frente competente
        ↓
Análise revisada
        ↓
O julgamento final é SEU
```

Funciona bem quando há muitos contratos a processar e é preciso um ponto de partida estruturado. A palavra-chave é **criticamente**: nunca aceite o resultado de forma passiva. O ciclo de comentários existe exatamente para isso — contestar as conclusões do Gilberto e obrigá-lo a defendê-las ou revisá-las.

### O que o Gilberto não é

O Gilberto **não substitui** a consultoria jurídica e **não é** um advogado inscrito na OAB. Ele **nem sempre acerta**: deixará de ver coisas, e você é a salvaguarda. Também **não foi feito para uso passivo** — o ciclo de comentários não é opcional; ele é o propósito do sistema.

---

## Como funciona

### Equipes de agentes

A análise é dividida em cinco frentes, cada uma com quatro especialistas e um coordenador:

| Frente | Especialistas |
|---|---|
| **Fundamentos** | Classificação do contrato, integridade do documento, qualificação das partes, contexto da operação |
| **Risco financeiro** | Preço e pagamento, cláusula penal, garantias, quantificação da exposição econômica |
| **Mitigação e saída** | Direitos de extinção do contrato, força maior e onerosidade excessiva, solução de controvérsias, estratégia de saída |
| **Conformidade** | LGPD e proteção de dados, anticorrupção, validade da assinatura eletrônica, disposições gerais |
| **Estratégia** | Poder de negociação, limites de concessão, intenção da contraparte, estrutura da operação |

Fora das frentes atuam dois agentes de coordenação: um **advogado do diabo**, que contesta as conclusões de todas as frentes, e um **coordenador-geral**, que produz a síntese final. Quando o usuário envia comentários, um **agente defensor dos comentários** é incluído na frente competente. Os papéis, objetivos e instruções de cada agente ficam em [`backend/agents/cluster_definitions.py`](backend/agents/cluster_definitions.py).

### Fluxo de uma rodada

```
Documento enviado
        │
        ▼
As cinco frentes trabalham em paralelo
  └─ dentro de cada frente, em sequência:
     análises dos especialistas → votos entre pares → síntese do coordenador
        │
        ▼
O advogado do diabo audita todas as frentes
        │
        ▼
O coordenador-geral consolida o resultado
        │
        ▼
Etapas de revisão humana (quando acionadas)
        │
        ▼
VOCÊ revisa ── comentários ──▶ reanálise da frente competente
        │                      e nova síntese
        ▼
Aceite final registrado
```

Os votos entre pares ocorrem **apenas dentro de cada frente**: um especialista em LGPD não pontua a análise de uma cláusula de garantia. A síntese entre frentes acontece somente nos níveis de coordenação.

**Custo por rodada.** Na revisão completa, cerca de **47 chamadas ao modelo** por rodada; no rascunho focado, com um revisor por frente, cerca de **12**. Os números pressupõem as cinco frentes ativas; a tela de plano mostra o número efetivo antes do envio.

### Pontuação de risco

Cada frente atribui uma pontuação de risco de 0 a 10 e uma autoavaliação de confiança de 1 a 5. Dois elementos são determinados pelo código, e não pelo modelo:

- **Pontuação final:** mediana das pontuações das frentes, ponderada pela confiança ([`backend/scoring.py`](backend/scoring.py)).
- **Classificação:** **Crítico** se a pontuação for ≥ 8; **Relevante** se for ≥ 5; **Aceitável** abaixo disso.

Os critérios qualitativos do Passo 11 — por exemplo, um risco crítico em qualquer frente ou um campo em branco no objeto, no preço ou no prazo — orientam os agentes por meio das suas instruções, mas **não são impostos pelo código**. A confiança informada pelo modelo **não é** uma probabilidade calibrada de acerto.

### Etapas de revisão humana

A análise para e exige uma decisão humana fundamentada quando:

1. a confiança de alguma frente fica abaixo do limite configurado (`GATE_1_CONFIDENCE_THRESHOLD`);
2. a gravidade das lacunas apontadas pelo advogado do diabo excede o limite configurado (`GATE_2_DEVIL_ADVOCATE_THRESHOLD`);
3. a classificação final é **Crítico**.

O revisor pode aprovar, substituir a pontuação ou solicitar reanálise; toda decisão exige fundamentação e fica registrada na trilha de auditoria. O aceite final só é possível depois de concluídas todas as revisões obrigatórias.

---

## Segurança e tratamento de dados

- **Autenticação obrigatória**, por OIDC ou por contas locais emitidas por um administrador (`AUTH_MODE=oidc` ou `local`). As rotas de sessão e de administração não funcionam sem autenticação.
- **Isolamento por titular:** cada sessão pertence ao usuário que a criou; para qualquer outro usuário, ela simplesmente "não existe".
- **Somente jurisdição brasileira.**
- **Provedor de IA:** Maritaca (Sabiá-4) é o provedor principal. Um provedor reserva só é usado se o operador o configurar **e** o usuário consentir expressamente com a transferência do documento. Não há nova tentativa nem troca automática de provedor após uma resposta incerta.
- **Permissões dos agentes:** cada envio ao modelo é autorizado por uma política de capacidades; um agente não pode ampliar as próprias permissões.
- **Persistência:** as sessões são gravadas em checkpoints SQLite em volume persistente (`SESSION_DB_PATH`), com backup criptografado e verificação de restauração isolada.
- **Base de provas (em implantação):** existe uma base PostgreSQL que vincula cada conclusão ao trecho exato do documento ou da fonte, com isolamento por inquilino no próprio banco. Ela **ainda não está ligada** ao fluxo de análise e permanece desativada até `EVIDENCE_DATABASE_URL` ser configurada.

---

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Modelo de linguagem | Maritaca AI Sabiá-4 (API compatível com OpenAI) |
| Agentes | CrewAI |
| Backend | FastAPI (Python 3.11) |
| Tempo real | Server-Sent Events |
| Frontend | React + Vite, Tailwind CSS, servido por Nginx |
| Persistência | SQLite (sessões e identidades); PostgreSQL + Alembic (base de provas) |
| Implantação | Railway — ambientes de homologação e de produção |

---

## Desenvolvimento local

### Pré-requisitos

- Python 3.11
- Node.js 22
- Chave de API da Maritaca ([plataforma.maritaca.ai](https://plataforma.maritaca.ai))

### Backend

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env              # nunca versione este arquivo
# Edite .env: MARITACA_API_KEY e a configuração de autenticação
uvicorn main:app --reload --port 8000
```

A autenticação é obrigatória também no ambiente local. Configure-a conforme um destes guias:

- contas locais por convite: [`docs/self-hosted-identity-runbook-20261029.md`](docs/self-hosted-identity-runbook-20261029.md);
- provedor OIDC: [`docs/oidc-rollout-and-railway-preflight.md`](docs/oidc-rollout-and-railway-preflight.md).

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

### Testes

Os mesmos comandos executados na integração contínua:

```bash
# Backend
cd backend
python -m unittest discover -s tests -v
python -m benchmarks.validate

# Frontend
cd frontend
npx playwright install chromium
npm test
npm run test:local
npm run test:br-legal-notice
npm run build
```

Os testes da base de provas também rodam contra PostgreSQL quando `EVIDENCE_TEST_DATABASE_URL` está definida; na integração contínua, eles não podem ser ignorados.

---

## Implantação

O Gilberto roda no Railway com dois serviços — backend e frontend — em dois ambientes:

| Ambiente | Ramo implantado |
|---|---|
| Homologação | `release/brlaw-security-staging-20261029` |
| Produção | `main` |

O frontend Nginx encaminha `/api` ao backend pela rede privada do Railway (`GILBERTO_API_UPSTREAM`, `GILBERTO_PROXY_SECRET`), de modo que navegador e API compartilham a mesma origem. O backend precisa de um volume persistente montado em `/data`. Para o passo a passo, as variáveis exigidas e as verificações prévias, consulte [`docs/oidc-rollout-and-railway-preflight.md`](docs/oidc-rollout-and-railway-preflight.md) e [`docs/self-hosted-identity-runbook-20261029.md`](docs/self-hosted-identity-runbook-20261029.md).

**Política de liberação:** nenhuma alteração chega à produção sem os critérios de liberação documentados, incluindo revisão jurídica humana do conteúdo jurídico.

---

## Referência da API

As rotas de sessão e de administração exigem autenticação. `…` corresponde a `/api/sessions`.

| Grupo | Rotas |
|---|---|
| Sessões | `POST /api/sessions` · `POST …/{id}/start` · `GET …/{id}/status` · `GET …/{id}/results` · `GET …/{id}/stream` (SSE) |
| Revisão humana | `GET …/{id}/gates` · `POST …/{id}/gate-decision` · `POST …/{id}/human-votes` · `POST …/{id}/feedback` · `POST …/{id}/accept` |
| Controle de execução | `POST …/{id}/pause` · `POST …/{id}/resume` · `POST …/{id}/cancel` |
| Autenticação | `POST /api/auth/login` · `POST /api/auth/logout` · `GET /api/auth/me` · `POST /api/auth/change-password` · `GET /api/auth/bootstrap-status` · `POST /api/auth/bootstrap` |
| Administração | `GET /api/admin/users` · `GET /api/admin/backups/status` · `POST /api/admin/backups/run` · `POST /api/admin/backups/verify` · `GET /api/admin/operations/summary` · rotas de observabilidade |
| Saúde | `GET /api/health` · `GET /api/ready` |

A documentação interativa da API fica em `/docs` quando o backend roda localmente.

---

## Estrutura do projeto

```
backend/
  main.py                  API FastAPI e todas as rotas
  config.py                Configurações por variáveis de ambiente
  engines/                 Orquestração dos agentes (debate_engine_v3.py)
  agents/                  Definições, papéis e instruções dos agentes
  legal/                   Regras de confiabilidade jurídica brasileira
  evidence/                Base de provas PostgreSQL (desativada por padrão)
  security/                Autenticação, autorização e política de capacidades
  gates/                   Etapas de revisão humana
  scoring.py               Agregação determinística da pontuação de risco
  benchmarks/              Casos sintéticos de controle
  tests/                   Testes do backend
frontend/
  src/components/          Telas e painéis
  src/hooks/               Estado da sessão e fluxo de eventos
  src/auth/                Autenticação no navegador
  tests/, tests-local/     Testes Playwright (OIDC e contas locais)
backup_gateway/            Gateway de backup criptografado
docs/                      Decisões de arquitetura, auditorias e guias operacionais
```

---

## Próximos passos

O plano de engenharia em andamento prevê, nesta ordem:

- [x] Reconciliação de segurança entre homologação e produção
- [x] Base de provas PostgreSQL com isolamento por inquilino
- [ ] Interface, mensagens e instruções dos agentes em português
- [ ] Ingestão estruturada de documentos (páginas, cláusulas, tabelas)
- [ ] OCR local para documentos digitalizados
- [ ] Consulta a fontes oficiais brasileiras (Planalto, LexML, STJ, STF, CNJ DataJud)
- [ ] Agentes que fundamentam cada conclusão em provas verificáveis
- [ ] Área de trabalho para inspecionar cada conclusão ao lado da fonte
- [ ] Revisão profissional atribuível, vinculada à versão exata da prova
- [ ] Benchmark jurídico brasileiro revisado por advogados

---

## Nota final

O Gilberto é um projeto pessoal, sem fins comerciais, para advogados que acreditam que o futuro da advocacia não é a IA substituindo o julgamento — são advogados usando a IA para tornar o próprio julgamento mais preciso, mais rápido e mais difícil de superar.

Se você está usando esta ferramenta de forma passiva, está usando errado.
