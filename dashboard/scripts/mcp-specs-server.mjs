#!/usr/bin/env node
/**
 * MCP server that exposes create_agent_spec and publish_squad_graph tools.
 * Proxies calls to the Next.js API routes via HTTP.
 *
 * Uses the official @modelcontextprotocol/sdk.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const API_BASE = process.env.MC_API_BASE || "http://localhost:3000";

const server = new McpServer({
  name: "mc-specs",
  version: "1.0.0",
});

server.tool(
  "create_agent_spec",
  "Create and publish a V2 agent specification. Returns the new spec ID on success.",
  {
    name: z.string().describe("Agent slug name"),
    displayName: z.string().describe("Human-readable name"),
    role: z.string().describe("Agent role description"),
    responsibilities: z.array(z.string()).optional(),
    nonGoals: z.array(z.string()).optional(),
    principles: z.array(z.string()).optional(),
    workingStyle: z.string().optional(),
    qualityRules: z.array(z.string()).optional(),
    antiPatterns: z.array(z.string()).optional(),
    outputContract: z.string().optional(),
    toolPolicy: z.string().optional(),
    memoryPolicy: z.string().optional(),
    executionPolicy: z.string().optional(),
    reviewPolicyRef: z.string().optional(),
    skills: z.array(z.string()).optional(),
    model: z.string().optional(),
  },
  async (args) => {
    const res = await fetch(`${API_BASE}/api/specs/agent`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(args),
    });
    const data = await res.json();
    if (data.error) {
      return { content: [{ type: "text", text: `Error: ${data.error}` }], isError: true };
    }
    return { content: [{ type: "text", text: `Agent spec created and published: ${data.specId}` }] };
  },
);

server.tool(
  "publish_squad_graph",
  "Publish a complete squad blueprint with agents, workflows, and optional review policy.",
  {
    squad: z
      .object({
        name: z.string(),
        displayName: z.string(),
        description: z.string().optional(),
        outcome: z.string().optional(),
      })
      .describe("Squad metadata"),
    agents: z
      .array(
        z.object({
          key: z.string(),
          name: z.string(),
          role: z.string(),
          displayName: z.string().optional(),
        }),
      )
      .describe("Agents in the squad"),
    workflows: z
      .array(
        z.object({
          key: z.string(),
          name: z.string(),
          steps: z.array(z.record(z.unknown())),
          exitCriteria: z.string().optional(),
        }),
      )
      .describe("Workflow definitions"),
    reviewPolicy: z.string().optional().describe("Optional review policy"),
  },
  async (args) => {
    const res = await fetch(`${API_BASE}/api/specs/squad`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(args),
    });
    const data = await res.json();
    if (data.error) {
      return { content: [{ type: "text", text: `Error: ${data.error}` }], isError: true };
    }
    return { content: [{ type: "text", text: `Squad published: ${data.squadId}` }] };
  },
);

const transport = new StdioServerTransport();
await server.connect(transport);
