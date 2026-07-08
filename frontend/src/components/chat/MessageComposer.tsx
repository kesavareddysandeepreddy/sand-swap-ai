import { useState } from "react";
import type { FormEvent } from "react";

interface MessageComposerProps {
  isSending: boolean;
  onSendMessage: (message: string) => Promise<void>;
}

export const MessageComposer = ({ isSending, onSendMessage }: MessageComposerProps) => {
  const [value, setValue] = useState<string>("");

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!value.trim() || isSending) {
      return;
    }

    const payload = value;
    setValue("");
    await onSendMessage(payload);
  };

  return (
    <form className="composer" onSubmit={submit}>
      <textarea
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Ask SandSwap AI something..."
        rows={3}
        disabled={isSending}
      />
      <button type="submit" disabled={isSending || !value.trim()}>
        Send
      </button>
    </form>
  );
};
