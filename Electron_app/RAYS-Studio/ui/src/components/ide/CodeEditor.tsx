import { useEffect, useMemo, useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

function detectLanguage(fileName: string): string {
  const extension = fileName.split(".").pop()?.toLowerCase() || "";
  if (["py", "pyi"].includes(extension)) return "python";
  if (["ts", "tsx"].includes(extension)) return "typescript";
  if (["js", "jsx", "mjs", "cjs"].includes(extension)) return "javascript";
  if (["json"].includes(extension)) return "json";
  if (["md", "markdown"].includes(extension)) return "markdown";
  if (["html", "htm"].includes(extension)) return "markup";
  if (["css", "scss"].includes(extension)) return "css";
  if (["yml", "yaml"].includes(extension)) return "yaml";
  if (["sh", "bash", "zsh"].includes(extension)) return "bash";
  return "text";
}

export function CodeEditor({
  fileName,
  fileContent,
  onLoadFile,
}: {
  fileName: string;
  fileContent?: string;
  onLoadFile: (filePath: string) => Promise<void> | void;
}) {
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    Promise.resolve(onLoadFile(fileName))
      .catch((error) => {
        if (!cancelled) {
          setLoadError(error instanceof Error ? error.message : "Failed to load file");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [fileName, onLoadFile]);

  const lines = useMemo(() => {
    if (loading) {
      return [`# ${fileName}`, "", "# Loading file content..."];
    }
    if (loadError) {
      return [`# ${fileName}`, "", `# ${loadError}`];
    }
    if (fileContent !== undefined) {
      return fileContent.split("\n");
    }
    return [`# ${fileName}`, "", "# File content unavailable"];
  }, [fileName, fileContent, loading, loadError]);
  const language = useMemo(() => detectLanguage(fileName), [fileName]);
  const content = useMemo(() => lines.join("\n"), [lines]);

  return (
    <div className="h-full overflow-auto bg-background font-mono-code text-code p-0">
      <SyntaxHighlighter
        language={language}
        style={oneDark}
        showLineNumbers
        wrapLongLines
        customStyle={{
          margin: 0,
          borderRadius: 0,
          background: "transparent",
          minHeight: "100%",
          padding: "8px 0",
          fontSize: "12px",
          lineHeight: "1.5",
        }}
        lineNumberStyle={{
          minWidth: "42px",
          paddingRight: "12px",
          color: "hsl(var(--muted-foreground) / 0.55)",
          userSelect: "none",
        }}
        codeTagProps={{ style: { fontFamily: "inherit" } }}
      >
        {content}
      </SyntaxHighlighter>
    </div>
  );
}
