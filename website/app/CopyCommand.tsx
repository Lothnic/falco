"use client";

import { useEffect, useRef, useState } from "react";

type CopyCommandProps = {
  index: string;
  label: string;
  command: string;
  note?: string;
};

export default function CopyCommand({ index, label, command, note }: CopyCommandProps) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(command);
    } catch {
      const field = document.createElement("textarea");
      field.value = command;
      field.setAttribute("readonly", "");
      field.style.position = "fixed";
      field.style.opacity = "0";
      document.body.appendChild(field);
      field.select();
      document.execCommand("copy");
      field.remove();
    }

    setCopied(true);
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setCopied(false), 1800);
  }

  return (
    <div className="command-block">
      <div className="command-head">
        <span>
          {index} / {label}
        </span>
        <button type="button" onClick={copy} aria-label={`Copy ${label.toLowerCase()} command`}>
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre>
        <code>{command}</code>
      </pre>
      {note ? <p className="command-note">{note}</p> : null}
      <span className="sr-only" role="status">
        {copied ? "Command copied" : ""}
      </span>
    </div>
  );
}
