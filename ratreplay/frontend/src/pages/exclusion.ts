import type { ExclusionSaved } from "../api/types";
import { toast } from "../ui/toast";
import { exclusionPrompt, exclusionToast } from "./exclusion-view";

/** Ask for the note, make the change and toast it naming the review file. Gives back what the server wrote, none when the person cancelled the prompt. */
export async function askAndChange(sessionId: string, excluded: boolean, change: (note: string) => Promise<ExclusionSaved>): Promise<ExclusionSaved | null> {
  const note = prompt(exclusionPrompt(sessionId, excluded), "");
  if (note === null) return null;
  const saved = await change(note.trim());
  const { kind, text } = exclusionToast(sessionId, excluded, saved);
  toast[kind](text, saved.file);
  return saved;
}
