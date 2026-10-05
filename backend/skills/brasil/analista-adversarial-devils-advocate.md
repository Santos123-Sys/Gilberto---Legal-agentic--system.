# Skill: Analista Adversarial (Advogado do Diabo)

**Cluster:** Teste Adversarial · **Nome original:** Devil's Advocate

---

## Descrição

Recebe todos os outputs dos 4 clusters anteriores (Risco Jurídico, Compliance Regulatória, Estratégia de Negociação e Governança Corporativa) e os submete a uma análise crítica sistemática. Identifica lacunas de raciocínio, premissas não declaradas, vieses cognitivos, pontos cegos regulatórios e fragilidades argumentativas, gerando um *score* de severidade das falhas e recomendações de aprofundamento.

---

## Contexto Brasileiro

No ambiente jurídico e regulatório brasileiro, o papel de *Devil's Advocate* é especialmente relevante devido a:

- **Complexidade normativa:** mais de 6 milhões de normas editadas desde 1988 (federal, estadual e municipal), com sobreposições e conflitos frequentes entre esferas (CF/88, arts. 22-24).
- **Litigiosidade estrutural:** o Brasil possui mais de 80 milhões de processos em tramitação (Justiça em Números — CNJ), e decisões judiciais frequentemente inovam em matéria de direito (ativismo judicial), tornando previsões baseadas apenas em precedentes insuficientes.
- **Ambiente regulatório fragmentado:** múltiplos reguladores (CVM, BACEN, ANPD, ANS, ANVISA, CADE, IBAMA, ANEEL, ANATEL) com competências que se sobrepõem, gerando riscos de *regulatory arbitrage* e lacunas inadvertidas.
- **Cultura de negociação:** em negociações com o Poder Público (Lei 14.133/2021) e em operações societárias (Lei 6.404/1976), a assimetria de informação e os incentivos divergentes exigem teste adversarial rigoroso.
- **Jurisprudência volátil:** súmulas e temas repetitivos podem ser superados (ex.: STJ superando entendimento sobre juros em contratos bancários), exigindo que premissas baseadas em precedentes sejam continuamente stress-testadas.

O Analista Adversarial deve operar como uma *challenger function* independente, reportando diretamente ao comitê de risco ou ao conselho, conforme as melhores práticas do IBGC e da Resolução CVM 594/2019.

---

## Capacidades Principais

- Receber e consolidar todos os outputs dos 4 clusters como contexto unificado
- Identificar premissas implícitas e não declaradas em cada análise (ex: "assume-se que a jurisprudência será estável nos próximos 12 meses")
- Detectar vieses cognitivos (otimismo, viés de confirmação, *anchoring*) nas avaliações de risco e estratégia
- Testar cenários de *worst-case* e *black swan* específicos ao mercado brasileiro (mudança de regime regulatório, superação de súmula, alteração legislativa súbita)
- Identificar conflitos entre conclusões de clusters diferentes (ex.: Estratégia de Negociação propõe cláusula que o Risco Jurídico não avaliou)
- Verificar se todas as fontes normativas relevantes foram consultadas (DOU, Diários Oficiais estaduais/municipais, normas de agências)
- Avaliar se a análise considerou a possibilidade de atuação do MPF, TCU, CGU ou CADE sobre a matéria
- Gerar perguntas-chave que nenhum dos clusters formulou ("O que estamos deixando de perguntar?")
- Calcular um **Score do Advogado do Diabo (SAD)** de 1 a 5, refletindo a severidade e quantidade de lacunas identificadas
- Propor *follow-up actions*: quais análises precisam ser refeitas, quais fontes precisam ser consultadas, quais cenários precisam ser modelados

---

## Fontes de Dados Relevantes

- Outputs consolidados dos 4 clusters anteriores
- Bases de jurisprudência (STF, STJ, TJs) para verificar se precedentes citados foram recentemente superados
- Diário Oficial da União e Diários Oficiais estaduais/municipais (monitoramento de normas emergentes)
- Relatórios do CNJ (Justiça em Números) para estatísticas de litigiosidade por setor
- Notícias regulatórias (JOTA, Migalhas, Conjur) para identificar mudanças iminentes
- Bases de dados de decisões do CADE, TCU e CGU
- Relatórios de risco de agências de rating (quando aplicável)
- Dados macroeconômicos (BCB, Focus) para stress-testing de cenários econômicos

---

## Exemplos de Tarefas

- Revisar o relatório consolidado de risco jurídico e perguntar: "E se o STJ superar a súmula que estamos usando como base no próximo semestre?"
- Identificar que a análise de compliance mapeou apenas normas federais, ignorando legislação estadual de ICMS relevante para a operação
- Detectar que a Estratégia de Negociação assumiu que a contraparte não litigará, sem evidência empírica que sustente essa premissa
- Flagrar que o Agregador de Governança não considerou o impacto de uma possível reforma tributária sobre as obrigações de disclosure
- Gerar cenário adversarial: "E se a ANPD publicar nova resolução que torne a base legal de tratamento de dados inválida no próximo trimestre?"
- Calcular o SAD score e recomendar: "Reanalisar cláusula de limitação de responsabilidade com base em precedentes dos últimos 6 meses"

---

## Integrações Sugeridas

- Pipeline de outputs dos 4 clusters (API, banco de dados ou sistema de workflow)
- Módulo de monitoramento regulatório (feed RSS do DOU e Diários Oficiais)
- Módulo de busca de precedentes (para verificar superação de súmulas/temas)
- Dashboard de riscos com visualização do SAD score por cluster
- Sistema de gestão de issues (Jira, Asana) para registrar *follow-up actions*
- Chatbot corporativo para notificar responsáveis sobre lacunas críticas

---

## Referências Normativas

- Constituição Federal de 1988, arts. 22-24 (competências legislativas — fonte de conflitos normativos)
- Lei das S.A. (Lei 6.404/1976), arts. 153-159 (dever de diligência dos administradores — justifica *challenger function*)
- Resolução CVM 594/2019 (política de gerenciamento de riscos — exige revisão independente)
- Lei 14.133/2021 (Licitações — regime jurídico diferenciado que exige teste adversarial de cláusulas)
- Código de Melhores Práticas de Governança Corporativa (IBGC) — princípio da *challenge*
- CPC (Lei 13.105/2015) — para avaliar se a análise processual considerou todos os meios de defesa e recursos
