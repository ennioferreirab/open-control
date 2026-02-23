"use client";

import { useState } from "react";
import { useQuery, useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";
import { ConvexError } from "convex/values";
import { TAG_COLORS } from "@/lib/constants";

const COLOR_KEYS = Object.keys(TAG_COLORS) as Array<keyof typeof TAG_COLORS>;

export function TagsPanel() {
  const tags = useQuery(api.taskTags.list);
  const createTag = useMutation(api.taskTags.create);
  const removeTag = useMutation(api.taskTags.remove);

  const [name, setName] = useState("");
  const [selectedColor, setSelectedColor] = useState<string>("blue");
  const [error, setError] = useState("");

  const handleAdd = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setError("");
    try {
      await createTag({ name: trimmed, color: selectedColor });
      setName("");
    } catch (err: unknown) {
      if (err instanceof ConvexError && err.data === "Tag already exists") {
        setError("Tag already exists");
      } else {
        setError("Failed to create tag. Please try again.");
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleAdd();
  };

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-5 border-b border-border">
        <h2 className="text-lg font-semibold text-foreground">Tags</h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          Manage predefined task tags
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        {tags === undefined ? null : tags.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            No tags yet. Add your first tag below.
          </p>
        ) : (
          <ul className="space-y-2">
            {tags.map((tag) => {
              const color = TAG_COLORS[tag.color];
              return (
                <li
                  key={tag._id}
                  className="flex items-center gap-3 py-1.5"
                >
                  <span
                    className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${color?.dot ?? "bg-muted"}`}
                  />
                  <span className="text-sm flex-1">{tag.name}</span>
                  <button
                    aria-label={`Delete tag ${tag.name}`}
                    onClick={() => removeTag({ id: tag._id })}
                    className="text-muted-foreground hover:text-red-500 transition-colors"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="px-6 py-4 border-t border-border space-y-3">
        <div className="flex gap-2">
          <Input
            placeholder="Tag name…"
            value={name}
            maxLength={32}
            onChange={(e) => {
              setName(e.target.value);
              setError("");
            }}
            onKeyDown={handleKeyDown}
            className={error ? "border-red-500" : ""}
          />
          <Button onClick={handleAdd} disabled={!name.trim()}>
            Add
          </Button>
        </div>
        {error && <p className="text-xs text-red-500">{error}</p>}
        <div className="flex gap-2 flex-wrap">
          {COLOR_KEYS.map((key) => {
            const color = TAG_COLORS[key];
            const isSelected = selectedColor === key;
            return (
              <button
                key={key}
                aria-label={`Select color ${key}`}
                onClick={() => setSelectedColor(key)}
                className={`w-6 h-6 rounded-full flex-shrink-0 transition-all ${color.dot} ${
                  isSelected
                    ? "ring-2 ring-offset-2 ring-foreground"
                    : "opacity-70 hover:opacity-100"
                }`}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}
