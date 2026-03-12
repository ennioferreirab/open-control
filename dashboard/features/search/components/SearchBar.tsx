"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Search, SlidersHorizontal, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useSearchBarFilters } from "@/features/search/hooks/useSearchBarFilters";
import { TAG_COLORS } from "@/lib/constants";
import { parseSearch } from "@/lib/searchParser";
import { cn } from "@/lib/utils";

interface SearchBarProps {
  onSearchChange?: (value: string) => void;
  className?: string;
}

export function SearchBar({ onSearchChange, className }: SearchBarProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState("");
  const [attrValues, setAttrValues] = useState<Record<string, string>>({});
  const { tags, tagsWithAttrs } = useSearchBarFilters();

  const parsed = useMemo(() => parseSearch(value), [value]);
  const hasValue = value.trim().length > 0;
  const hasFilterOptions = (tags?.length ?? 0) > 0;

  useEffect(() => {
    const handle = window.setTimeout(() => {
      onSearchChange?.(value);
    }, 300);
    return () => window.clearTimeout(handle);
  }, [onSearchChange, value]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const isEditable = target
        ? target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable
        : false;

      if (event.key === "/" && !isEditable) {
        event.preventDefault();
        inputRef.current?.focus();
        return;
      }

      if (event.key === "Escape" && document.activeElement === inputRef.current) {
        setValue("");
        inputRef.current?.blur();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  function toggleTagFilter(tagName: string) {
    const lc = tagName.toLowerCase();
    if (parsed.tagFilters.includes(lc)) {
      const newValue = value
        .replace(new RegExp(`(?:^|\\s)tag:${lc}(?=\\s|$)`, "i"), " ")
        .replace(/\s+/g, " ")
        .trim();
      setValue(newValue);
    } else {
      setValue(value.trim() ? `${value.trim()} tag:${lc}` : `tag:${lc}`);
    }
  }

  function applyAttrFilter(tagName: string, attrName: string) {
    const key = `${tagName}:${attrName}`;
    const filterValue = attrValues[key]?.trim();
    if (!filterValue) return;
    const lcTag = tagName.toLowerCase();
    const lcAttr = attrName.toLowerCase();
    const token = `${lcTag}:${lcAttr}:${filterValue}`;
    const cleaned = value
      .replace(new RegExp(`(?:^|\\s)${lcTag}:${lcAttr}:[^\\s]+`, "gi"), " ")
      .replace(/\s+/g, " ")
      .trim();
    setValue(cleaned ? `${cleaned} ${token}` : token);
    setAttrValues((prev) => ({ ...prev, [key]: "" }));
  }

  function removeAttrFilter(tagName: string, attrName: string) {
    const lcTag = tagName.toLowerCase();
    const lcAttr = attrName.toLowerCase();
    const newValue = value
      .replace(new RegExp(`(?:^|\\s)${lcTag}:${lcAttr}:[^\\s]+`, "gi"), " ")
      .replace(/\s+/g, " ")
      .trim();
    setValue(newValue);
  }

  const hasActiveFilters = parsed.tagFilters.length > 0 || parsed.attributeFilters.length > 0;

  return (
    <div className={cn("flex items-center gap-1 w-full max-w-md", className)}>
      <div className="relative flex-1">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          ref={inputRef}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="Search tasks…"
          aria-label="Search tasks"
          className="h-9 bg-background pl-8 pr-8"
        />
        {hasValue && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="absolute right-1 top-1/2 h-7 w-7 -translate-y-1/2"
            aria-label="Clear search"
            onClick={() => {
              setValue("");
              inputRef.current?.focus();
            }}
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      {hasFilterOptions && (
        <Popover>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className={cn("h-9 w-9 shrink-0", hasActiveFilters && "text-primary")}
              aria-label="Open filter picker"
            >
              <SlidersHorizontal className="h-4 w-4" />
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-72 p-3 space-y-3">
            {tags && tags.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Tags
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {tags.map((tag) => {
                    const colors = TAG_COLORS[tag.color] ?? TAG_COLORS.blue;
                    const isActive = parsed.tagFilters.includes(tag.name.toLowerCase());
                    return (
                      <button
                        key={tag._id}
                        type="button"
                        onClick={() => toggleTagFilter(tag.name)}
                        className={cn(
                          "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium transition-all cursor-pointer",
                          colors.bg,
                          colors.text,
                          isActive
                            ? "ring-2 ring-offset-1 ring-current opacity-100"
                            : "opacity-60 hover:opacity-100",
                        )}
                      >
                        <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", colors.dot)} />
                        {tag.name}
                        {isActive && <X className="h-2.5 w-2.5 ml-0.5 shrink-0" />}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {tagsWithAttrs.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Attributes
                </p>
                {tagsWithAttrs.map((tag) => {
                  const colors = TAG_COLORS[tag.color] ?? TAG_COLORS.blue;
                  return (
                    <div key={tag._id} className="space-y-1">
                      <div
                        className={cn(
                          "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
                          colors.bg,
                          colors.text,
                        )}
                      >
                        <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", colors.dot)} />
                        {tag.name}
                      </div>
                      <div className="pl-3 space-y-1">
                        {tag.attrs.map((attr) => {
                          const key = `${tag.name}:${attr.name}`;
                          const activeFilter = parsed.attributeFilters.find(
                            (filter) =>
                              filter.tagName === tag.name.toLowerCase() &&
                              filter.attrName === attr.name.toLowerCase(),
                          );
                          return (
                            <div key={attr._id} className="flex items-center gap-1.5">
                              <span className="text-xs text-muted-foreground w-20 truncate shrink-0">
                                {attr.name}
                              </span>
                              {activeFilter ? (
                                <button
                                  type="button"
                                  onClick={() => removeAttrFilter(tag.name, attr.name)}
                                  className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs"
                                >
                                  {activeFilter.value}
                                  <X className="h-3 w-3" />
                                </button>
                              ) : (
                                <>
                                  <Input
                                    value={attrValues[key] ?? ""}
                                    onChange={(event) =>
                                      setAttrValues((prev) => ({
                                        ...prev,
                                        [key]: event.target.value,
                                      }))
                                    }
                                    placeholder="Value"
                                    className="h-7 text-xs"
                                  />
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="secondary"
                                    className="h-7 px-2 text-xs"
                                    onClick={() => applyAttrFilter(tag.name, attr.name)}
                                  >
                                    Add
                                  </Button>
                                </>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </PopoverContent>
        </Popover>
      )}
    </div>
  );
}
