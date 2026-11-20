import { CopyButton } from "./copy-button";
import { highlight, type Lang } from "./highlight";

const LANG_LABEL: Record<Lang, string> = {
  json: "JSON",
  bash: "Shell",
  http: "HTTP",
  text: "Text",
  toml: "TOML",
};

// A code block with a header (title or language), a real copy button and
// build-time highlighting. The <pre> scrolls on its own, so a long curl
// line never widens the page on a phone; it is focusable so a keyboard
// user can scroll it too.
export function CodeBlock({
  code,
  lang = "text",
  title,
  copy = true,
  className,
}: {
  code: string;
  lang?: Lang | "sh";
  title?: string;
  copy?: boolean;
  className?: string;
}) {
  const l: Lang = lang === "sh" ? "bash" : lang;
  return (
    <figure className={"dx-code" + (className ? " " + className : "")}>
      <figcaption className="dx-code-head">
        {title ? <span className="dx-code-title">{title}</span> : null}
        <span className="dx-code-lang">{LANG_LABEL[l]}</span>
        {copy ? <CopyButton value={code} /> : null}
      </figcaption>
      <pre tabIndex={0} aria-label={title ? `${title} (${LANG_LABEL[l]})` : `${LANG_LABEL[l]} example`}>
        <code>{highlight(code, l)}</code>
      </pre>
    </figure>
  );
}

// A one-line value with a copy button: the base URL, the MCP endpoint.
export function CopyField({ value, method, label }: { value: string; method?: string; label?: string }) {
  return (
    <div className="dx-field">
      {method ? <span className="dx-field-method">{method}</span> : null}
      <code aria-label={label}>{value}</code>
      <CopyButton value={value} />
    </div>
  );
}

export function C({ children }: { children: React.ReactNode }) {
  return <code className="dx-ic">{children}</code>;
}
