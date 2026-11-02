# br-eli-mcp (versão endurecida no Gilberto)

## Origem e licença

- Projeto: `github.com/matematicsolutions/br-eli-mcp`, licença Apache-2.0 (arquivo `LICENSE` preservado).
- Versão: 0.8.3, commit de origem `1ac3f631915bef95a6590ceccc1d1b88f081ee96`.
- Dependências: `lock/requirements.txt`, exportado de `plugin/uv.lock` do upstream com `uv export --frozen`, incluindo hashes SHA-256. A instalação usa `--require-hashes`.

## Por que foi vendorizado

A auditoria estática encontrou um mecanismo de configuração remota: o pacote buscava um manifesto JSON em uma Release do GitHub na primeira chamada de ferramenta e o usava para substituir os oito endereços base das APIs, sem assinatura nem verificação de hash. A versão do PyPI tem essa busca ativada por padrão; a versão do plugin a desativa por variável de ambiente.

## Alterações em relação ao upstream

1. **Dados pessoais removidos dos fixtures.** Os arquivos de `tests/fixtures/` do upstream continham nomes reais de relatores, signatários e advogados, além de um CPF válido em campo de signatário. Esses valores foram substituídos por marcadores estáveis (`Pessoa Sintética NNN` e `00000000000`). Apenas os valores mudaram: a estrutura das chaves JSON é idêntica em todos os arquivos, verificada automaticamente. Os testes que citavam um nome real passaram a usar o marcador.
2. **Manifesto remoto desativado.** `runtime.py` não busca nem lê cache; os endereços são os fixados no código ou uma substituição validada.
3. **Substituição de endereços restrita.** `server.py`: a variável de ambiente só é aceita se for HTTPS, no mesmo host do padrão, sem credenciais e sem porta fora do padrão. Qualquer outro valor gera erro.
4. **STJ sem redirecionamentos.** `stj_client.py` usa `follow_redirects=False`, para que uma resposta não leve a requisição para fora do domínio oficial.
5. **Testes de travamento.** `tests/test_hardening.py` (11 testes offline) fixa os controles acima.

A lista de ferramentas e suas descrições não mudou: `test_descriptor_lock.py` continua passando.

Esta versão está consolidada em um único commit. Uma versão anterior, que continha os fixtures originais, foi removida do histórico do ramo por conter dados pessoais.

## Resultados verificados

- Testes offline do upstream antes das alterações: 25 aprovados.
- Após as alterações e a pseudonimização: 36 testes offline aprovados (25 + 11 novos), com dependências fixadas por hash, Python 3.11.
- Verificação dos fixtures: nenhum nome original e nenhum CPF formatado restante. Três ocorrências de texto coincidem com nomes de chaves JSON, não com dados pessoais.
- **Não executados:** os testes `*_smoke.py` precisam de rede real contra as APIs públicas e não foram rodados. Não há, portanto, evidência de que os endpoints ainda respondem nem de que o formato das respostas não mudou.

## Riscos ainda abertos

1. **Endpoints por engenharia reversa.** O README do upstream admite que alguns endpoints foram descobertos a partir das interfaces web (TST, TCU e STJ). Podem mudar sem aviso e seu uso pode estar fora dos termos de uso. Não usar em produção sem confirmação de advogado e de engenheiro.
2. **Termos do DataJud.** A API pública do CNJ permite apenas uso não comercial e autorizado e proíbe redistribuição. Qualquer uso que atinja o DataJud herda essas restrições.
3. **Cache em disco.** O `diskcache` usa pickle para alguns valores. O risco fica restrito a quem tem escrita no diretório de cache do usuário, que deve ter permissão restrita.
4. **Registro de auditoria.** O log grava hashes das entradas, não as entradas. Ainda é preciso definir retenção e base legal da LGPD.
5. **Dependências transitivas.** Os hashes garantem que os pacotes são os revisados, mas não que estão livres de vulnerabilidades. Falta uma varredura de vulnerabilidades (SBOM e CVE).
6. **Integração com o Gilberto.** Esta cópia ainda não está ligada ao backend nem ao CI do projeto.

## Como atualizar

Qualquer nova versão do upstream deve ser comparada com o upstream em `1ac3f63`, reaplicando os controles de `test_hardening.py` e a pseudonimização dos fixtures, e depois passar pela auditoria estática e pelos testes offline.

## Serviço HTTP (implantação separada)

`service/app.py` expõe o mesmo servidor MCP por streamable-http, em modo sem estado, atrás de
`Authorization: Bearer` (`BR_ELI_SERVICE_TOKEN`, mínimo de 32 caracteres; sem token o processo não inicia).
`/health` é a única rota sem autenticação. `service/Dockerfile` instala as dependências com
`--require-hashes` a partir de `lock/requirements.txt`. O backend usa `backend/legal_sources/br_eli_client.py`,
que só chama as ferramentas da lista de permissões, todas somente leitura.
Cache e auditoria ficam em `/tmp` no contêiner, portanto não persistem entre implantações.
