export interface ParsedAttributeFilter {
  tagName: string;
  attrName: string;
  value: string;
}

export interface ParsedSearch {
  freeText: string;
  tagFilters: string[];
  attributeFilters: ParsedAttributeFilter[];
}

function tokenize(input: string): string[] {
  const tokens: string[] = [];
  let current = "";
  let quote: '"' | "'" | null = null;

  for (const char of input) {
    if (quote) {
      if (char === quote) {
        quote = null;
      } else {
        current += char;
      }
      continue;
    }

    if (char === '"' || char === "'") {
      quote = char;
      continue;
    }

    if (/\s/.test(char)) {
      if (current) {
        tokens.push(current);
        current = "";
      }
      continue;
    }

    current += char;
  }

  if (current) {
    tokens.push(current);
  }

  return tokens;
}

export function parseSearch(input: string): ParsedSearch {
  const raw = input.trim();
  if (!raw) {
    return { freeText: "", tagFilters: [], attributeFilters: [] };
  }

  const tokens = tokenize(raw);
  const freeTextTokens: string[] = [];
  const tagFilters = new Set<string>();
  const attributeFilters: ParsedAttributeFilter[] = [];

  for (const token of tokens) {
    const tagMatch = token.match(/^tag:(.+)$/i);
    if (tagMatch) {
      const tagName = tagMatch[1].trim().toLowerCase();
      if (tagName) {
        tagFilters.add(tagName);
        continue;
      }
    }

    const parts = token.split(":");
    if (parts.length >= 3) {
      const [tagNameRaw, attrNameRaw, ...valueParts] = parts;
      const tagName = tagNameRaw.trim().toLowerCase();
      const attrName = attrNameRaw.trim().toLowerCase();
      const value = valueParts.join(":").trim().toLowerCase();

      if (tagName && attrName && value) {
        attributeFilters.push({ tagName, attrName, value });
        continue;
      }
    }

    freeTextTokens.push(token);
  }

  return {
    freeText: freeTextTokens.join(" ").trim(),
    tagFilters: [...tagFilters],
    attributeFilters,
  };
}
