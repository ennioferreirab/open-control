"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Input } from "@/components/ui/input";
import { X } from "lucide-react";
import type { Id } from "../convex/_generated/dataModel";

interface TagAttributeEditorProps {
  taskId: Id<"tasks">;
  tagName: string;
  attribute: {
    _id: Id<"tagAttributes">;
    name: string;
    type: string;
    options?: string[];
  };
  currentValue: string;
}

export function TagAttributeEditor({
  taskId,
  tagName,
  attribute,
  currentValue,
}: TagAttributeEditorProps) {
  const upsert = useMutation(api.tagAttributeValues.upsert);
  const [localValue, setLocalValue] = useState(currentValue);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Sync from prop when external data changes
  useEffect(() => {
    setLocalValue(currentValue);
  }, [currentValue]);

  const save = useCallback(
    (val: string) => {
      upsert({
        taskId,
        tagName,
        attributeId: attribute._id,
        value: val,
      });
    },
    [upsert, taskId, tagName, attribute._id]
  );

  const handleDebouncedChange = useCallback(
    (val: string) => {
      setLocalValue(val);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => save(val), 300);
    },
    [save]
  );

  const handleImmediateChange = useCallback(
    (val: string) => {
      setLocalValue(val);
      save(val);
    },
    [save]
  );

  const handleClear = useCallback(() => {
    setLocalValue("");
    save("");
  }, [save]);

  // Cleanup debounce on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const clearButton = localValue ? (
    <button
      onClick={handleClear}
      className="text-muted-foreground hover:text-foreground transition-colors flex-shrink-0"
      aria-label={`Clear ${attribute.name}`}
    >
      <X className="h-3 w-3" />
    </button>
  ) : null;

  if (attribute.type === "select" && attribute.options) {
    return (
      <div className="flex items-center gap-2">
        <label className="text-xs text-muted-foreground min-w-[60px] truncate">
          {attribute.name}
        </label>
        <select
          value={localValue}
          onChange={(e) => handleImmediateChange(e.target.value)}
          className="h-7 flex-1 rounded-md border border-input bg-transparent px-2 text-xs"
        >
          <option value="">--</option>
          {attribute.options.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
        {clearButton}
      </div>
    );
  }

  if (attribute.type === "date") {
    return (
      <div className="flex items-center gap-2">
        <label className="text-xs text-muted-foreground min-w-[60px] truncate">
          {attribute.name}
        </label>
        <Input
          type="date"
          value={localValue}
          onChange={(e) => handleImmediateChange(e.target.value)}
          className="h-7 flex-1 text-xs"
        />
        {clearButton}
      </div>
    );
  }

  if (attribute.type === "number") {
    return (
      <div className="flex items-center gap-2">
        <label className="text-xs text-muted-foreground min-w-[60px] truncate">
          {attribute.name}
        </label>
        <Input
          type="number"
          value={localValue}
          onChange={(e) => handleDebouncedChange(e.target.value)}
          className="h-7 flex-1 text-xs"
          placeholder="0"
        />
        {clearButton}
      </div>
    );
  }

  // Default: text
  return (
    <div className="flex items-center gap-2">
      <label className="text-xs text-muted-foreground min-w-[60px] truncate">
        {attribute.name}
      </label>
      <Input
        type="text"
        value={localValue}
        onChange={(e) => handleDebouncedChange(e.target.value)}
        className="h-7 flex-1 text-xs"
        placeholder="..."
      />
      {clearButton}
    </div>
  );
}
