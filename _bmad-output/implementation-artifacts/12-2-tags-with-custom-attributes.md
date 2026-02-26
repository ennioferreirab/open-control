# Story 12.2: Tags with Custom Attributes (Lightweight CRM)

Status: ready-for-dev

## Story

As a **user**,
I want tags to carry custom attributes (like client, deadline, priority) with a shared catalog of reusable attribute types,
so that I can use tags as a lightweight CRM.

## Acceptance Criteria

### AC1: Schema -- `tagAttributes` Catalog Table

**Given** the existing Convex schema
**When** the schema is extended
**Then** a new `tagAttributes` table is created:
```typescript
tagAttributes: defineTable({
  name: v.string(),
  type: v.union(v.literal("text"), v.literal("number"), v.literal("date"), v.literal("select")),
  options: v.optional(v.array(v.string())),
  createdAt: v.string(),
}).index("by_name", ["name"]),
```
**And** the table holds the shared catalog of reusable attribute definitions
**And** the `name` field is unique (case-insensitive)
**And** the `options` field is only meaningful for `type: "select"` attributes
**And** existing schema data remains unaffected

### AC2: Schema -- `tagAttributeValues` Table

**Given** the tagAttributes catalog exists
**When** the schema is extended
**Then** a new `tagAttributeValues` table is created:
```typescript
tagAttributeValues: defineTable({
  taskId: v.id("tasks"),
  tagName: v.string(),
  attributeId: v.id("tagAttributes"),
  value: v.string(),
  updatedAt: v.string(),
}).index("by_taskId", ["taskId"])
  .index("by_taskId_tagName", ["taskId", "tagName"])
  .index("by_attributeId", ["attributeId"]),
```
**And** each row represents one attribute value for one tag on one task
**And** the combination of (taskId, tagName, attributeId) is logically unique

### AC3: Tag Attribute Catalog CRUD

**Given** the tagAttributes table exists
**When** Convex mutations are created
**Then** the following are available:
- `tagAttributes.list` -- query all attribute definitions, ordered by name
- `tagAttributes.create` -- create a new attribute (validates unique name, valid type, options required for select type)
- `tagAttributes.update` -- update an attribute's name, type, or options
- `tagAttributes.remove` -- delete an attribute from the catalog AND cascade-delete all `tagAttributeValues` rows that reference it
**And** creating an attribute named "client" makes it available for ALL tags (shared catalog)

### AC4: Tag Attribute Value CRUD

**Given** the tagAttributeValues table exists
**When** Convex mutations are created
**Then** the following are available:
- `tagAttributeValues.getByTask` -- query all attribute values for a given taskId (used by TaskDetailSheet)
- `tagAttributeValues.getByTaskAndTag` -- query attribute values for a specific taskId + tagName pair
- `tagAttributeValues.upsert` -- create or update a value for a (taskId, tagName, attributeId) tuple. If a row exists for that tuple, update its value; otherwise insert a new row.
- `tagAttributeValues.removeByTaskAndTag` -- delete all attribute values for a given (taskId, tagName) pair (used when a tag is removed from a task)

### AC5: Cascade -- Removing Tag from Task Cleans Values

**Given** a task has tag "client-a" with attribute values (e.g., client=Acme, deadline=2026-03-15)
**When** the tag "client-a" is removed from the task (via existing tag removal flow)
**Then** all `tagAttributeValues` rows with that (taskId, tagName="client-a") are deleted
**And** the tagAttributes catalog itself is NOT affected (attributes remain available for other tags)

### AC6: Cascade -- Deleting Attribute from Catalog Cleans All Values

**Given** an attribute "deadline" exists in the catalog and has values across multiple tasks/tags
**When** the attribute "deadline" is deleted from the catalog via `tagAttributes.remove`
**Then** ALL `tagAttributeValues` rows referencing that attributeId are deleted (across all tasks and tags)
**And** the deletion is atomic within the Convex mutation

### AC7: Frontend -- Attribute Catalog in TagsPanel

**Given** the TagsPanel (`dashboard/components/TagsPanel.tsx`) shows the list of tags
**When** the user scrolls to the bottom of the panel
**Then** a new "Attributes" section is displayed below the tag creation form
**And** it shows the list of all defined attributes with their name and type
**And** for "select" type attributes, the options are shown as small badges
**And** each attribute has a delete button (with cascade warning)
**And** below the list, a creation form is available with:
  - Name input (text, max 32 chars)
  - Type selector (text | number | date | select)
  - Options input (only visible when type is "select", comma-separated)
  - "Add Attribute" button

### AC8: Frontend -- Tag Attributes in TaskDetailSheet

**Given** a task has tags assigned (shown in the Config tab of TaskDetailSheet)
**When** the user views the Config tab
**Then** below the tag badges (currently at lines 557-570 of `TaskDetailSheet.tsx`), an expandable section appears for each tag
**And** each tag section shows the full attribute catalog with current values (filled or empty)
**And** clicking an attribute value opens an inline editor (TagAttributeEditor component)

### AC9: Frontend -- TagAttributeEditor Component

**Given** the user clicks on an attribute value for a tag on a task
**When** the TagAttributeEditor renders
**Then** it shows the appropriate input control based on the attribute type:
  - `text`: standard text input
  - `number`: number input with step support
  - `date`: date picker input (type="date")
  - `select`: dropdown with the attribute's defined options
**And** changing the value triggers an upsert to `tagAttributeValues`
**And** the editor supports clearing a value (setting it to empty string)
**And** the UI updates optimistically (no visible delay)

### AC10: Backend Python -- Thread Context Includes Tag Attributes

**Given** the thread context builder in `nanobot/mc/thread_context.py` builds context for agent prompt injection
**When** a task has tags with attribute values
**Then** the thread context includes a `[Task Tag Attributes]` section:
```
[Task Tag Attributes]
client-a: client=Acme, deadline=2026-03-15
priority-high: level=critical
```
**And** only tags with at least one non-empty attribute value are included
**And** the section is omitted entirely if no tag attributes exist

## Tasks / Subtasks

- [ ] **Task 1: Extend Convex Schema** (AC: #1, #2)
  - [ ] 1.1 In `dashboard/convex/schema.ts`, add the `tagAttributes` table after the `taskTags` table (line ~223):
    ```typescript
    tagAttributes: defineTable({
      name: v.string(),
      type: v.union(v.literal("text"), v.literal("number"), v.literal("date"), v.literal("select")),
      options: v.optional(v.array(v.string())),
      createdAt: v.string(),
    }).index("by_name", ["name"]),
    ```
  - [ ] 1.2 Add the `tagAttributeValues` table:
    ```typescript
    tagAttributeValues: defineTable({
      taskId: v.id("tasks"),
      tagName: v.string(),
      attributeId: v.id("tagAttributes"),
      value: v.string(),
      updatedAt: v.string(),
    }).index("by_taskId", ["taskId"])
      .index("by_taskId_tagName", ["taskId", "tagName"])
      .index("by_attributeId", ["attributeId"]),
    ```
  - [ ] 1.3 Verify `npx convex dev` starts without schema errors and existing data is unaffected.

- [ ] **Task 2: Create `tagAttributes.ts` Convex Functions** (AC: #3, #6)
  - [ ] 2.1 Create `dashboard/convex/tagAttributes.ts` following the pattern of `taskTags.ts`.
  - [ ] 2.2 Implement `list` query:
    ```typescript
    export const list = query({
      args: {},
      handler: async (ctx) => {
        return await ctx.db.query("tagAttributes").withIndex("by_name").order("asc").collect();
      },
    });
    ```
  - [ ] 2.3 Implement `create` mutation:
    - Validate name is 1-32 chars, trimmed.
    - Validate type is one of "text", "number", "date", "select".
    - If type is "select", validate that options is a non-empty array.
    - Check for duplicate name (case-insensitive), throw ConvexError if duplicate.
    - Insert with `createdAt: new Date().toISOString()`.
  - [ ] 2.4 Implement `update` mutation:
    - Accept `id: v.id("tagAttributes")`, optional `name`, `type`, `options`.
    - Validate same rules as create for any provided fields.
    - If name is changed, check for duplicate.
    - If type changes to non-"select", clear options.
  - [ ] 2.5 Implement `remove` mutation with cascade:
    - Accept `id: v.id("tagAttributes")`.
    - Query all `tagAttributeValues` where `attributeId === id` using the `by_attributeId` index.
    - Delete all matching rows, then delete the attribute itself.

- [ ] **Task 3: Create `tagAttributeValues.ts` Convex Functions** (AC: #4, #5)
  - [ ] 3.1 Create `dashboard/convex/tagAttributeValues.ts`.
  - [ ] 3.2 Implement `getByTask` query:
    ```typescript
    export const getByTask = query({
      args: { taskId: v.id("tasks") },
      handler: async (ctx, { taskId }) => {
        return await ctx.db.query("tagAttributeValues")
          .withIndex("by_taskId", (q) => q.eq("taskId", taskId))
          .collect();
      },
    });
    ```
  - [ ] 3.3 Implement `getByTaskAndTag` query:
    ```typescript
    export const getByTaskAndTag = query({
      args: { taskId: v.id("tasks"), tagName: v.string() },
      handler: async (ctx, { taskId, tagName }) => {
        return await ctx.db.query("tagAttributeValues")
          .withIndex("by_taskId_tagName", (q) => q.eq("taskId", taskId).eq("tagName", tagName))
          .collect();
      },
    });
    ```
  - [ ] 3.4 Implement `upsert` mutation:
    ```typescript
    export const upsert = mutation({
      args: {
        taskId: v.id("tasks"),
        tagName: v.string(),
        attributeId: v.id("tagAttributes"),
        value: v.string(),
      },
      handler: async (ctx, { taskId, tagName, attributeId, value }) => {
        const existing = await ctx.db.query("tagAttributeValues")
          .withIndex("by_taskId_tagName", (q) => q.eq("taskId", taskId).eq("tagName", tagName))
          .collect();
        const match = existing.find((r) => r.attributeId === attributeId);
        const now = new Date().toISOString();
        if (match) {
          await ctx.db.patch(match._id, { value, updatedAt: now });
          return match._id;
        }
        return await ctx.db.insert("tagAttributeValues", {
          taskId, tagName, attributeId, value, updatedAt: now,
        });
      },
    });
    ```
  - [ ] 3.5 Implement `removeByTaskAndTag` mutation:
    ```typescript
    export const removeByTaskAndTag = mutation({
      args: { taskId: v.id("tasks"), tagName: v.string() },
      handler: async (ctx, { taskId, tagName }) => {
        const rows = await ctx.db.query("tagAttributeValues")
          .withIndex("by_taskId_tagName", (q) => q.eq("taskId", taskId).eq("tagName", tagName))
          .collect();
        for (const row of rows) {
          await ctx.db.delete(row._id);
        }
        return rows.length;
      },
    });
    ```

- [ ] **Task 4: Wire Tag Removal Cascade** (AC: #5)
  - [ ] 4.1 Locate the existing tag removal flow. Tags are stored as `string[]` on the task's `tags` field. When a tag is removed from a task (likely via `tasks.ts` update mutation or a dedicated `removeTag` mutation), add a cascade call.
  - [ ] 4.2 In the mutation that removes a tag from a task, after removing the tag name from the `tags` array, call the cascade logic:
    ```typescript
    // After removing tagName from task.tags array:
    const attrValues = await ctx.db.query("tagAttributeValues")
      .withIndex("by_taskId_tagName", (q) => q.eq("taskId", taskId).eq("tagName", removedTagName))
      .collect();
    for (const row of attrValues) {
      await ctx.db.delete(row._id);
    }
    ```
  - [ ] 4.3 If tag removal is done client-side (patching the tasks.tags array directly), create a new mutation `tagAttributeValues.removeByTaskAndTag` that the client calls after updating tags. The client should call this mutation whenever it removes a tag from a task.

- [ ] **Task 5: Frontend -- Attribute Catalog in TagsPanel** (AC: #7)
  - [ ] 5.1 In `dashboard/components/TagsPanel.tsx`, add Convex hooks at the top of the component:
    ```typescript
    const attributes = useQuery(api.tagAttributes.list);
    const createAttribute = useMutation(api.tagAttributes.create);
    const removeAttribute = useMutation(api.tagAttributes.remove);
    ```
  - [ ] 5.2 Add local state for the attribute creation form:
    ```typescript
    const [attrName, setAttrName] = useState("");
    const [attrType, setAttrType] = useState<"text" | "number" | "date" | "select">("text");
    const [attrOptions, setAttrOptions] = useState("");
    const [attrError, setAttrError] = useState("");
    ```
  - [ ] 5.3 After the tag creation form section (after line ~120, before the closing `</div>` of the component), add the "Attributes" section:
    ```tsx
    {/* Attributes Catalog Section */}
    <div className="px-6 py-4 border-t border-border">
      <h3 className="text-sm font-semibold text-foreground mb-2">Attribute Catalog</h3>
      <p className="text-xs text-muted-foreground mb-3">
        Define reusable attributes available for all tags.
      </p>
      {/* Attribute list */}
      {attributes && attributes.length > 0 && (
        <ul className="space-y-1.5 mb-3">
          {attributes.map((attr) => (
            <li key={attr._id} className="flex items-center gap-2 text-sm">
              <span className="font-medium">{attr.name}</span>
              <Badge variant="outline" className="text-[10px] px-1 py-0 h-4">
                {attr.type}
              </Badge>
              {attr.type === "select" && attr.options && (
                <span className="text-xs text-muted-foreground">
                  [{attr.options.join(", ")}]
                </span>
              )}
              <button
                aria-label={`Delete attribute ${attr.name}`}
                onClick={() => removeAttribute({ id: attr._id })}
                className="ml-auto text-muted-foreground hover:text-red-500 transition-colors"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {/* Attribute creation form */}
      <div className="space-y-2">
        <div className="flex gap-2">
          <Input
            placeholder="Attribute name..."
            value={attrName}
            maxLength={32}
            onChange={(e) => { setAttrName(e.target.value); setAttrError(""); }}
            className={`flex-1 ${attrError ? "border-red-500" : ""}`}
          />
          <select
            value={attrType}
            onChange={(e) => setAttrType(e.target.value as any)}
            className="h-9 rounded-md border border-input bg-background px-2 text-sm"
          >
            <option value="text">Text</option>
            <option value="number">Number</option>
            <option value="date">Date</option>
            <option value="select">Select</option>
          </select>
        </div>
        {attrType === "select" && (
          <Input
            placeholder="Options (comma-separated)..."
            value={attrOptions}
            onChange={(e) => setAttrOptions(e.target.value)}
          />
        )}
        <Button
          onClick={async () => {
            const trimmed = attrName.trim();
            if (!trimmed) return;
            setAttrError("");
            try {
              await createAttribute({
                name: trimmed,
                type: attrType,
                ...(attrType === "select" && attrOptions.trim()
                  ? { options: attrOptions.split(",").map((o) => o.trim()).filter(Boolean) }
                  : {}),
              });
              setAttrName("");
              setAttrOptions("");
            } catch (err) {
              setAttrError(err instanceof Error ? err.message : "Failed to create attribute");
            }
          }}
          disabled={!attrName.trim()}
          size="sm"
        >
          Add Attribute
        </Button>
        {attrError && <p className="text-xs text-red-500">{attrError}</p>}
      </div>
    </div>
    ```

- [ ] **Task 6: Frontend -- TagAttributeEditor Component** (AC: #9)
  - [ ] 6.1 Create `dashboard/components/TagAttributeEditor.tsx`:
    ```typescript
    interface TagAttributeEditorProps {
      taskId: Id<"tasks">;
      tagName: string;
      attribute: { _id: Id<"tagAttributes">; name: string; type: string; options?: string[] };
      currentValue: string;
    }
    ```
  - [ ] 6.2 Implement the component with type-aware input rendering:
    - `type === "text"`: `<Input type="text" />`
    - `type === "number"`: `<Input type="number" />`
    - `type === "date"`: `<Input type="date" />`
    - `type === "select"`: `<select>` with `<option>` for each option in `attribute.options`
  - [ ] 6.3 On value change, call `tagAttributeValues.upsert` mutation with debounce (300ms) for text/number inputs, immediate for select/date.
  - [ ] 6.4 Show a small "x" button to clear the value (upserts empty string).

- [ ] **Task 7: Frontend -- Tag Attributes in TaskDetailSheet** (AC: #8)
  - [ ] 7.1 In `dashboard/components/TaskDetailSheet.tsx`, add Convex hooks:
    ```typescript
    const tagAttributeValues = useQuery(
      api.tagAttributeValues.getByTask,
      taskId ? { taskId } : "skip",
    );
    const allAttributes = useQuery(api.tagAttributes.list);
    ```
  - [ ] 7.2 In the Config tab, below the existing tags section (after line ~570), add the tag attributes section:
    ```tsx
    {task.tags && task.tags.length > 0 && allAttributes && allAttributes.length > 0 && (
      <div className="mt-3">
        <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
          Tag Attributes
        </h4>
        {task.tags.map((tag) => {
          const tagValues = tagAttributeValues?.filter((v) => v.tagName === tag) ?? [];
          return (
            <div key={tag} className="mb-3">
              <p className="text-sm font-medium mb-1">{tag}</p>
              <div className="space-y-1.5 ml-2">
                {allAttributes.map((attr) => {
                  const val = tagValues.find((v) => v.attributeId === attr._id);
                  return (
                    <TagAttributeEditor
                      key={attr._id}
                      taskId={task._id}
                      tagName={tag}
                      attribute={attr}
                      currentValue={val?.value ?? ""}
                    />
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    )}
    ```
  - [ ] 7.3 Add the import at the top of TaskDetailSheet:
    ```typescript
    import { TagAttributeEditor } from "./TagAttributeEditor";
    ```

- [ ] **Task 8: Backend Python -- Thread Context Tag Attributes** (AC: #10)
  - [ ] 8.1 The thread context is built in `nanobot/mc/thread_context.py` (`ThreadContextBuilder.build()`). However, the thread context builder works with message data, not task data. The tag attribute injection should happen at the call site in `executor.py` where the task data is available.
  - [ ] 8.2 In `nanobot/mc/executor.py`, in the `_execute_task` method, after the thread context injection (around line ~690), add tag attribute context injection:
    ```python
    # Inject tag attribute context
    try:
        task_tags = (fresh_task or {}).get("tags") or []
        if task_tags:
            tag_attr_values = await asyncio.to_thread(
                self._bridge.query,
                "tagAttributeValues:getByTask",
                {"taskId": task_id},
            )
            if tag_attr_values:
                tag_attrs_context = _build_tag_attributes_context(task_tags, tag_attr_values)
                if tag_attrs_context:
                    description = (description or "") + f"\n{tag_attrs_context}"
    except Exception:
        logger.warning(
            "[executor] Failed to fetch tag attributes for '%s', continuing without",
            title, exc_info=True,
        )
    ```
  - [ ] 8.3 Add the helper function `_build_tag_attributes_context` in `executor.py` (near the existing `_build_thread_context` function around line 246):
    ```python
    def _build_tag_attributes_context(
        tags: list[str],
        attr_values: list[dict[str, Any]],
    ) -> str:
        """Format tag attribute values as context for the agent."""
        lines = []
        for tag in tags:
            tag_vals = [v for v in attr_values if v.get("tag_name") == tag and v.get("value")]
            if not tag_vals:
                continue
            pairs = ", ".join(f"{v.get('attribute_name', 'unknown')}={v.get('value', '')}" for v in tag_vals)
            lines.append(f"{tag}: {pairs}")
        if not lines:
            return ""
        return "[Task Tag Attributes]\n" + "\n".join(lines)
    ```
  - [ ] 8.4 Note: The bridge will auto-convert camelCase keys from Convex (`tagName`, `attributeId`, `value`) to snake_case (`tag_name`, `attribute_id`, `value`). However, the attribute name is stored as an ID reference, not a name. To include the attribute name in context, either:
    - **Option A (recommended):** Also fetch `tagAttributes.list` in the executor and build a lookup dict `{attribute_id: attribute_name}`. This avoids changing the Convex schema.
    - **Option B:** Add an `attributeName` denormalized field to `tagAttributeValues` (simpler queries but data duplication).
    Choose Option A for data integrity.
  - [ ] 8.5 Update the helper to use the attribute lookup:
    ```python
    def _build_tag_attributes_context(
        tags: list[str],
        attr_values: list[dict[str, Any]],
        attr_catalog: list[dict[str, Any]],
    ) -> str:
        """Format tag attribute values as context for the agent."""
        attr_names = {a.get("id", a.get("_id", "")): a.get("name", "unknown") for a in attr_catalog}
        lines = []
        for tag in tags:
            tag_vals = [v for v in attr_values if v.get("tag_name") == tag and v.get("value")]
            if not tag_vals:
                continue
            pairs = ", ".join(
                f"{attr_names.get(v.get('attribute_id', ''), 'unknown')}={v.get('value', '')}"
                for v in tag_vals
            )
            lines.append(f"{tag}: {pairs}")
        if not lines:
            return ""
        return "[Task Tag Attributes]\n" + "\n".join(lines)
    ```

## Dev Notes

### Architecture Patterns

**Shared Catalog Pattern:**
The `tagAttributes` table is a catalog -- creating "client" as a text attribute makes it available for ALL tags, not just one specific tag. This is intentional: it enables consistency (all tags that track "client" use the same attribute definition) and discoverability (users see all available attributes when editing any tag).

**Upsert Pattern for Values:**
The `tagAttributeValues.upsert` mutation uses a query-then-patch-or-insert pattern. Convex does not have a native upsert, so the pattern is:
1. Query by (taskId, tagName) index
2. Filter in memory by attributeId
3. If found: `ctx.db.patch()`
4. If not found: `ctx.db.insert()`

This is the standard Convex approach. The `by_taskId_tagName` compound index makes the initial query efficient.

**Cascade Delete Strategy:**
Two cascade paths exist:
1. **Tag removed from task** -> delete all `tagAttributeValues` where (taskId, tagName) match. This can be triggered client-side after the tag array update, OR server-side in a mutation.
2. **Attribute removed from catalog** -> delete all `tagAttributeValues` where attributeId matches. This MUST be server-side (in `tagAttributes.remove`) to ensure atomicity.

**Bridge Key Conversion:**
Convex uses camelCase (`tagName`, `attributeId`, `taskId`). The Python bridge auto-converts to snake_case (`tag_name`, `attribute_id`, `task_id`). Always use snake_case in Python code when accessing bridge response data.

**Common Mistakes to Avoid:**
- Do NOT add a `tagId` field referencing `taskTags` -- tags are stored as plain strings on the task. The `tagName` string is the join key.
- Do NOT eagerly load all tag attribute values on the kanban board -- only load them in TaskDetailSheet when a task is opened.
- The `options` array on `tagAttributes` should only be present for `type: "select"`. Do not store empty arrays for other types.

### Project Structure Notes

**Files to CREATE:**
- `dashboard/convex/tagAttributes.ts` -- Catalog CRUD mutations + queries
- `dashboard/convex/tagAttributeValues.ts` -- Value CRUD mutations + queries
- `dashboard/components/TagAttributeEditor.tsx` -- Type-aware inline value editor

**Files to MODIFY:**
- `dashboard/convex/schema.ts` -- Add `tagAttributes` and `tagAttributeValues` tables
- `dashboard/components/TagsPanel.tsx` -- Add "Attributes" catalog section
- `dashboard/components/TaskDetailSheet.tsx` -- Add tag attribute display + editors below tag badges
- `nanobot/mc/executor.py` -- Add `_build_tag_attributes_context()` helper and inject into task description

### References

- [Source: `dashboard/convex/schema.ts`] -- Existing `taskTags` table (lines 220-223) and `tasks.tags` field (line 41)
- [Source: `dashboard/convex/taskTags.ts`] -- Pattern for tag CRUD: list, create, remove (lines 1-56)
- [Source: `dashboard/components/TagsPanel.tsx`] -- Tag management UI with list, creation form, color picker (lines 1-123)
- [Source: `dashboard/components/TaskDetailSheet.tsx`] -- Tags display in Config tab (lines 557-570), shows tag badges
- [Source: `nanobot/mc/thread_context.py`] -- ThreadContextBuilder class (lines 1-218), context formatting patterns
- [Source: `nanobot/mc/executor.py`] -- `_build_thread_context` shim (lines 246-257), thread context injection in `_execute_task` (lines 683-700)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
