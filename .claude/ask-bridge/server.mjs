/**
 * ask-bridge MCP Server
 *
 * Provides an `ask_user` tool that replaces Claude's built-in AskUserQuestion.
 * Communicates with the parent wrapper process via named pipes (FIFOs):
 *   - ASK_BRIDGE_Q_PIPE: server writes questions here
 *   - ASK_BRIDGE_A_PIPE: server reads answers from here
 *
 * If pipes are not configured, returns hardcoded first-option answers (test mode).
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { readFileSync, writeFileSync, openSync, closeSync } from "fs";

const Q_PIPE = process.env.ASK_BRIDGE_Q_PIPE;
const A_PIPE = process.env.ASK_BRIDGE_A_PIPE;
const TEST_MODE = !Q_PIPE || !A_PIPE;

function log(msg) {
  process.stderr.write(`[ask-bridge] ${msg}\n`);
}

log(`Starting. Mode: ${TEST_MODE ? "TEST (hardcoded answers)" : "INTERACTIVE"}`);
if (!TEST_MODE) {
  log(`Q pipe: ${Q_PIPE}`);
  log(`A pipe: ${A_PIPE}`);
}

/**
 * Ask the user via named pipes.
 * Writes the full question payload as JSON to the Q pipe,
 * then blocks reading the answer from the A pipe.
 */
function askViaFifo(payload) {
  // Write question to the Q pipe (blocks until reader opens it)
  const qfd = openSync(Q_PIPE, "w");
  const data = JSON.stringify(payload) + "\n";
  writeFileSync(qfd, data);
  closeSync(qfd);

  // Read answer from the A pipe (blocks until writer sends data)
  const afd = openSync(A_PIPE, "r");
  const answer = readFileSync(afd, "utf-8").trim();
  closeSync(afd);

  return JSON.parse(answer);
}

/**
 * Auto-answer by picking the first option for each question (test mode).
 */
function autoAnswer(questions) {
  const answers = {};
  for (const q of questions) {
    const opts = q.options || [];
    answers[q.question] = opts.length > 0 ? opts[0].label : "auto-answer";
  }
  return answers;
}

const server = new McpServer({
  name: "ask-bridge",
  version: "1.0.0",
});

server.tool(
  "ask_user",
  `Ask the user a question and get their answer. Use this whenever you need user input, preferences, or decisions.
Supports 1-4 questions per call. Each question has a header, question text, and 2-4 options.
The user can also provide free-text answers beyond the listed options.`,
  {
    questions: z
      .array(
        z.object({
          question: z.string().describe("The question to ask the user"),
          header: z
            .string()
            .describe("Short label for the question (max 12 chars)"),
          options: z
            .array(
              z.object({
                label: z.string().describe("Short option label (1-5 words)"),
                description: z
                  .string()
                  .describe("Explanation of this option"),
              })
            )
            .min(2)
            .max(4)
            .describe("Available choices"),
          multiSelect: z
            .boolean()
            .default(false)
            .describe("Allow selecting multiple options"),
        })
      )
      .min(1)
      .max(4)
      .describe("Questions to ask (1-4)"),
  },
  async ({ questions }) => {
    log(`Received ${questions.length} question(s)`);

    let answers;

    if (TEST_MODE) {
      log("TEST MODE: auto-answering with first option");
      answers = autoAnswer(questions);
    } else {
      log("Sending questions to wrapper via FIFO...");
      try {
        answers = askViaFifo({ questions });
        log(`Received answers: ${JSON.stringify(answers)}`);
      } catch (err) {
        log(`FIFO error: ${err.message}. Falling back to auto-answer.`);
        answers = autoAnswer(questions);
      }
    }

    // Format response for Claude
    const parts = [];
    for (const q of questions) {
      const answer = answers[q.question] || "no answer provided";
      parts.push(`Q: ${q.question}\nA: ${answer}`);
    }

    return {
      content: [{ type: "text", text: parts.join("\n\n") }],
    };
  }
);

const transport = new StdioServerTransport();
await server.connect(transport);
log("Connected and ready.");
