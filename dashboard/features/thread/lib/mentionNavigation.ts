export interface MentionNavigation {
  close: () => void;
  navigateDown: () => void;
  navigateUp: () => void;
  selectFocused: () => boolean;
}

export interface MentionTextareaElement extends HTMLTextAreaElement {
  __mentionNav?: MentionNavigation;
}
