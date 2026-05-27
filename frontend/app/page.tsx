"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  files?: { name: string; path: string }[];
}

export default function HomePage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<{ name: string; path: string }[]>([]);
  const [sessionId] = useState(() => crypto.randomUUID());
  const chatEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleUpload(files: FileList | null) {
    if (!files || files.length === 0) return;
    setBusy(true);

    // Show file names immediately for instant feedback
    const fileList = Array.from(files);
    const pendingFiles = fileList.map((f) => ({ name: f.name, path: "上传中..." }));
    setUploadedFiles((prev) => [...prev, ...pendingFiles]);

    const form = new FormData();
    fileList.forEach((f) => form.append("files", f));

    try {
      const res = await fetch("/api/upload", { method: "POST", body: form });
      const data = await res.json();
      if (data.files) {
        const added = data.files.map((f: { original_name: string; path: string }) => ({
          name: f.original_name,
          path: f.path,
        }));
        // Replace pending entries with confirmed ones
        setUploadedFiles((prev) => [...prev.filter((p) => p.path !== "上传中..."), ...added]);
      } else if (data.detail) {
        console.error("上传失败:", data.detail);
      }
    } catch (e) {
      console.error("上传失败", e);
      // Remove pending files on error
      setUploadedFiles((prev) => prev.filter((p) => p.path !== "上传中..."));
    } finally {
      setBusy(false);
      // Reset file input so same file can be re-uploaded
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      if (input) input.value = "";
    }
  }

  async function handleSend(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;

    const fileHint = uploadedFiles.length
      ? `\n\n[已上传文件: ${uploadedFiles.map((f) => f.path).join(", ")}]`
      : "";

    const userMsg: ChatMessage = {
      role: "user",
      content: text,
      files: uploadedFiles.length > 0 ? uploadedFiles : undefined,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setBusy(true);

    const assistantMsg: ChatMessage = { role: "assistant", content: "正在处理中，请稍候..." };
    setMessages((prev) => [...prev, assistantMsg]);

    try {
      // Submit as non-streaming to avoid Edge Function timeout
      const submitRes = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: [
            ...messages.map((m) => ({ role: m.role, content: m.content })),
            { role: "user", content: text + fileHint },
          ],
          session_id: sessionId,
          stream: false,
        }),
      });

      if (!submitRes.ok) throw new Error("服务器无响应");
      const { task_id } = await submitRes.json();
      if (!task_id) throw new Error("未获取到任务ID");

      // Poll for result every 3 seconds
      let dots = 0;
      const maxPolls = 200; // ~10 min
      for (let i = 0; i < maxPolls; i++) {
        await new Promise((r) => setTimeout(r, 3000));
        const pollRes = await fetch(`/api/chat/result/${task_id}`);
        if (!pollRes.ok) continue;
        const data = await pollRes.json();

        if (data.status === "completed") {
          const content = data.choices?.[0]?.message?.content ?? "分析完成，无内容返回。";
          setMessages((prev) => {
            const next = [...prev];
            next[next.length - 1] = { role: "assistant", content };
            return next;
          });
          break;
        }
        if (data.status === "error") {
          throw new Error(data.error || "处理失败");
        }
        dots = (dots + 1) % 4;
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = { role: "assistant", content: "正在处理中" + ".".repeat(dots + 1) };
          return next;
        });
      }
    } catch (e) {
      const errMsg = `错误: ${(e as Error).message}`;
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = { role: "assistant", content: errMsg };
        return next;
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ maxWidth: 800, margin: "0 auto", padding: "1rem", fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ margin: 0 }}>LA Review 权限核对智能体</h1>
      <p style={{ color: "#666", marginTop: 4 }}>
        上传系统账号清单与HR人员名单，智能体将自动识别表结构并完成权限核对分析。
      </p>

      {/* 文件上传区域 */}
      <label
        style={{
          display: "block",
          border: "2px dashed #ccc",
          borderRadius: 8,
          padding: "1.5rem",
          textAlign: "center",
          cursor: "pointer",
          marginBottom: 16,
          background: "#fafafa",
        }}
      >
        <input
          type="file"
          multiple
          accept=".csv,.xlsx,.xls"
          onChange={(e) => handleUpload(e.target.files)}
          style={{ display: "none" }}
        />
        拖拽或点击上传 CSV / Excel 文件
      </label>

      {uploadedFiles.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <strong>已上传文件：</strong>
          <ul style={{ margin: 4, paddingLeft: 20 }}>
            {uploadedFiles.map((f, i) => (
              <li key={i}>{f.name}</li>
            ))}
          </ul>
        </div>
      )}

      {/* 对话消息区 */}
      <div
        style={{
          border: "1px solid #e5e5e5",
          borderRadius: 8,
          padding: "1rem",
          minHeight: 300,
          maxHeight: 500,
          overflowY: "auto",
          marginBottom: 16,
          background: "#fff",
        }}
      >
        {messages.length === 0 && (
          <p style={{ color: "#999", textAlign: "center", marginTop: 120 }}>
            上传文件后输入需求，智能体将自动完成权限核对。
          </p>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              marginBottom: 12,
              textAlign: msg.role === "user" ? "right" : "left",
            }}
          >
            <div
              style={{
                display: "inline-block",
                maxWidth: "85%",
                padding: "8px 14px",
                borderRadius: 12,
                background: msg.role === "user" ? "#0070f3" : "#f3f3f3",
                color: msg.role === "user" ? "#fff" : "#111",
                whiteSpace: "pre-wrap",
                textAlign: "left",
              }}
            >
              {msg.role === "user" ? (
                <>
                  {msg.content}
                  {msg.files && msg.files.length > 0 && (
                    <div style={{ fontSize: "0.8em", opacity: 0.8, marginTop: 4 }}>
                      {msg.files.map((f) => f.name).join(", ")}
                    </div>
                  )}
                </>
              ) : (
                <ChatContent text={msg.content || (busy ? "思考中..." : "")} />
              )}
            </div>
          </div>
        ))}
        <div ref={chatEnd} />
      </div>

      {/* 输入区 */}
      <form onSubmit={handleSend} style={{ display: "flex", gap: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="例如：请帮我核对这些文件的权限"
          disabled={busy}
          style={{
            flex: 1,
            padding: "10px 14px",
            borderRadius: 8,
            border: "1px solid #ccc",
            fontSize: 14,
          }}
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          style={{
            padding: "10px 20px",
            borderRadius: 8,
            background: busy ? "#ccc" : "#0070f3",
            color: "#fff",
            border: "none",
            cursor: busy ? "not-allowed" : "pointer",
            fontSize: 14,
          }}
        >
          发送
        </button>
      </form>
    </main>
  );
}

/** 渲染助手的 Markdown 文本。 */
function ChatContent({ text }: { text: string }) {
  if (!text) return null;

  // Escape HTML first, then collapse excessive blank lines
  const rawLines = text.split("\n");
  const cleanLines: string[] = [];
  for (const line of rawLines) {
    const trimmed = line.trim();
    if (trimmed) {
      cleanLines.push(trimmed);
    } else if (cleanLines.length > 0 && cleanLines[cleanLines.length - 1] !== "") {
      cleanLines.push(""); // at most one blank line between paragraphs
    }
  }
  // Remove trailing empty line
  while (cleanLines.length > 0 && cleanLines[cleanLines.length - 1] === "") {
    cleanLines.pop();
  }
  let html = cleanLines.join("\n")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Block-level elements (before line-break conversion)
  // Tables: convert | col | col | patterns to HTML tables
  html = renderTables(html);

  // Strip newlines between HTML tags (artifacts from table joining)
  html = html.replace(/>\n+</g, "><");

  // Headings
  html = html.replace(/^#### (.+)$/gm, "<h4>$1</h4>");
  html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
  html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");

  // Horizontal rules
  html = html.replace(/^---$/gm, "<hr/>");

  // Inline formatting
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

  // Links: rewrite /download/... to /api/download/... so they go through the Next.js proxy
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_match, text, url) => {
    const resolved = url.startsWith("/download/") ? `/api/download/${url.slice("/download/".length)}` : url;
    // Only allow http, https, relative paths, and anchors
    if (/^(https?:\/\/|\/|\.\/|\.\.\/|#)/.test(resolved)) {
      return `<a href="${resolved}" target="_blank" rel="noopener noreferrer" style="color:#0070f3;text-decoration:underline">${text}</a>`;
    }
    return text;
  });

  // Line breaks: double newlines → paragraph break, single → <br/>
  html = html.replace(/\n\n/g, "</p><p>");
  html = html.replace(/\n/g, "<br/>");
  html = "<p>" + html + "</p>";

  // Strip any remaining newlines that pre-wrap would render as blank lines
  html = html.replace(/\n/g, "");

  return <span dangerouslySetInnerHTML={{ __html: html }} />;
}

/** Convert markdown tables to HTML tables. */
function renderTables(text: string): string {
  const lines = text.split("\n");
  const result: string[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    // Detect table: line with | that's not just a separator
    if (line.includes("|") && !line.match(/^[\s\|:-]+$/)) {
      const tableLines: string[] = [line];
      let j = i + 1;
      // Collect table rows
      while (j < lines.length) {
        const next = lines[j];
        if (next.includes("|") && !next.match(/^[\s\|:-]+$/)) {
          tableLines.push(next);
          j++;
        } else if (next.match(/^[\s\|:-]+$/)) {
          // separator row, skip it
          j++;
        } else {
          break;
        }
      }
      if (tableLines.length >= 1) {
        result.push("<table>");
        for (const row of tableLines) {
          const cells = row.split("|").filter((c) => c.trim() !== "");
          const tag = tableLines.indexOf(row) === 0 ? "th" : "td";
          result.push("<tr>");
          for (const cell of cells) {
            result.push(`<${tag}>${cell.trim()}</${tag}>`);
          }
          result.push("</tr>");
        }
        result.push("</table>");
        i = j;
        continue;
      }
    }
    result.push(line);
    i++;
  }
  return result.join("\n");
}
