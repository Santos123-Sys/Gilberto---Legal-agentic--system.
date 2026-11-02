# Recuperação jurídica (RAG) para o Gilberto — desenho e PR-R1

**Status:** PR-R1 em rascunho. Nada deste documento está ligado ao caminho de requisições nem carrega dados jurídicos reais. Os testes usam apenas textos sintéticos.

## 1. Objetivo e limites

O objetivo é um assistente que responda com base em fontes jurídicas brasileiras recuperadas do acervo, e não apenas da memória do modelo. Isso reduz, mas não elimina, a invenção de dispositivos e de decisões.

Não há treinamento de modelo. A abordagem é de recuperação com geração aumentada (RAG): o sistema busca trechos de fontes e os entrega ao modelo como evidência. A saída é uma minuta para revisão humana, nunca uma certificação jurídica.

## 2. Correções ao roteiro de referência

- **Modelos:** o roteiro cita GPT-4o, Claude 3.5 Sonnet e Llama 3, que são versões antigas. A escolha do modelo deve ser feita no momento da implementação, com base na avaliação do próprio sistema, e não em listas de redes sociais.
- **"Treinado com o acervo":** uma reportagem de 7 de novembro de 2025 descreve o Jus IA como recuperação sobre base proprietária, não como treinamento. Essa é a mesma abordagem deste desenho, mas a afirmação do fornecedor sobre o tamanho da base não foi verificada, e a reportagem não traz taxas de acerto.
- **Citação existente não é citação válida:** confirmar que um artigo ou acórdão existe não mostra que ele está em vigor, que não foi superado nem que tem força vinculante. Essas duas verificações são etapas separadas.
- **Licenciamento:** o acervo de leis publicadas é público, mas decisões, doutrina e bases de terceiros têm termos próprios. Nenhum dado real é carregado antes da decisão de licenciamento (seção 6).

## 3. Arquitetura em camadas

| Camada | Função | Estado |
|---|---|---|
| Ingestão de fontes | Registra `LegalSource` e `SourceVersion` com hash do texto, data de recuperação e datas de vigência declaradas | Existe (PR-02) |
| Fragmentação | Divide cada versão em trechos com deslocamentos exatos, de modo que cada trecho vire um `EvidenceSpan` íntegro | **PR-R1** |
| Índice léxico | BM25 com normalização de acentos, filtrado pela data de referência | **PR-R1** |
| Índice vetorial | Busca semântica. Adiada: exige escolha de modelo de embeddings e avaliação própria | Futuro |
| Portão de citações | Toda citação de dispositivo ou decisão numa resposta precisa coincidir com um trecho recuperado. O que não coincidir é marcado como não verificado | **PR-R2** |
| Geração com revisão | O modelo recebe apenas trechos recuperados como evidência. A saída passa por revisão humana obrigatória | PR-R3 |
| Perfil e tom | Nome, área de atuação e tom de voz. O número de OAB **não** entra no texto gerado, para não apresentar saída automática como trabalho assinado de um advogado | PR-R4 |

## 4. O que a PR-R1 garante

- **Fragmentos exatos.** Para todo fragmento, `texto[início:fim]` é igual ao próprio fragmento. Um teste verifica essa igualdade, e outro verifica que o trecho se torna um `EvidenceSpan` íntegro (`span_is_intact`).
- **Vigência registrada, nunca presumida.** Fontes ainda não vigentes ou já encerradas na data de referência são excluídas e contadas. Fontes sem datas são incluídas, mas marcadas como `vigencia_nao_informada`. O rótulo `vigente_pelas_datas_registradas` indica apenas que as datas cadastradas batem com a data de referência. Nenhum rótulo afirma validade jurídica.
- **Evidência, não instrução.** O texto da fonte é devolvido sem alteração, com `role = "evidencia_nao_instrucao"` e `authority_verified = False`.
- **Isolamento entre locatários.** O índice só lê versões do locatário do repositório. Um teste confirma que o outro locatário recebe índice vazio.
- **Somente leitura.** Construir o índice não cria linhas nem eventos de auditoria. Um teste compara as contagens antes e depois.
- **Limites.** Consulta limitada a 32 termos; `top_k` entre 1 e 20; índice limitado a 100.000 fragmentos.

## 5. O que a PR-R1 não faz

Não há embeddings, chamadas a modelos, acesso à rede nem ligação ao caminho de requisições. A qualidade da recuperação não foi medida em direito brasileiro, porque não existe gabarito revisado por advogados (ver a lacuna BR-10 na auditoria). Os testes provam apenas o comportamento determinístico do código.

## 6. Decisão pendente do proprietário

Antes de carregar qualquer fonte real, é preciso decidir, por fonte:

1. Se a fonte é publicação oficial de domínio público (por exemplo, texto de lei publicado pelo Planalto) ou se tem termos de uso próprios (tribunais, DataJud, bases comerciais).
2. Se há restrição de redistribuição, inclusive para trechos armazenados e exibidos.
3. Se o conteúdo contém dados pessoais e qual base da LGPD se aplica.

Sem essas respostas, a ingestão permanece restrita a textos sintéticos.

## 7. Critérios de aceitação das próximas PRs

- **PR-R2:** toda citação de dispositivo ou decisão numa resposta gerada deve coincidir, por texto e deslocamento, com um trecho recuperado. Citações sem correspondência ficam marcadas como não verificadas e nunca como certificadas. Testes com citações inventadas e com citações de fontes fora de vigência.
- **PR-R3:** a saída deve conter as fontes usadas, os status de vigência e de verificação, e a marca de revisão humana obrigatória. Testes de injeção de instruções em fontes e em documentos enviados.
- **PR-R4:** perfil sem OAB no texto gerado. Testes confirmando que o número não aparece na saída.

Todas as PRs passam pelos portões existentes do projeto. Nenhuma delas altera o comportamento de produção.
