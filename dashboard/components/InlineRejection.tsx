"use client";

import { useState, useRef, useEffect } from "react";
import { Id } from "../convex/_generated/dataModel";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import * as motion from "motion/react-client";
import { useInlineRejectionActions } from "@/features/tasks/hooks/useInlineRejectionActions";

interface InlineRejectionProps {
  taskId: Id<"tasks">;
  onClose: () => void;
}

export function InlineRejection({ taskId, onClose }: InlineRejectionProps) {
  const [feedback, setFeedback] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { deny, returnToLeadAgent } = useInlineRejectionActions(taskId, onClose);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const handleDeny = async () => {
    if (!feedback.trim()) return;
    setIsSubmitting(true);
    try {
      await deny(feedback.trim());
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReturn = async () => {
    if (!feedback.trim()) return;
    setIsSubmitting(true);
    try {
      await returnToLeadAgent(feedback.trim());
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: "auto", opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      transition={{ duration: 0.15 }}
      className="overflow-hidden"
    >
      <div className="pt-2 space-y-2">
        <Textarea
          ref={textareaRef}
          placeholder="Explain what needs to change..."
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          className="text-sm min-h-[80px]"
          disabled={isSubmitting}
        />
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="destructive"
            className="text-xs h-7"
            onClick={handleDeny}
            disabled={isSubmitting || !feedback.trim()}
          >
            Submit
          </Button>
          <Button
            size="sm"
            variant="secondary"
            className="text-xs h-7"
            onClick={handleReturn}
            disabled={isSubmitting || !feedback.trim()}
          >
            Return to Lead Agent
          </Button>
        </div>
      </div>
    </motion.div>
  );
}
