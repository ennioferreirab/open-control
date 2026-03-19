"use client";

import { useState, useMemo } from "react";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useSkillsSelectorData } from "@/features/agents/hooks/useSkillsSelectorData";

interface SkillsSelectorProps {
  selected: string[];
  onChange: (skills: string[]) => void;
  onViewSkill?: (name: string) => void;
}

export function SkillsSelector({ selected, onChange, onViewSkill }: SkillsSelectorProps) {
  const skills = useSkillsSelectorData();
  const [search, setSearch] = useState("");

  const filteredSkills = useMemo(() => {
    if (!skills) return [];
    const q = search.toLowerCase();
    return skills.filter(
      (s) => s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q),
    );
  }, [skills, search]);

  const selectedSkills = useMemo(
    () => filteredSkills.filter((s) => selected.includes(s.name)),
    [filteredSkills, selected],
  );

  const unselectedSkills = useMemo(
    () => filteredSkills.filter((s) => !selected.includes(s.name)),
    [filteredSkills, selected],
  );

  const parseEmoji = (metadata: string | undefined): string | null => {
    if (!metadata) return null;
    try {
      const parsed = JSON.parse(metadata);
      return parsed?.nanobot?.emoji || parsed?.openclaw?.emoji || null;
    } catch {
      return null;
    }
  };

  const handleToggle = (skillName: string, isAlways: boolean) => {
    if (isAlways) return; // Cannot uncheck always-loaded skills
    if (selected.includes(skillName)) {
      onChange(selected.filter((s) => s !== skillName));
    } else {
      onChange([...selected, skillName]);
    }
  };

  if (skills === undefined) {
    return <p className="text-sm text-muted-foreground py-2">Loading skills...</p>;
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium">Skills</label>
        <Badge variant="secondary" className="text-xs">
          {selected.length} of {skills.length} selected
        </Badge>
      </div>

      <Input
        placeholder="Search skills..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="h-8 text-sm"
      />

      <ScrollArea className="h-[200px] rounded-md border p-2">
        {selectedSkills.length > 0 && (
          <>
            {selectedSkills.map((skill) => (
              <SkillRow
                key={skill.name}
                name={skill.name}
                description={skill.description}
                emoji={parseEmoji(skill.metadata)}
                available={skill.available}
                requires={skill.requires}
                always={skill.always}
                checked={true}
                onToggle={() => handleToggle(skill.name, !!skill.always)}
                onView={onViewSkill ? () => onViewSkill(skill.name) : undefined}
              />
            ))}
            {unselectedSkills.length > 0 && <Separator className="my-1" />}
          </>
        )}
        {unselectedSkills.map((skill) => (
          <SkillRow
            key={skill.name}
            name={skill.name}
            description={skill.description}
            emoji={parseEmoji(skill.metadata)}
            available={skill.available}
            requires={skill.requires}
            always={skill.always}
            checked={false}
            onToggle={() => handleToggle(skill.name, !!skill.always)}
            onView={onViewSkill ? () => onViewSkill(skill.name) : undefined}
          />
        ))}
        {filteredSkills.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-4">
            {search ? "No skills match your search" : "No skills available"}
          </p>
        )}
      </ScrollArea>
    </div>
  );
}

function SkillRow({
  name,
  description,
  emoji,
  available,
  requires,
  always,
  checked,
  onToggle,
  onView,
}: {
  name: string;
  description: string;
  emoji: string | null;
  available: boolean;
  requires?: string;
  always?: boolean;
  checked: boolean;
  onToggle: () => void;
  onView?: () => void;
}) {
  return (
    <label className="flex items-start gap-2 py-1.5 px-1 rounded hover:bg-muted/50 cursor-pointer">
      <Checkbox
        checked={checked}
        onCheckedChange={onToggle}
        disabled={!!always}
        className="mt-0.5"
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          {emoji && <span className="text-sm">{emoji}</span>}
          {onView ? (
            <button
              type="button"
              className="text-sm font-medium hover:underline text-left"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onView();
              }}
            >
              {name}
            </button>
          ) : (
            <span className="text-sm font-medium">{name}</span>
          )}
          {always && <span className="text-[10px] text-muted-foreground">(always loaded)</span>}
          {available ? (
            <span
              className="h-1.5 w-1.5 rounded-full bg-green-500 shrink-0"
              title="Requirements met"
            />
          ) : (
            <span
              className="h-1.5 w-1.5 rounded-full bg-amber-500 shrink-0"
              title={requires ? `Missing: ${requires}` : "Requirements not met"}
            />
          )}
        </div>
        <p className="text-xs text-muted-foreground truncate">{description}</p>
      </div>
    </label>
  );
}
