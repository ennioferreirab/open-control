export type DocumentSource =
  | { kind: "task"; taskId: string }
  | { kind: "board-artifact"; boardName: string };

export interface DocumentFileRef {
  name: string;
  type?: string;
  size?: number;
  subfolder?: string;
  path?: string;
}

export function resolveDocumentSource(
  source?: DocumentSource,
  taskId?: string,
): DocumentSource | null {
  if (source) {
    return source;
  }
  if (taskId) {
    return { kind: "task", taskId };
  }
  return null;
}

export function buildDocumentUrl(source: DocumentSource, file: DocumentFileRef): string {
  if (source.kind === "task") {
    if (!file.subfolder) {
      throw new Error("Task document sources require a subfolder");
    }
    return `/api/tasks/${source.taskId}/files/${file.subfolder}/${encodeURIComponent(file.name)}`;
  }

  const artifactPath = file.path ?? file.name;
  return `/api/boards/${source.boardName}/artifacts/${encodeURIComponent(artifactPath)}`;
}

export function buildRelativeDocumentUrl(
  source: DocumentSource | null,
  sourceFile: DocumentFileRef | undefined,
  value: string | undefined,
): string | undefined {
  if (!value || !source || !sourceFile) {
    return value;
  }

  if (value.startsWith("#") || value.startsWith("/") || value.startsWith("//")) {
    return value;
  }
  if (/^[a-zA-Z][a-zA-Z\d+.-]*:/.test(value)) {
    return value;
  }

  const suffixIndex = value.search(/[?#]/);
  const pathname = suffixIndex === -1 ? value : value.slice(0, suffixIndex);
  const suffix = suffixIndex === -1 ? "" : value.slice(suffixIndex);

  const basePath = source.kind === "task" ? sourceFile.name : (sourceFile.path ?? sourceFile.name);

  const resolved = basePath.split("/").filter(Boolean);
  resolved.pop();

  for (const segment of pathname.split("/")) {
    if (!segment || segment === ".") {
      continue;
    }
    if (segment === "..") {
      if (resolved.length === 0) {
        return undefined;
      }
      resolved.pop();
      continue;
    }
    resolved.push(segment);
  }

  const relativePath = resolved.join("/");
  if (source.kind === "task") {
    if (!sourceFile.subfolder) {
      return undefined;
    }
    return `/api/tasks/${source.taskId}/files/${sourceFile.subfolder}/${encodeURIComponent(relativePath)}${suffix}`;
  }

  return `/api/boards/${source.boardName}/artifacts/${encodeURIComponent(relativePath)}${suffix}`;
}
