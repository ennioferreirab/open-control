# Runtime State Capture And Race Report

## Objetivo

Este relatorio explica como o runtime atual:

- captura mudancas de estado
- observa `tasks`, `steps`, `messages` e `chats`
- faz polling
- decide dispatch, pause, resume e review
- escreve status concorrentes

O foco e avaliar onde o desenho atual abre espaco para:

- stale reads
- duplicate processing
- duplicate side effects
- reconciliacao concorrente entre Python e Convex

O objetivo final e apoiar um endurecimento do Convex como source of truth.

## Resumo Executivo

O sistema atual nao funciona como um runtime dirigido por eventos do Convex.
Ele funciona como um conjunto de loops Python que fazem polling por `status`
ou por listas globais e reagem a snapshots inteiros.

Isso gera quatro propriedades estruturais importantes:

1. O runtime reage a listas por status, nao a transicoes atomicas.
2. O mesmo estado pode ser escrito por mais de um ator.
3. A deduplicacao e local em memoria do processo, nao global no banco.
4. O bridge faz retry generico de mutations sem idempotency key.

Na pratica, isso significa que o Convex ja guarda o estado operacional, mas
a logica de ownership do lifecycle ainda esta distribuida entre:

- workers Python
- mutations `tasks.ts`
- mutations `steps.ts`
- watchers de conversa
- timeouts e escalations

Se a meta e reduzir race condition, o sistema precisa migrar de:

- "workers observam snapshots e cada um age como consegue"

para:

- "Convex valida transicoes, concede claims e registra comandos/efeitos com idempotencia"

## 1. Como O Estado E Capturado Hoje

### 1.1 ConvexBridge como boundary

`mc/bridge/__init__.py` e o unico boundary Python para Convex.

Ele faz:

- `query()`
- `mutation()`
- adaptacao snake_case <-> camelCase
- retry de mutation com backoff
- subscription manager por polling

Ponto importante:

- `mutation()` faz retry generico
- nao existe idempotency key
- nao existe compare-and-set versionado no bridge

Implicacao:

se uma mutation aplicar no servidor mas a resposta falhar, a tentativa seguinte
pode repetir o efeito.

Isso e especialmente perigoso para:

- `messages:create`
- `messages:postStepCompletion`
- `activities:create`
- `tasks:updateStatus`
- `steps:updateStatus`

### 1.2 SubscriptionManager nao usa eventos reais do Convex

`mc/bridge/subscriptions.py` implementa `async_subscribe()` por polling.

Comportamento:

- cada assinatura vira uma query periodica
- o manager deduplica assinaturas iguais
- ele guarda `last_result`
- so emite para consumidores quando o snapshot inteiro muda

Propriedades:

- a unidade observada e "resultado atual da query"
- nao e "transicao detectada"
- nao existe cursor de evento
- nao existe ack persistido

Implicacoes:

- se uma task muda rapido de estado entre polls, um observer pode perder a fase intermediaria
- se o processo reinicia, a deduplicacao de snapshots e perdida
- dois loops diferentes podem reagir ao mesmo task state em momentos ligeiramente diferentes

### 1.3 Deduplicacao e local, nao global

Quase todos os loops mantem memoria local:

- `_known_inbox_ids`
- `_known_planning_ids`
- `_known_review_task_ids`
- `_known_kickoff_ids`
- `_known_assigned_ids`
- `_processed_signatures`
- `_seen_message_ids`

Esses mecanismos funcionam apenas dentro de um processo vivo.

Se houver:

- restart do gateway
- dois processos
- retry em paralelo
- clock drift entre loops

o sistema perde a nocao global de "ja processei esse evento".

## 2. Quais Loops Existem E O Que Cada Um Observa

### 2.1 Loops principais do gateway

`mc/runtime/gateway.py` sobe varios loops independentes.

### 2.2 TaskOrchestrator

`mc/runtime/orchestrator.py` cria 4 loops baseados em `tasks:listByStatus`.

#### Inbox loop

- Query: `tasks:listByStatus(status=inbox)`
- Poll: 3s
- Worker: `InboxWorker`
- Responsabilidade:
  - auto-title
  - primeira roteirizacao para `planning` ou `assigned`

#### Planning loop

- Query: `tasks:listByStatus(status=planning)`
- Poll: 5s
- Worker: `PlanningWorker`
- Responsabilidade:
  - gerar plano via Lead Agent
  - salvar `executionPlan`
  - materializar steps
  - iniciar dispatch autonomo
  - ou mover para `review + awaitingKickoff`

#### Review loop

- Query: `tasks:listByStatus(status=review)`
- Poll: 5s
- Worker: `ReviewWorker`
- Responsabilidade:
  - registrar que entrou em review
  - criar atividades/mensagens de review
  - bloquear auto-completion quando ha ask-user pendente

#### Kickoff/resume loop

- Query: `tasks:listByStatus(status=in_progress)`
- Poll: 5s
- Worker: `KickoffResumeWorker`
- Responsabilidade:
  - detectar task kicked off ou resumed
  - materializar steps se ainda nao existem
  - materializar steps incrementais quando o plano muda
  - disparar `StepDispatcher`

### 2.3 TaskExecutor

`mc/contexts/execution/executor.py` observa:

- Query: `tasks:listByStatus(status=assigned)`
- Poll: default de `async_subscribe()` = 2s

Responsabilidade:

- pickup de task assigned
- transicao `assigned -> in_progress`
- execucao de task sem steps materializados

Propriedade importante:

isso cria dois modelos de execucao de task:

- task direta em `assigned`, tratada pelo `TaskExecutor`
- task planejada com `steps`, tratada pelo `StepDispatcher`

### 2.4 PlanNegotiationSupervisor

`mc/contexts/planning/supervisor.py` observa:

- `tasks:listByStatus(status=review)`
- `tasks:listByStatus(status=in_progress)`
- Poll: 5s

Responsabilidade:

- spawnar loops por task para negociacao de plano

Implicacao:

o mesmo status `review` ou `in_progress` e observado por:

- `ReviewWorker`
- `KickoffResumeWorker`
- `PlanNegotiationSupervisor`
- `TimeoutChecker`

cada um com objetivos diferentes.

### 2.5 MentionWatcher

`mc/contexts/conversation/mentions/watcher.py` observa:

- Query: `messages:listRecentUserMessages`
- Poll: 10s
- Escopo: global, todas as tasks

Responsabilidade:

- detectar `@agent`
- classificar intent
- acionar resposta de mention

Importante:

- ele usa janela com overlap de 30s
- deduplica por `_seen_message_ids` em memoria
- nao usa claim persistido por mensagem

### 2.6 AskUserReplyWatcher

`mc/contexts/conversation/ask_user/watcher.py` faz polling por task ativa no registry.

- Poll: 1.5s
- Leitura: `bridge.get_task_messages(task_id)` para cada task com pending ask

Implicacao:

o mesmo conjunto de `messages` pode ser lido por:

- `MentionWatcher`
- `AskUserReplyWatcher`
- `ConversationService`

com logicas diferentes em cima da mesma mensagem.

### 2.7 ChatHandler

`mc/contexts/conversation/chat_handler.py` observa:

- Query: `chats:listPending`
- Poll: 5s ativo / 60s sleep

Responsabilidade:

- processar chats diretos fora da thread de task

### 2.8 TimeoutChecker

`mc/runtime/timeout_checker.py` observa:

- `tasks:listByStatus(status=in_progress)`
- `tasks:listByStatus(status=review)`
- Poll: 60s

Responsabilidade:

- marcar stalled
- escalar review timeout

Ele tambem escreve:

- `tasks:markStalled`
- `activities:create`
- `messages:create`

## 3. Quais Estados Sao Observados Por Status

### Tasks observadas por status

- `inbox`
  - `InboxWorker`
- `planning`
  - `PlanningWorker`
- `assigned`
  - `TaskExecutor`
- `in_progress`
  - `KickoffResumeWorker`
  - `PlanNegotiationSupervisor`
  - `TimeoutChecker`
- `review`
  - `ReviewWorker`
  - `PlanNegotiationSupervisor`
  - `TimeoutChecker`

### Steps observados

Nao existe um subscription loop dedicado a `steps:listByStatus`.

Os steps sao lidos sob demanda por:

- `KickoffResumeWorker`
- `StepDispatcher`
- mutations de `steps.ts`

Isso significa que o runtime de steps e menos "reativo por status" e mais
"reativo por task em in_progress".

### Messages observadas

- `MentionWatcher` le mensagens recentes do usuario globalmente
- `AskUserReplyWatcher` le mensagens por task para pending asks
- `ConversationService` classifica mensagens quando algum watcher a entrega

## 4. Quem Escreve Estado Concorrentemente

## 4.1 Escritores de `task.status`

### Python via bridge

- `InboxWorker`
  - `inbox -> planning`
  - `inbox -> assigned`
  - workflow em alguns casos -> `review`
- `PlanningWorker`
  - `planning -> review`
  - `planning -> failed`
  - em modo autonomo materializa e kick-off
- `TaskExecutor`
  - `assigned -> in_progress`
  - `in_progress -> review/done/crashed`
- `StepDispatcher`
  - ao final pode escrever `review/done/crashed`
- `KickoffResumeWorker`
  - nao muda status diretamente na maioria dos casos, mas dispara materializacao/dispatch
- `TimeoutChecker`
  - escreve `stalledAt`, mensagens e atividades
- `task_requeue.py`
  - requeue de cron para `assigned`

### Convex mutations / UI

- `tasks:approveAndKickOff`
  - `review(awaitingKickoff) -> in_progress`
- `tasks:pauseTask`
  - `in_progress -> review`
- `tasks:resumeTask`
  - `review -> in_progress`
- `tasks:approve`
  - `review -> done`
- `tasks:returnToLeadAgent`
  - `review -> inbox`
- `tasks:retry`
  - `crashed/failed -> retrying -> in_progress`
  - ou `-> inbox`
- `tasks:manualMove`
  - manual tasks podem pular o state machine
- `steps:updateStatus`
  - reconcilia `task.status` pai

### Conclusao

`task.status` nao tem owner unico.

Ele e escrito por:

- Python workers
- Convex task mutations
- Convex step mutations que reconciliam a task pai

Esse e o principal fator estrutural de race condition.

## 4.2 Escritores de `step.status`

### Python via bridge

- `PlanMaterializer`
  - cria steps
- `StepDispatcher`
  - `assigned -> running`
  - gate/human -> `waiting_human`
  - erros -> `crashed`
- `StepRepository.check_and_unblock_dependents`
  - `blocked -> assigned`

### Convex/UI

- `steps:updateStatus`
  - transicao generica
- `steps:acceptHumanStep`
  - `waiting_human -> running`
- `steps:manualMoveStep`
  - move manual para humano/gate
- `steps:checkAndUnblockDependents`
  - desbloqueia e atribui dependentes

## 4.3 Escritores de `messages`

- `messages:create`
- `messages:postStepCompletion`
- `messages:postLeadAgentMessage`
- `postMentionMessage`
- `sendThreadMessage`
- `TimeoutChecker`
- `task_requeue.py`
- mention handler
- executor
- review actions

Como nao ha idempotency key, `messages` e uma das tabelas mais expostas a duplicacao.

## 5. Como O Sistema Detecta Mudanca De Estado Na Pratica

O sistema detecta mudanca de estado por tres mecanismos.

### 5.1 Polling por status

Exemplo:

- task entrou em `planning`
- no proximo poll do `PlanningWorker`, ela aparece na lista
- o worker decide o que fazer

Isso nao detecta a transicao em si.
Detecta apenas que "no snapshot atual a task esta em planning".

### 5.2 Polling por lista global de mensagens

Exemplo:

- usuario postou `@agente`
- `MentionWatcher` varre mensagens recentes
- se encontrar mensagem nao vista, reage

Isso tambem nao e event-driven.
E leitura repetida com dedup em memoria.

### 5.3 Leitura sob demanda apos mutation

Exemplo:

- `steps:updateStatus` le task pai e todos os steps
- reconciliacao de parent status e feita no handler

Esse mecanismo mistura escrita e reconciliacao no mesmo ponto.

## 6. Onde Ha Stale Reads

### 6.1 Polling por snapshots de listas

Qualquer loop que usa `tasks:listByStatus` pode tomar decisao com base em
um snapshot ja antigo alguns segundos.

Exemplos:

- `ReviewWorker` ve task em `review`
- antes de reagir, usuario ja clicou `approveAndKickOff`
- o worker ainda executa logica de review baseada em estado velho

### 6.2 Releituras locais apos escrita paralela

`steps:updateStatus`:

- le o step atual
- patcha o step
- relê task e steps
- reconcilia task pai

Se o dispatcher ou UI mexerem na task no mesmo intervalo, a reconciliacao pode
reescrever um parent status com base numa visao intermediaria.

### 6.3 Materializacao incremental no kickoff

`KickoffResumeWorker` detecta task `in_progress` com `executionPlan` e steps.

Ele pode:

- materializar novos steps em cima dos existentes
- disparar dispatch

Se o plano foi editado perto do mesmo instante em que o dispatcher fecha grupo
paralelo, ha risco de sobreposicao entre:

- "plan changed"
- "resume detectado"
- "dispatch finalizando"

### 6.4 Watchers de mensagem sobre a mesma thread

A mesma thread pode ser lida por:

- mention watcher
- ask-user watcher
- plan negotiation loop

Se a classificacao nao for bem mutuamente exclusiva, a mensagem pode ser
interpretada por mais de um caminho.

## 7. Onde Ha Duplicate Processing

### 7.1 `_known_*` e `_seen_*` sao apenas memoria local

Se o gateway reiniciar:

- tasks em `assigned` podem ser re-picked
- mensagens recentes podem ser reprocessadas
- review loops podem reacender

### 7.2 Mutation retry sem idempotencia

O bridge faz retry de mutation em `mc/bridge/__init__.py`.

Se ocorrer:

- mutation aplicada no servidor
- timeout/rede falha no cliente

a tentativa seguinte pode:

- criar mensagem duplicada
- criar atividade duplicada
- reaplicar patch de status

### 7.3 Overlap deliberado do MentionWatcher

O mention watcher usa overlap de 30s.

Isso ajuda contra drift de clock, mas aumenta a dependencia da deduplicacao local.
Sem dedup persistida, esse overlap pode reprocessar mensagens apos restart.

### 7.4 Review + plan negotiation observando o mesmo status

`review` e observado ao mesmo tempo por:

- `ReviewWorker`
- `PlanNegotiationSupervisor`
- `TimeoutChecker`

Cada um pode responder ao mesmo estado com efeitos diferentes.

## 8. Onde Ha Escrita Concorrente Real

### 8.1 `task.status` vindo de `steps:updateStatus` e do dispatcher

O dispatcher ao final decide:

- `crashed`
- `done`
- `review`

Mas `steps:updateStatus` tambem reconcilia task pai ao longo do caminho.

Isso cria duas autoridades parciais:

- autoridade incremental de step
- autoridade final de dispatcher

### 8.2 `pauseTask` vs dispatcher

`pauseTask` move `task.status` para `review`, mas nao cancela steps em execucao.

O dispatcher so checa `task.status` antes de despachar novos passos.

Logo:

- steps em andamento podem concluir depois do pause
- seus updates ainda podem reconciliar task/plan

Isso nao e necessariamente bug, mas e uma janela clara de concorrencia.

### 8.3 `sendThreadMessage` limpa plano enquanto loops observam status

`sendThreadMessage` em task nao manual:

- move para `assigned`
- redefine `assignedAgent`
- limpa `executionPlan`

Se isso acontecer enquanto:

- `PlanNegotiationSupervisor` observa `review/in_progress`
- `KickoffResumeWorker` observa `in_progress`
- `StepDispatcher` fecha grupo

ha troca brusca de ownership sem handshake explicito.

### 8.4 `returnToLeadAgent` nao aciona o Lead Agent imediatamente

Ela move a task para `inbox`.

Depois disso:

- `InboxWorker` volta a processar
- a task pode ir para `planning` ou `assigned`

Isso e um segundo salto assincromo em cima do mesmo objeto.

### 8.5 `retryTask` altera task e steps em bloco, mas depois recoloca em `in_progress`

O retry:

- patcha task para `retrying`
- reseta steps
- insere mensagem
- patcha task de novo para `in_progress`

Observers de `in_progress` podem pegar a task entre esses estados, dependendo do timing.

## 9. Onde O Convex Ja Esta Rigoroso

Nem tudo esta frouxo. Existem bons sinais.

### 9.1 Validacao de transicao em `steps:updateStatus`

`steps.ts` faz:

- valida status
- valida transicao
- trata no-op para step deletado

### 9.2 `steps:batchCreate` resolve dependencias atomicas

O processo de criar steps e depois resolver `blockedBy` fica numa mutation so.

### 9.3 `messages` separam `postMentionMessage` de `sendThreadMessage`

O modelo ja distingue:

- mencao de thread
- delegacao operacional

Conceitualmente isso e bom.

### 9.4 Workflow compiler marca `generatedBy = workflow`

Isso permite ao runtime diferenciar:

- plano do Lead Agent
- plano compilado de workflow

## 10. Onde O Convex Ainda Nao E Source Of Truth Forte O Bastante

### 10.1 A decisao de "quem pega o trabalho" esta no Python

Hoje o Convex guarda `status`, mas nao guarda um claim forte de processamento.

Nao existe algo como:

- `claimedBy`
- `claimedAt`
- `claimLeaseExpiresAt`
- `processingEpoch`

Sem isso, o runtime depende de memoria local para evitar double pickup.

### 10.2 A semantica de transicao esta duplicada

`dashboard/convex/lib/taskLifecycle.ts` duplica o state machine em vez de usar
sempre `shared/workflow/workflow_spec.json`.

Se o contrato diverge, o runtime pode aceitar ou rejeitar caminhos diferentes.

### 10.3 `task.status` nao tem mutation unica como gatekeeper

Existe `tasks:updateStatus`, mas varias mutacoes especiais contornam a ideia de
"uma unica porta de transicao".

Seria mais rigido se toda mudanca de task passasse por um unico ponto com:

- expected current status
- actor
- reason
- idempotency key
- version check

### 10.4 Side effects nao sao idempotentes

Atividades e mensagens sao criadas em varios pontos sem chave natural unica.

## 11. Riscos Concretos De Race Condition

### Risco A: double pickup apos restart

Sintoma:

- task em `assigned` ou mensagem recente e reprocessada

Causa:

- dedup apenas em memoria

### Risco B: duplicate message/activity

Sintoma:

- thread ou feed com entradas repetidas

Causa:

- retry de mutation sem idempotencia

### Risco C: parent task status "saltando"

Sintoma:

- task muda de `review` para `in_progress` ou `done` de forma inesperada

Causa:

- dispatcher, `steps:updateStatus`, UI e review actions escrevendo o mesmo campo

### Risco D: plano sendo limpo enquanto runtime ainda opera em cima dele

Sintoma:

- task reassign via thread e workers ainda olhando estado anterior

Causa:

- `sendThreadMessage` limpa `executionPlan` sem handshake com loops vivos

### Risco E: mesma mensagem user acionando mais de um caminho

Sintoma:

- mention + ask-user reply + plan negotiation competindo

Causa:

- multiplos watchers sobre `messages`

## 12. Oportunidades Para Tornar O Convex Mais Rigido

## 12.1 Introduzir claim persistido por task

Para tasks orientadas a worker, adicionar campos como:

- `runtimeOwner`
- `runtimeLeaseId`
- `runtimeLeaseExpiresAt`
- `stateVersion`

Fluxo:

1. worker observa task elegivel
2. worker chama mutation `tasks:claimForWorker`
3. mutation so concede se:
   - status esperado ainda confere
   - lease atual nao existe ou expirou
4. o resto do pipeline usa esse claim

Isso remove a dependencia de `_known_*`.

## 12.2 Introduzir transicoes compare-and-set

Toda mutacao de state machine deveria receber:

- `expectedStatus`
- `expectedVersion`
- `actor`
- `reason`
- `idempotencyKey`

Se o estado nao confere, falha.

Isso reduz:

- lost update
- stale write
- "eu achei que ainda estava em review"

## 12.3 Centralizar task lifecycle em uma unica mutation

Recomendacao:

criar uma mutation interna unica, por exemplo:

- `tasks:transition`

Responsabilidades:

- validar transicao
- validar expected state/version
- atualizar status
- gravar activity
- gravar side effects obrigatorios

Outras mutations como:

- `approveAndKickOff`
- `pauseTask`
- `resumeTask`
- `returnToLeadAgent`

passariam a compor essa mutation, nao a reimplementar semantica.

## 12.4 Idempotency key para mensagens e atividades

Toda escrita com side effect deveria aceitar `idempotencyKey`.

Exemplos:

- `messages:create`
- `messages:postStepCompletion`
- `messages:postLeadAgentMessage`
- `activities:create`

Chaves naturais possiveis:

- `taskId + stepId + eventKind + attempt`
- `sessionId + seq`
- `taskId + messageKind + sourceMessageId`

## 12.5 Declarar ownership claro do parent task status

Escolher um modelo:

### Modelo 1: task status e derivado dos steps

- dispatcher nao seta `done/review/crashed`
- Convex calcula a partir de steps + policy

### Modelo 2: task status e autoritativo e steps nao o reconciliam

- `steps:updateStatus` nao mexe na task pai
- apenas publica fatos
- uma unica mutation/worker decide o parent status

Hoje o sistema tenta usar os dois modelos ao mesmo tempo.

## 12.6 Separar "message", "command" e "reply"

Hoje `messages` carrega ao mesmo tempo:

- conversa
- comando indireto
- aprovacao
- mention
- reply de ask-user

Para reduzir ambiguidade, considerar tabelas ou tipos mais rigidos:

- `threadMessages`
- `taskCommands`
- `executionReplies`

ou ao menos um `messageIntent` persistido no momento da escrita.

## 12.7 Unificar state machine com `shared/workflow`

`taskLifecycle.ts` e `workflow_spec.json` precisam convergir.

Enquanto houver duas fontes, o Convex nao e um source of truth forte.

## 12.8 Trocar polling por filas de comando quando o evento for critico

Nem todo caso precisa sair do polling.

Mas para caminhos sensiveis, vale considerar tabelas de comando:

- `taskClaims`
- `dispatchCommands`
- `reviewCommands`
- `conversationCommands`

Workers passariam a consumir comandos explicitamente, em vez de inferir tudo
apenas a partir de snapshots de `status`.

## 13. Recomendacao Pragmatica De Sequencia

Se a meta e endurecer sem reescrever tudo:

### Fase 1

- adicionar `stateVersion` em `tasks` e `steps`
- adicionar `idempotencyKey` em mensagens/atividades criticas
- unificar task transitions em mutation unica interna

### Fase 2

- introduzir `claimForWorker` persistido
- remover dependencia dos sets `_known_*`

### Fase 3

- decidir owner unico do parent task status
- parar de ter dispatcher e `steps:updateStatus` reconciliando o mesmo campo

### Fase 4

- separar command stream de thread stream
- remover ambiguidade entre mention, delegacao e follow-up

## 14. Conclusao

O problema central nao e "falta de Convex".
O problema central e "Convex guarda o estado, mas ainda nao arbitra ownership e
idempotencia com rigidez suficiente".

Hoje o runtime usa Convex como:

- store de estado
- superficie de leitura por polling
- superficie de escrita com validacoes locais

Para reduzir race condition, o Convex precisa evoluir para:

- guardiao unico de transicao
- concedente de claims
- registrador de side effects idempotentes
- dono explicito da versao do estado

Sem isso, cada melhoria local em workers Python ainda vai conviver com:

- stale snapshots
- duplicacao apos restart
- retries sem idempotencia
- reconciliação concorrente entre task e step
