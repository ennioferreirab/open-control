"use client";

import { useState } from "react";
import { useQuery, useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { X } from "lucide-react";
import { ConvexError } from "convex/values";
import { TAG_COLORS } from "@/lib/constants";

const COLOR_KEYS = Object.keys(TAG_COLORS) as Array<keyof typeof TAG_COLORS>;

const ATTR_TYPES = ["text", "number", "date", "select"] as const;
type AttrType = (typeof ATTR_TYPES)[number];

const ATTR_TYPE_LABELS: Record<AttrType, string> = {
  text: "Text",
  number: "Number",
  date: "Date",
  select: "Select",
};

export function TagsPanel() {
  const tags = useQuery(api.taskTags.list);
  const createTag = useMutation(api.taskTags.create);
  const removeTag = useMutation(api.taskTags.remove);

  const attributes = useQuery(api.tagAttributes.list);
  const createAttribute = useMutation(api.tagAttributes.create);
  const removeAttribute = useMutation(api.tagAttributes.remove);

  const [name, setName] = useState("");
  const [selectedColor, setSelectedColor] = useState<string>("blue");
  const [error, setError] = useState("");

  // Attribute catalog form state
  const [attrName, setAttrName] = useState("");
  const [attrType, setAttrType] = useState<AttrType>("text");
  const [attrOptions, setAttrOptions] = useState("");
  const [attrError, setAttrError] = useState("");

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

  const handleAddAttribute = async () => {
    const trimmed = attrName.trim();
    if (!trimmed) return;
    setAttrError("");

    const options =
      attrType === "select"
        ? attrOptions
            .split(",")
            .map((o) => o.trim())
            .filter(Boolean)
        : undefined;

    try {
      await createAttribute({
        name: trimmed,
        type: attrType,
        ...(options ? { options } : {}),
      });
      setAttrName("");
      setAttrOptions("");
      setAttrType("text");
    } catch (err: unknown) {
      if (err instanceof ConvexError) {
        setAttrError(String(err.data));
      } else {
        setAttrError("Failed to create attribute. Please try again.");
      }
    }
  };

  const handleAttrKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleAddAttribute();
  };

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-5 border-b border-border">
        <h2 className="text-lg font-semibold text-foreground">Tags</h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          Manage predefined task tags
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
        {/* Tag list */}
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

        {/* Attribute Catalog */}
        <div>
          <h3 className="text-sm font-medium text-foreground mb-2">Attribute Catalog</h3>
          <p className="text-xs text-muted-foreground mb-3">
            Define reusable attributes that can be set per tag on each task.
          </p>
          {attributes === undefined ? null : attributes.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">
              No attributes yet. Add your first attribute below.
            </p>
          ) : (
            <ul className="space-y-1.5 mb-3">
              {attributes.map((attr) => (
                <li
                  key={attr._id}
                  className="flex items-center gap-2 py-1"
                >
                  <span className="text-sm flex-1">{attr.name}</span>
                  <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                    {ATTR_TYPE_LABELS[attr.type as AttrType] ?? attr.type}
                  </Badge>
                  {attr.type === "select" && attr.options && (
                    <span className="text-[10px] text-muted-foreground truncate max-w-[120px]">
                      {attr.options.join(", ")}
                    </span>
                  )}
                  <button
                    aria-label={`Delete attribute ${attr.name}`}
                    onClick={() => removeAttribute({ id: attr._id })}
                    className="text-muted-foreground hover:text-red-500 transition-colors flex-shrink-0"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="px-6 py-4 border-t border-border space-y-4">
        {/* Tag creation form */}
        <div className="space-y-2">
          <div className="flex gap-2">
            <Input
              placeholder="Tag name..."
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

        {/* Attribute creation form */}
        <div className="space-y-2 pt-2 border-t border-border">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            New Attribute
          </p>
          <div className="flex gap-2">
            <Input
              placeholder="Attribute name..."
              value={attrName}
              maxLength={32}
              onChange={(e) => {
                setAttrName(e.target.value);
                setAttrError("");
              }}
              onKeyDown={handleAttrKeyDown}
              className={`flex-1 ${attrError ? "border-red-500" : ""}`}
            />
            <select
              value={attrType}
              onChange={(e) => setAttrType(e.target.value as AttrType)}
              className="h-9 rounded-md border border-input bg-transparent px-2 text-sm"
            >
              {ATTR_TYPES.map((t) => (
                <option key={t} value={t}>
                  {ATTR_TYPE_LABELS[t]}
                </option>
              ))}
            </select>
          </div>
          {attrType === "select" && (
            <Input
              placeholder="Options (comma-separated)..."
              value={attrOptions}
              onChange={(e) => setAttrOptions(e.target.value)}
              onKeyDown={handleAttrKeyDown}
            />
          )}
          <Button
            onClick={handleAddAttribute}
            disabled={!attrName.trim()}
            variant="outline"
            className="w-full"
          >
            Add Attribute
          </Button>
          {attrError && <p className="text-xs text-red-500">{attrError}</p>}
        </div>
      </div>
    </div>
  );
}
