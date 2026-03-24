# Story: Workflow Authoring UI

## Story
As a user, I want a "Create Workflow" option in the creation dialog that opens an interactive terminal wizard, so I can design workflows from the UI.

## Status: ready-for-dev

## Context
The `CreateAuthoringDialog` currently offers "Create Agent" and "Create Squad". We need to add a third "Create Workflow" option that opens a `WorkflowAuthoringWizard` (terminal dialog running `/create-workflow-mc`). This follows the exact same pattern as the existing `SquadAuthoringWizard`.

## Acceptance Criteria
- [ ] `CreateAuthoringDialog` shows 3 options: Agent, Squad, Workflow
- [ ] "Create Workflow" button uses `GitBranch` icon with indigo accent color
- [ ] Clicking "Create Workflow" opens `WorkflowAuthoringWizard` dialog
- [ ] `WorkflowAuthoringWizard` runs `/create-workflow-mc` skill in an `AgentTerminal`
- [ ] Provider selector (claude-code/codex) works in workflow wizard
- [ ] Closing the wizard terminates the session and resets state
- [ ] Sidebar "Create" button tooltip updated to mention workflows
- [ ] `make lint && make typecheck` passes

## Tasks

- [ ] **Create `dashboard/features/agents/components/WorkflowAuthoringWizard.tsx`**
  - Copy the structure of `SquadAuthoringWizard.tsx` exactly
  - Props: `open: boolean`, `onClose: () => void`, `onPublished?: (workflowSpecId: string) => void`
  - State: `generation` (number, for scopeId uniqueness), `provider` (WizardProvider)
  - `scopeId = "create-workflow:${generation}-${reactId}"`
  - Dialog: `w-[70vw] h-[90vh]`, no interact outside, no escape key close
  - Header: "Create Workflow" title + `ProviderSelector`
  - Body: `AgentTerminal` with `agentName="nanobot"`, `provider={provider}`, `scopeId`, `prompt="/create-workflow-mc"`, `terminateOnClose`
  - `handleClose`: increment generation, call `onClose()`
  - Reference: `SquadAuthoringWizard.tsx` — copy and change title/scopeId/prompt

- [ ] **Modify `dashboard/features/agents/components/CreateAuthoringDialog.tsx`**
  - Add import: `GitBranch` from `lucide-react`
  - Add prop: `onSelectWorkflow: () => void`
  - Update `DialogDescription` text: "Choose what you want to create. Agents are individual workers; squads are reusable multi-agent teams; workflows define execution flows for squads."
  - Change grid from `grid-cols-2` to `grid-cols-3`
  - Add third button after Squad button:
    ```tsx
    <Button
      variant="outline"
      className="flex h-auto flex-col items-center gap-3 p-6"
      onClick={() => { onClose(); onSelectWorkflow(); }}
      aria-label="Create Workflow"
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-indigo-500/10">
        <GitBranch className="h-6 w-6 text-indigo-500" />
      </div>
      <div className="text-center">
        <p className="font-semibold">Create Workflow</p>
        <p className="mt-0.5 text-xs text-muted-foreground">Define an execution flow</p>
      </div>
    </Button>
    ```

- [ ] **Modify `dashboard/features/agents/components/AgentSidebar.tsx`**
  - Add import: `WorkflowAuthoringWizard` from `./WorkflowAuthoringWizard`
  - Add state: `const [showWorkflowWizard, setShowWorkflowWizard] = useState(false);`
  - Update `CreateAuthoringDialog` props — add: `onSelectWorkflow={() => setShowWorkflowWizard(true)}`
  - Add below existing wizard renders (after line ~431):
    ```tsx
    <WorkflowAuthoringWizard open={showWorkflowWizard} onClose={() => setShowWorkflowWizard(false)} />
    ```
  - Update "Create" button tooltip from "Create Agent or Squad" to "Create"
  - Update "Create" button aria-label from "Create Agent or Squad" to "Create"

## File List
- `dashboard/features/agents/components/WorkflowAuthoringWizard.tsx` (create)
- `dashboard/features/agents/components/CreateAuthoringDialog.tsx` (modify)
- `dashboard/features/agents/components/AgentSidebar.tsx` (modify)

## Dev Notes
- **`WorkflowAuthoringWizard` is nearly identical to `SquadAuthoringWizard`.** The only differences: title is "Create Workflow", scopeId prefix is "create-workflow:", prompt is "/create-workflow-mc".
- **`ProviderSelector` and `AgentTerminal`** are existing components — import from same location as SquadAuthoringWizard.
- **`GitBranch`** is available in lucide-react (verify with: `grep -r "GitBranch" node_modules/lucide-react/`).
- **Color scheme:** Agent = blue-500, Squad = violet-500, Workflow = indigo-500.
- **Grid layout:** `grid-cols-3` may need `sm:max-w-lg` or `sm:max-w-xl` on DialogContent instead of `sm:max-w-md` to fit 3 columns comfortably.

## Testing Standards
- Follow `agent_docs/running_tests.md` decision tree
- Visual verification: start stack, click Create, verify 3 options display correctly
- Functional verification: click Create Workflow, verify terminal opens with correct prompt

## Dev Agent Record
- Model: (to be filled by dev agent)
- Completion notes: (to be filled by dev agent)
- Files modified: (to be filled by dev agent)
