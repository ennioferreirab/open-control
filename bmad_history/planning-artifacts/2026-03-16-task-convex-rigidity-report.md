# Task Flow, State Capture, Dispatch, And Convex Rigidity Report

## Objetivo

Este relatorio consolida o mapeamento de:

- criacao e lifecycle de `tasks`
- diferencas entre task comum, task manual e task de workflow
- como `executionPlan` vira `steps`
- como o runtime captura estado hoje
- como o paralelismo e o dispatch funcionam
- como `review`, `thread`, `@mention` e delegacao convivem
- onde existem janelas de corrida
- como endurecer o Convex para virar a autoridade rigida do lifecycle

Este documento cruza o que foi mapeado em:

- [_bmad-output/planning-artifacts/2026-03-16-task-usercase-flow-map.md](/Users/ennio/Documents/nanobot-ennio/_bmad-output/planning-artifacts/2026-03-16-task-usercase-flow-map.md)
- [_bmad-output/planning-artifacts/2026-03-16-runtime-state-capture-and-race-report.md](/Users/ennio/Documents/nanobot-ennio/_bmad-output/planning-artifacts/2026-03-16-runtime-state-capture-and-race-report.md)

## Resumo Executivo

O desenho atual ainda nao trata o Convex como o dono absoluto do lifecycle.
Hoje o runtime funciona como um conjunto de loops Python que fazem polling de
snapshots por `status` e reagem em paralelo a esses snapshots.

Isso gera 5 propriedades estruturais:

1. O runtime observa listas por status, nao transicoes atomicas.
2. `task.status` e `step.status` possuem multiplos escritores.
3. A deduplicacao de processamento e local em memoria, nao global no banco.
4. Parte do significado do estado esta implicitamente derivada de campos auxiliares.
5. A UI e o runtime compartilham conceitos com semanticas diferentes.

As 4 ambiguidades mais perigosas hoje sao:

1. `@mention` parece delegacao, mas no codigo e apenas resposta de thread.
2. `review` representa pelo menos 3 estados de negocio diferentes.
3. `task` e `step` compartilham partes do lifecycle, mas com owners diferentes.
4. o pai (`task`) e reconciliado tanto pelo runtime Python quanto por mutations Convex.

Se a meta e reduzir race conditions, o sistema precisa migrar de:

- "polling por status + writers concorrentes"

para:

- "transicoes explicitamente comandadas e validadas no Convex, com versionamento,
  claim persistido e idempotencia"

## 1. Entidades E Owners

### 1.1 Task

`tasks` e a unidade top-level do lifecycle.

Store principal:

- [dashboard/convex/schema.ts](/Users/ennio/Documents/nanobot-ennio/dashboard/convex/schema.ts)

Mutacoes e helpers mais relevantes:

- [dashboard/convex/tasks.ts](/Users/ennio/Documents/nanobot-ennio/dashboard/convex/tasks.ts)
- [dashboard/convex/lib/taskMetadata.ts](/Users/ennio/Documents/nanobot-ennio/dashboard/convex/lib/taskMetadata.ts)
- [dashboard/convex/lib/taskPlanning.ts](/Users/ennio/Documents/nanobot-ennio/dashboard/convex/lib/taskPlanning.ts)
- [dashboard/convex/lib/taskStatus.ts](/Users/ennio/Documents/nanobot-ennio/dashboard/convex/lib/taskStatus.ts)
- [dashboard/convex/lib/taskReview.ts](/Users/ennio/Documents/nanobot-ennio/dashboard/convex/lib/taskReview.ts)
- [dashboard/convex/lib/taskLifecycle.ts](/Users/ennio/Documents/nanobot-ennio/dashboard/convex/lib/taskLifecycle.ts)

Campos mais importantes para fluxo:

- `status`
- `assignedAgent`
- `executionPlan`
- `awaitingKickoff`
- `isManual`
- `workMode`
- `trustLevel`
- `reviewers`
- `sourceAgent`
- `activeCronJobId`

### 1.2 Step

`steps` sao unidades materializadas de execucao.

Store principal:

- [dashboard/convex/schema.ts](/Users/ennio/Documents/nanobot-ennio/dashboard/convex/schema.ts)

Mutacoes e runtime:

- [dashboard/convex/steps.ts](/Users/ennio/Documents/nanobot-ennio/dashboard/convex/steps.ts)
- [dashboard/convex/lib/stepLifecycle.ts](/Users/ennio/Documents/nanobot-ennio/dashboard/convex/lib/stepLifecycle.ts)
- [mc/contexts/planning/materializer.py](/Users/ennio/Documents/nanobot-ennio/mc/contexts/planning/materializer.py)
- [mc/contexts/execution/step_dispatcher.py](/Users/ennio/Documents/nanobot-ennio/mc/contexts/execution/step_dispatcher.py)

Campos mais importantes para fluxo:

- `status`
- `assignedAgent`
- `blockedBy`
- `parallelGroup`
- `workflowStepType`
- `reviewSpecId`
- `onRejectStepId`

### 1.3 Thread / Conversation

O journal da task vive em `messages`.

Arquivos principais:

- [dashboard/convex/messages.ts](/Users/ennio/Documents/nanobot-ennio/dashboard/convex/messages.ts)
- [mc/contexts/conversation/intent.py](/Users/ennio/Documents/nanobot-ennio/mc/contexts/conversation/intent.py)
- [mc/contexts/conversation/service.py](/Users/ennio/Documents/nanobot-ennio/mc/contexts/conversation/service.py)
- [mc/contexts/conversation/mentions/watcher.py](/Users/ennio/Documents/nanobot-ennio/mc/contexts/conversation/mentions/watcher.py)
- [mc/contexts/conversation/mentions/handler.py](/Users/ennio/Documents/nanobot-ennio/mc/contexts/conversation/mentions/handler.py)

### 1.4 Runtime Boundary

O boundary Python para Convex e:

- [mc/bridge/__init__.py](/Users/ennio/Documents/nanobot-ennio/mc/bridge/__init__.py)
- [mc/bridge/subscriptions.py](/Users/ennio/Documents/nanobot-ennio/mc/bridge/subscriptions.py)
- [mc/bridge/repositories/tasks.py](/Users/ennio/Documents/nanobot-ennio/mc/bridge/repositories/tasks.py)
- [mc/bridge/repositories/steps.py](/Users/ennio/Documents/nanobot-ennio/mc/bridge/repositories/steps.py)
- [mc/bridge/repositories/messages.py](/Users/ennio/Documents/nanobot-ennio/mc/bridge/repositories/messages.py)

## 2. Regra Basica: Task Nao E Step

`task` e a unidade de intencao e lifecycle do usuario.
`step` e a unidade concreta de execucao materializada.

Consequencias praticas:

- `task.status = review` nao significa que existe `review step`
- `workflowStepType = review` nao e `task.status = review`
- uma task pode estar em `in_progress` enquanto um step esta em `waiting_human`
- a task pode existir sem `steps`, apenas com `executionPlan`

Esse desacoplamento e necessario, mas hoje parte do sistema mistura os dois
niveis ao reconciliar o pai com base no estado dos filhos.

## 3. User Cases Principais

### 3.1 Criacao De Task Comum

Entrada:

- `tasks.create` -> `createTask()`

Comportamento:

- cria a task em `inbox`
- pode preservar `assignedAgent` se nao for manual
- define `trustLevel`
- define `supervisionMode`

Dois caminhos:

#### A. Sem `assignedAgent`

Fluxo:

1. `tasks.create`
2. task entra em `inbox`
3. [mc/runtime/workers/inbox.py](/Users/ennio/Documents/nanobot-ennio/mc/runtime/workers/inbox.py) move para `planning`
4. [mc/runtime/workers/planning.py](/Users/ennio/Documents/nanobot-ennio/mc/runtime/workers/planning.py) chama o planner
5. [mc/contexts/planning/planner.py](/Users/ennio/Documents/nanobot-ennio/mc/contexts/planning/planner.py) gera `executionPlan`
6. ou:
   - materializa e despacha
   - ou move para `review + awaitingKickoff`

#### B. Com `assignedAgent`

Fluxo:

1. `tasks.create`
2. task entra em `inbox`
3. inbox worker move direto para `assigned`
4. [mc/contexts/execution/executor.py](/Users/ennio/Documents/nanobot-ennio/mc/contexts/execution/executor.py) pega a task

Semantica:

- esse caminho e "delegacao direta"
- nao e o mesmo fluxo de "planejar em steps"

### 3.2 Criacao De Task Manual

Entrada:

- `tasks.create` com `isManual = true`

Comportamento:

- `assignedAgent` e removido
- `trustLevel` vira `autonomous`
- `supervisionMode` vira `autonomous`
- o `InboxWorker` ignora essa task

Ela depende de comandos explicitos:

- salvar plano
- `startInboxTask`
- `manualMove`
- `clearExecutionPlan`

Semantica:

- task manual nao passa pelo pipeline automatico do Lead Agent por default

### 3.3 Criacao De Task De Workflow

Entrada:

- `tasks.launchMission`

Arquivos:

- [dashboard/convex/lib/squadMissionLaunch.ts](/Users/ennio/Documents/nanobot-ennio/dashboard/convex/lib/squadMissionLaunch.ts)
- [dashboard/convex/lib/workflowExecutionCompiler.ts](/Users/ennio/Documents/nanobot-ennio/dashboard/convex/lib/workflowExecutionCompiler.ts)

Fluxo:

1. valida `squadSpec`
2. valida `workflowSpec`
3. resolve agentes
4. compila workflow em `executionPlan`
5. cria task com:
   - `status = planning`
   - `workMode = ai_workflow`
   - `executionPlan.generatedBy = workflow`

Semantica:

- o plano nao nasce do Lead Agent
- o planner LLM precisa ser pulado
- o runtime faz esse bypass em:
  - [mc/runtime/workers/inbox.py](/Users/ennio/Documents/nanobot-ennio/mc/runtime/workers/inbox.py)
  - [mc/runtime/workers/planning.py](/Users/ennio/Documents/nanobot-ennio/mc/runtime/workers/planning.py)

## 4. Onde O Lead Agent Atua E Onde Nao Atua

### 4.1 Onde Atua

O Lead Agent so e dono de:

- planejamento
- geracao de `executionPlan`
- negociacao de plano
- mensagens `lead_agent_plan`
- mensagens `lead_agent_chat`

Arquivos:

- [mc/contexts/planning/planner.py](/Users/ennio/Documents/nanobot-ennio/mc/contexts/planning/planner.py)
- [mc/runtime/workers/planning.py](/Users/ennio/Documents/nanobot-ennio/mc/runtime/workers/planning.py)
- [mc/contexts/planning/negotiation.py](/Users/ennio/Documents/nanobot-ennio/mc/contexts/planning/negotiation.py)
- [dashboard/convex/messages.ts](/Users/ennio/Documents/nanobot-ennio/dashboard/convex/messages.ts)

### 4.2 Onde Nao Atua

O Lead Agent explicitamente nao deve:

- responder a `@mention`
- ser dono de step
- executar task diretamente

Sinais concretos:

- o planner proibe steps no `lead-agent`
- [mc/contexts/conversation/mentions/handler.py](/Users/ennio/Documents/nanobot-ennio/mc/contexts/conversation/mentions/handler.py) bloqueia `@lead-agent`
- [mc/contexts/execution/step_dispatcher.py](/Users/ennio/Documents/nanobot-ennio/mc/contexts/execution/step_dispatcher.py) reroteia steps atribuídos a ele
- [mc/contexts/execution/executor_routing.py](/Users/ennio/Documents/nanobot-ennio/mc/contexts/execution/executor_routing.py) intercepta tasks assigned ao lead-agent

## 5. Como O Estado E Capturado Hoje

### 5.1 ConvexBridge

O bridge expõe `query`, `mutation` e polling deduplicado.

Problemas relevantes:

- retry generico de mutation
- sem `idempotencyKey`
- sem compare-and-set por versao

Impacto:

- `messages:create`, `activities:create`, `tasks:updateStatus`, `steps:updateStatus`
  podem duplicar efeitos em cenarios de falha parcial

### 5.2 SubscriptionManager

[mc/bridge/subscriptions.py](/Users/ennio/Documents/nanobot-ennio/mc/bridge/subscriptions.py)
implementa `async_subscribe()` por polling, nao por stream de transicoes.

Propriedades:

- observa snapshots
- compara com `last_result`
- emite quando o resultado inteiro muda

Impacto:

- transicoes intermediarias podem sumir entre polls
- reinicio perde deduplicacao local
- loops diferentes podem reagir ao mesmo estado em tempos diferentes

### 5.3 Loops Runtime

O gateway sobe varios loops independentes:

- inbox loop
- planning loop
- review loop
- kickoff/resume loop
- assigned execution loop
- plan negotiation loops
- mention watcher
- ask-user watcher
- timeout checker

Arquivos:

- [mc/runtime/gateway.py](/Users/ennio/Documents/nanobot-ennio/mc/runtime/gateway.py)
- [mc/runtime/orchestrator.py](/Users/ennio/Documents/nanobot-ennio/mc/runtime/orchestrator.py)

Todos observam estados por polling de status, ou `messages` globais.

### 5.4 Deduplicacao

A deduplicacao e local ao processo:

- `_known_inbox_ids`
- `_known_planning_ids`
- `_known_review_task_ids`
- `_known_kickoff_ids`
- `_known_assigned_ids`
- `_processed_signatures`
- `_seen_message_ids`

Impacto:

- restart zera conhecimento
- multi-processo nao compartilha claims
- mesma entidade pode ser reprocessada

## 6. Como O Dispatch E O Paralelismo Funcionam

### 6.1 Materializacao

[mc/contexts/planning/materializer.py](/Users/ennio/Documents/nanobot-ennio/mc/contexts/planning/materializer.py)
faz:

1. valida deps do plano em memoria
2. chama `steps:batchCreate`
3. opcionalmente chama `tasks:kickOff`

Em Convex, `steps:batchCreate` e two-phase:

1. cria todos os steps
2. resolve `blockedBy` reais e faz patch

Isso serializa a materializacao, mas nao serializa:

- kickoff
- dispatch
- a reconciliacao posterior do pai

### 6.2 Dispatch

[mc/contexts/execution/step_dispatcher.py](/Users/ennio/Documents/nanobot-ennio/mc/contexts/execution/step_dispatcher.py)
opera assim:

1. verifica se `task.status == in_progress`
2. le todos os steps
3. seleciona steps `assigned`
4. agrupa por `parallelGroup`
5. executa o menor grupo com `asyncio.gather`
6. repete

Caracteristicas:

- paralelismo e por nivel
- nao e work-stealing
- um grupo faz barreira para o proximo

### 6.3 Pause / Resume

Pause:

- `pauseTask` faz `in_progress -> review`
- nao cancela work ja iniciado
- apenas impede novos dispatches

Resume:

- `resumeTask` faz `review -> in_progress`
- o `KickoffResumeWorker` detecta isso depois por polling

Impacto:

- `pause` nao e stop forte
- `resume` nao e transacao de retomada
- e um "toggle de status + watcher"

### 6.4 Gates Humanos

Dois comportamentos diferentes:

- `workflow gate` (`human` / `checkpoint`) vira `waiting_human`
- `step assigned to human` fica `assigned` e o dispatcher pula

Impacto:

- "esperando humano" e representado de duas formas
- isso aumenta branching na UI e no runtime

### 6.5 Unblocking

Dependentes so desbloqueiam quando todos os blockers estao `completed`.

Quem faz isso:

- `steps.updateStatus`
- `steps.manualMoveStep`
- `steps.checkAndUnblockDependents`

Impacto:

- o unblocking esta acoplado ao mutation path
- uma acao humana no step e tambem reconciliacao do grafo

## 7. Review Hoje Nao E Um Estado So

`review` hoje representa pelo menos 3 coisas:

### 7.1 Review Pre-Kickoff

Condicao:

- `task.status = review`
- `awaitingKickoff = true`

Significa:

- plano pronto
- usuario ainda nao iniciou

### 7.2 Review-Pause

Condicao:

- `task.status = review`
- `awaitingKickoff = false`
- existem steps nao concluidos

Significa:

- task pausada
- dispatcher nao deve abrir novas execucoes

### 7.3 Review Final

Condicao:

- task terminou execucao
- aguarda aprovacao/negação/retorno

Significa:

- e o review "de negocio"

Impacto:

- a mesma coluna e o mesmo status modelam 3 significados
- o dashboard depende de inferencia por flags
- o runtime tambem depende de inferencia por flags

## 8. Thread, Mention, Follow-Up E Delegacao

### 8.1 `postUserReply`

Apenas conversa.

Efeito:

- grava `messages`
- grava `activities`
- pode responder `executionQuestion`

Nao muda:

- `task.status`
- `assignedAgent`
- `executionPlan`

### 8.2 `postMentionMessage`

So conversa assistida.

Fluxo:

- grava a mensagem
- MentionWatcher detecta
- ConversationService classifica `MENTION`
- `handle_all_mentions()` roda agente e posta resposta

Nao muda:

- `task.status`
- `assignedAgent`
- `executionPlan`

Esse e o ponto central de UX:

- parece delegacao
- no codigo e one-shot thread reply

### 8.3 `sendThreadMessage`

Esse e o reassignment operacional real.

Efeito:

- grava mensagem
- `task.status -> assigned`
- seta `assignedAgent`
- grava `previousStatus`
- limpa `executionPlan`
- limpa `stalledAt`

Esse fluxo e drasticamente diferente de `@mention`.

### 8.4 `postUserPlanMessage`

Esse e o canal canonico para falar com o Lead Agent sobre plano.

Efeito:

- mantem plano
- nao delega a task
- pode reabrir task concluida para `review`

### 8.5 `FOLLOW_UP`

O intent existe, mas o `ConversationService` nao faz o roteamento final.

Impacto:

- o comportamento depende do caller
- existe risco de intermitencia funcional

## 9. Onde Estao As Corridas Mais Graves

### P1. Multi-writer em `task.status`

Escritores reais de `task.status` hoje:

- `InboxWorker`
- `PlanningWorker`
- `TaskExecutor`
- `StepDispatcher`
- `steps.updateStatus`
- `manualMoveStep`
- `pauseTask`
- `resumeTask`
- `approveAndKickOff`
- `retryTask`
- `returnToLeadAgent`
- cron / timeout / review flows

Impacto:

- o pai pode andar por conciliadores diferentes
- sem compare-and-set, o ultimo writer vence

### P1. Kickoff e resume por polling + assinatura local

`KickoffResumeWorker` detecta kickoff/resume olhando:

- `updatedAt`
- `generatedAt`

Impacto:

- dois writes proximos podem ser coalescidos
- um mesmo evento logico pode parecer "kickoff" ou "resume"

### P1. Pause sem cancelamento

`pauseTask` nao interrompe steps correntes.

Impacto:

- usuario entra em review
- step ainda escreve completion/crash depois
- isso disputa com a expectativa de pausa

### P1. `sendThreadMessage` compete com review/planning

`sendThreadMessage`:

- reatribui
- limpa plano

Se outro loop ainda estiver vendo `review` ou `in_progress`, ele pode agir com
uma visao antiga do mundo.

### P1. `steps.updateStatus` e dispatcher compartilham autoridade do pai

O filho atualiza o pai no Convex, e o dispatcher tambem atualiza o pai no fim
do loop.

Impacto:

- o pai nao tem um dono unico

### P2. Matching de plan-step por heuristica

Em resume incremental e no sync do `executionPlan`, o sistema associa step
materializado por:

- `order`
- `title`
- as vezes `description`

Impacto:

- duas etapas parecidas podem ser associadas errado
- edicao de plano aumenta risco

### P2. Humano/gate com semantica dupla

Hoje:

- gate workflow = `waiting_human`
- human assigned = `assigned`

Impacto:

- mesmo conceito de bloqueio humano tem dois estados

### P2. `review` com semantica tripla

Impacto:

- UI e runtime inferem subtipo de review em vez de recebê-lo explicitamente

### P3. Deduplicacao nao persistida

Impacto:

- restart pode reprocessar
- multi-instancia nao compartilha claims

## 10. Onde O Convex Ja Esta Forte E Onde Ainda Esta Fraco

### 10.1 Onde Ja Esta Forte

- schema central de entidades
- queries e mutations reativas
- read models agregados para UI
- parte das regras de transicao em TS

### 10.2 Onde Ainda Esta Fraco Como Autoridade

- ownership de transicao ainda distribuido
- sem `stateVersion`
- sem claims persistidos por worker
- sem `idempotencyKey`
- sem fila/command log explicito para runtime
- sem diferenciar semanticamente subtipos importantes do estado

## 11. Desenho-Alvo Para Tornar O Convex Rigido

### 11.1 Principio Central

Python nao deve "decidir e patchar estado derivado" por conta propria.
Python deve pedir ao Convex para:

- validar a transicao
- conceder claim
- registrar o command
- devolver a proxima unidade de trabalho

### 11.2 Mudancas Estruturais Recomendadas

#### A. `stateVersion` em task e step

Adicionar:

- `stateVersion` na task
- `stateVersion` no step

Regra:

- toda transicao incrementa versao
- runtime envia `expectedVersion`
- Convex rejeita stale write

Beneficio:

- compare-and-set
- menos lost update

#### B. Mutation unica de lifecycle

Criar algo como:

- `tasks.transition`
- `steps.transition`

Essa mutation deve:

- validar estado atual
- validar subtipo do fluxo
- aplicar patch
- registrar activity/message se necessario
- incrementar `stateVersion`

Beneficio:

- remove logica de transicao espalhada
- centraliza invariantes

#### C. Claim persistido por worker

Adicionar algo como:

- `runtimeOwner`
- `runtimeLeaseId`
- `runtimeLeaseExpiresAt`
- `dispatchGeneration`

Regra:

- worker precisa adquirir claim antes de agir
- claim expira
- outro worker nao reprocessa enquanto claim valida existir

Beneficio:

- deduplicacao global
- sobrevive restart

#### D. `idempotencyKey`

Para:

- `messages`
- `activities`
- comandos de runtime

Regra:

- mesma chave = no-op idempotente

Beneficio:

- retries ficam seguros

#### E. Subtipos explicitos de review

Em vez de inferir por flags, criar algo como:

- `reviewKind = pre_kickoff | paused | final`

ou ate separar estados mesmo:

- `review_pre_kickoff`
- `paused`
- `review_final`

Beneficio:

- UI simples
- runtime simples
- menos branching implícito

#### F. Unificar bloqueio humano

Criar um estado unico canônico:

- `waiting_human`

Regra:

- gate workflow e human-assigned usam o mesmo estado

Beneficio:

- menos casos especiais

#### G. Separar command de thread message

Hoje a UI usa texto para inferir:

- reply
- mention
- delegation
- plan chat

Melhor modelo:

- `threadMessage`
- `commandType`
- `commandPayload`

Exemplos:

- `commandType = mention`
- `commandType = delegate`
- `commandType = plan_chat`
- `commandType = reply`

Beneficio:

- intencao deixa de ser implícita
- fica audível e reprocessável

## 12. Proposta De Refactor Por Fases

### Fase 0. Endurecimento Minimo Sem Reescrever Tudo

Objetivo:

- reduzir as corridas mais provaveis com menor impacto

Mudancas:

1. adicionar `stateVersion` em task e step
2. adicionar `idempotencyKey` em messages/activities
3. criar `reviewKind`
4. tornar `@mention` e `delegate` tipos diferentes no schema
5. parar de usar matching por `order/title` para sync de plan-step

### Fase 1. Owner unico para `task.status`

Objetivo:

- remover multi-writer do pai

Opcao recomendada:

- o Convex vira o unico reconciliador do status da task
- Python apenas pede `steps.transition` e `tasks.transition`

Python nao deve fazer patch direto do pai com base em leitura local do grafo.

### Fase 2. Claims persistidos e dispatch comandado

Objetivo:

- substituir deduplicacao local por claim persistido

Mudancas:

- `taskClaims` ou campos embutidos na task
- lease por worker
- `dispatchGeneration`

### Fase 3. De polling por snapshot para command/event-driven

Objetivo:

- reduzir loops especulativos

Mudancas:

- runtime consome comandos e claims
- Convex materializa o "work queue"
- polling por status vira fallback, nao mecanismo primario

## 13. Corte Minimo Recomendado

Se o objetivo for reduzir bug rapido sem refazer o runtime inteiro, eu faria
nesta ordem:

1. separar semanticamente `postMentionMessage` de `sendThreadMessage` na UI e no schema
2. introduzir `reviewKind`
3. adicionar `stateVersion` em task/step
4. escolher um owner unico para `task.status`
5. introduzir `idempotencyKey` em `messages` e `activities`
6. persistir `planStepKey` estavel em cada step materializado

Esse corte ja atacaria:

- ambiguidade de UX
- stale writes
- retries duplicados
- sync errado entre plano e steps

## 14. Conclusao

O problema central nao e apenas "tem race condition".
O problema central e que o sistema ainda mistura 4 eixos de responsabilidade:

- conversa
- comando/delegacao
- reconciliacao de lifecycle
- observacao por polling

Enquanto isso continuar espalhado entre:

- workers Python
- mutations de task
- mutations de step
- inferencias de UI

o Convex continuara sendo um store operacional forte, mas nao uma autoridade
rigida do fluxo.

Se a meta for previsibilidade, o proximo passo arquitetural correto e:

- explicitar intencao no schema
- versionar transicoes
- persistir claims
- reduzir o numero de escritores de estado
- mover a validacao final do lifecycle para o Convex
