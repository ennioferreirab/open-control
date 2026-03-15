# Provider CLI Live Observability And Intervention Checklist

**Date:** 2026-03-15

Use este checklist antes de considerar o live control do `provider-cli` pronto.

## Backend Eventing (Story 28-18)

- [x] sessões `provider-cli` gravam eventos via LiveStreamProjector (Story 28-18)
- [x] eventos incluem texto, falha e lifecycle mínimo (Story 28-18)
- [x] tool calls aparecem como eventos operacionais, não chain-of-thought (Story 28-18)
- [x] sequência por sessão é monotônica (Story 28-18)
- [x] projeção usa supervision_sink callback (Story 28-18)

## Session Metadata (Story 28-19)

- [x] ProviderSessionRecord guarda status real da sessão (Story 28-19)
- [x] ProviderSessionRecord guarda último erro (last_error) (Story 28-19)
- [x] ProviderSessionRecord guarda bootstrap prompt (Story 28-19)
- [x] ProviderSessionRecord guarda provider session id quando houver (Story 28-19)
- [x] ProviderSessionRecord guarda diagnóstico do último comando (Story 28-22)

## Control Plane (Stories 28-20, 28-22)

- [x] existe caminho backend real para `interrupt` (Story 28-20)
- [x] existe caminho backend real para `stop` (Story 28-20)
- [x] `resume` é implementado via HumanInterventionController (Story 28-20)
- [x] intervenção muda registry + subprocesso via ProviderCliControlPlane (Story 28-20)
- [x] intervenção gera rastro diagnóstico persistido (Story 28-22)

## Backend E2E Proof (Story 28-21)

- [x] há teste com subprocesso real para start/stream (Story 28-21)
- [x] há teste com subprocesso real para interrupt (Story 28-21)
- [x] há teste com subprocesso real para stop (Story 28-21)
- [x] falhas terminam em estado consistente (Story 28-21)
- [x] evidência backend distingue comando solicitado, aplicado e falho (Story 28-22)

## Out Of Scope For This Stage

- [ ] dashboard/live tab não entra como critério de aceite
- [ ] botões visuais não são pré-requisito para considerar o backend pronto

## Safety

- [ ] não há exposição de chain-of-thought bruto
- [ ] inputs de tool são truncados
- [ ] erros ficam legíveis para operador
