# Consulta a fontes jurídicas brasileiras: diligência preliminar sobre terceiros

**Data:** 30/10/2026. **Decisão:** apenas pesquisa e piloto; nenhuma dependência é instalada, copiada ou ativada por este PR.

## Procedência e triagem dos repositórios

| Candidato | Fonte canônica | Metadados do repositório inspecionados | Destinação |
|---|---|---|---|
| LexMCP / `mcp-juridico-brasil` | https://github.com/ehrodan/lexmcp | Metadados do GitHub: MIT; último envio em 24/07/2026; há testes e workflows publicados. O histórico do repositório é raso (um commit no instantâneo inspecionado). O README afirma suportar LexML, DataJud e um corpus local. | **PILOTO, isolado e somente leitura**. Auditar todos os caminhos de rede e de credenciais, as licenças transitivas, a precisão das saídas, o comportamento sob limites de requisição e a cobertura real das fontes antes do uso. As afirmações do README não são desempenho verificado. |
| `EternoHelder/datasets-jur` | https://github.com/EternoHelder/datasets-jur | Metadados do GitHub: Apache-2.0 para o repositório; último envio em 05/04/2026. Histórico escasso. O README descreve scripts de extração do STJ, do DataJud e de trabalhos acadêmicos e afirma expressamente que os dados de origem têm termos próprios. | **REJEITAR a execução e a integração diretas**. O script de download do STJ inspecionado insere dados não confiáveis de uma API remota em um heredoc de shell que contém código Python gerado e monta URLs e caminhos de arquivo a partir de metadados remotos. São riscos de injeção e de travessia de caminho que exigem reescrita com um parser seguro. Os direitos sobre os dados continuam sem verificação. |
| Awesome Legal Data | https://github.com/openlegaldata/awesome-legal-data | Diretório curado com links brasileiros; último envio em 20/10/2026. Nenhuma classificação de licença identificada nos metadados inspecionados. | **APROVADO apenas como referência de descoberta**; **EVIDÊNCIA INSUFICIENTE** para incluir, relicenciar ou integrar código ou dados. |
| ContractNLI | https://github.com/stanfordnlp/contract-nli e https://stanfordnlp.github.io/contract-nli/ | Metadados do GitHub: CC-BY-4.0; conjunto de dados de pesquisa com 607 NDAs em inglês, 17 hipóteses fixas, rótulos de implicação/contradição/não mencionado e trechos de evidência. Último envio em 11/02/2022. | **PILOTO como metodologia de avaliação**, com atribuição; nunca usar como verdade de referência legislativa ou jurisprudencial brasileira. |

Inspeção adicional de código (30/10/2026):
- **LexMCP:** o `pyproject.toml` declara dependências apenas com versão mínima, sem limites superiores abrangentes. O cliente HTTP inspecionado implementa tempos limite, novas tentativas, limites de requisição e cache com TTL. O cliente do LexML usa `follow_redirects=True`; antes de um piloto, validar os destinos de redirecionamento e exigir uma lista de destinos de rede permitidos. Trata-se de uma observação de padrão de código, e não de um teste de intrusão.
- **datasets-jur:** `scripts/download_stj_academicos.sh` insere JSON remoto do CKAN em um heredoc Python sem aspas e deriva URLs de download e nomes de arquivo de campos de recursos remotos. Também referencia um caminho local fixo e identificadores provisórios. `scripts/download_datajud.py` contém um corte em março de 2026. Não executar nem integrar esses scripts como estão; reimplementar a consulta com segurança, com validação estrita de host e de caminho, e verificar de forma independente os direitos sobre os dados.

Os rótulos de licença do GitHub são metadados preliminares de licença de código e de dados, e não um parecer jurídico completo sobre direitos de material de terceiros, pesos de modelos, corpora derivados ou uso comercial posterior. Ainda não foram feitos, para esses candidatos, uma revisão completa de segurança do código, um SBOM das dependências, implantação nem experimento de precisão da consulta. Nenhum artefato revisado deve ser marcado silenciosamente como APROVADO PARA PRODUÇÃO.

## Viabilidade dos dados oficiais

- A [API Pública do CNJ](https://www.cnj.jus.br/sistemas/datajud/api-publica/) descreve **metadados** públicos de capa processual e de movimentações, e não uma API confiável de inteiro teor dos julgados. Não usar metadados do DataJud para certificar fundamentação ou teses de julgados.
- A [Wiki do DataJud (CNJ)](https://datajud-wiki.cnj.jus.br/api-publica/acesso/) documenta a autenticação por chave de API fornecida publicamente; a rotação é possível. Usar um valor atual, obtido por via oficial, e nunca fixá-lo no código.
- Os [endpoints do CNJ](https://datajud-wiki.cnj.jus.br/api-publica/endpoints/) são apelidos específicos por tribunal. Implementar paginação, limites e novas tentativas por tribunal.
- Prioridade para texto legal: publicação oficial vigente do Planalto e dos diários oficiais aplicáveis; LexML para metadados e descoberta, com conferência em fontes oficiais.
- Prioridade para decisões: **inteiro teor** oficial do STJ, do STF ou do tribunal pertinente, com data de publicação, número do processo, tese jurídica, trecho e verificação de alteração ou superação.
- Todo resultado deve distinguir **metadados descobertos**, **documento obtido**, **trecho correspondente**, **tese verificada**, **vigência temporal avaliada**, **fundamentos contrários investigados** e **revisão humana**.

## Contrato do piloto em etapas

1. Nenhum material confidencial de clientes; apenas entradas sintéticas controladas.
2. Ferramentas de consulta somente leitura, com lista explícita de hosts permitidos, proteção contra SSRF, credenciais de escopo restrito, orçamentos de requisição, direitos de cache e limites rígidos de requisição.
3. A ingestão deve preservar URLs originais, instituição, data e hora da consulta, hash do conteúdo, processo/data, versão do documento e trechos de evidência.
4. Sinais separados de autenticidade, trecho, aplicabilidade, vigência e revisão. Nenhum booleano único `VERIFIED`.
5. Os gabaritos devem ser aprovados por advogados brasileiros habilitados e independentes. Usar conjuntos distintos de teste e de validação reservada, com métricas de falsos positivos e falsos negativos.
6. Comparar cada adaptador com as fontes oficiais diretas; registrar cobertura, erros, latência p50/p95, custo total da execução e condições de saída ou reversão.
7. Exigir, antes da integração, lista de licenças de dependências aprovada, SBOM, varredura de vulnerabilidades, revisão de ameaças de rede e de segredos e resultados da integração contínua.
8. Não usar esses conjuntos de dados candidatos para sugerir endosso da OAB ou parecer jurídico verificado.

## Recomendação entre construir e contratar (provisória)

Começar com as verificações determinísticas de transcrição já existentes e com adaptadores de fontes oficiais mantidos pelo próprio Gilberto. Usar bibliotecas de consulta de código aberto somente por meio de interfaces pequenas e expressamente autorizadas. Considerar um fornecedor comercial de inteiro teor (inclusive o JUIT) **somente** após medir uma deficiência documentada de completude, licenciamento ou confiabilidade que não possa ser sanada de forma econômica pela estratégia de fontes oficiais.

A métrica relevante é o número de análises jurídicas brasileiras integralmente verificadas e aceitas por advogados por unidade de custo total, e não o volume de buscas ou o preço por token. Custos e direitos exigem os termos vigentes dos fornecedores e a medição da carga de trabalho; este documento não autoriza nenhuma contratação.

## Benchmark sintético neste PR

`backend/benchmarks/contract_controls.py` testa um contrato comercial fictício quanto a uma citação inventada do STJ, à divergência entre multa de 20% e de 2%, a poderes de representação sem respaldo, à validade da cláusula de foro e a um controle negativo válido de extração literal. Ele exercita o código **determinístico** existente de correspondência e de status de evidência. Não aciona um modelo nem verifica a jurisprudência brasileira.

Critério de aceitação: cinco estados de controle esperados e nenhuma certificação jurídica implícita. A precisão do modelo, a precisão das fontes de inteiro teor, a verdade de referência por advogados e os custos entre modelos permanecem **NÃO VERIFICADOS**.

## Revisores independentes da liberação

**Gerente de Auditoria de Engenharia**: verifica o esquema de procedência, o licenciamento, os testes de citação, a segurança e a integridade dos casos sintéticos. **Gerente de DevOps**: verifica a integração contínua, os limites de rede e de segredos, a homologação, a reprodutibilidade e a reversão. Estas são responsabilidades de revisão, e não afirmações de que processos gerenciais autônomos estejam em execução.
