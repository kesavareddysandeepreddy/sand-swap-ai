import type { FormEvent, KeyboardEvent } from "react";
import { useState } from "react";

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

    const handleComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            if (!value.trim() || isSending) {
                return;
            }
            void onSendMessage(value);
            setValue("");
        }
    };

    return (
        <form className="composer" onSubmit={submit}>
            <textarea
                className="composer-input"
                value={value}
                onChange={(event) => setValue(event.target.value)}
                onKeyDown={handleComposerKeyDown}
                placeholder="Ask SandSwap AI something..."
                rows={1}
                disabled={isSending}
            />
            <button className="composer-send" type="submit" disabled={isSending || !value.trim()}>
                {isSending ? <span className="button-spinner" aria-hidden="true" /> : null}
                {isSending ? "Sending" : "Send"}
            </button>
        </form>
    );
};
