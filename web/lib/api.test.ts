import { describe, expect, it, vi } from "vitest";
import { askStream } from "./api";

/**
 * Builds a fake fetch Response whose body streams `chunks` verbatim, so a test can
 * control exactly where the network splits the byte stream.
 */
function streamingResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(body, { status: 200 });
}

function mockFetch(chunks: string[]) {
  vi.stubGlobal("fetch", vi.fn(async () => streamingResponse(chunks)));
}

// sse-starlette terminates lines with CRLF. Every frame below uses \r\n deliberately —
// rewriting them to \n would make these tests pass against the bug they exist to catch.
const CRLF_FRAMES =
  "event: token\r\ndata: The\r\n\r\n" +
  "event: token\r\ndata:  ARR\r\n\r\n" +
  "event: token\r\ndata:  is $12.4M\r\n\r\n" +
  'event: citations\r\ndata: [{"marker":1,"source":"pitch.md","page":null,"snippet":"x"}]\r\n\r\n';

describe("askStream SSE parsing", () => {
  it("renders tokens from CRLF-terminated frames", async () => {
    // The failure this catches: the client split frames on "\n\n", which never occurs
    // in a "\r\n\r\n" stream. Every frame stayed in the buffer, the end-of-stream flush
    // handed the whole response to the frame parser at once, JSON.parse threw, and the
    // catch swallowed it — so the UI showed a caret and never a single token, with a
    // 200 on the wire and nothing in the console.
    mockFetch([CRLF_FRAMES]);
    const tokens: string[] = [];
    const { citations } = await askStream("q", [], (t) => tokens.push(t));

    expect(tokens.join("")).toBe("The ARR is $12.4M");
    expect(citations).toHaveLength(1);
    expect(citations[0].source).toBe("pitch.md");
  });

  it("survives a CR and its LF arriving in different network chunks", async () => {
    // Frame boundaries do not respect packet boundaries. Normalising the decoded chunk
    // instead of the accumulated buffer would drop this frame separator entirely.
    mockFetch(["event: token\r\ndata: split\r", "\n\r\nevent: token\r\ndata: !\r\n\r\n"]);
    const tokens: string[] = [];
    await askStream("q", [], (t) => tokens.push(t));
    expect(tokens.join("")).toBe("split!");
  });

  it("preserves leading spaces inside token payloads", async () => {
    // SSE strips exactly one space after "data:", so a token that is itself a leading
    // space must survive. Losing it silently welds words together in the answer.
    mockFetch(["event: token\r\ndata:  gap\r\n\r\n"]);
    const tokens: string[] = [];
    await askStream("q", [], (t) => tokens.push(t));
    expect(tokens).toEqual([" gap"]);
  });

  it("ignores a malformed citations frame rather than failing the whole answer", async () => {
    mockFetch(["event: token\r\ndata: hi\r\n\r\nevent: citations\r\ndata: {oops\r\n\r\n"]);
    const tokens: string[] = [];
    const { citations } = await askStream("q", [], (t) => tokens.push(t));
    expect(tokens.join("")).toBe("hi");
    expect(citations).toEqual([]);
  });

  it("still parses a plain LF stream", async () => {
    // Nothing guarantees the server keeps CRLF forever; the parser must accept both.
    mockFetch(["event: token\ndata: lf\n\n"]);
    const tokens: string[] = [];
    await askStream("q", [], (t) => tokens.push(t));
    expect(tokens.join("")).toBe("lf");
  });
});
