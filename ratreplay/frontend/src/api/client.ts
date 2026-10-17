import { decodeColumns } from "./arrow";
import type {
  BlockArrays, BlockHeader, BlockIndex, Edit, FormatContract, OpenApiDocument, Review, ReviewBody, ReviewPreview,
  SavedReview, SessionArrays, SessionHeader, SessionRow, SettingsAnswer, Sources, WindowSettings,
} from "./types";

const SOURCES = "/api/sources";
const SESSIONS = "/api/sessions";
const BLOCKS = "/api/blocks";
const WINDOW_SETTINGS = "/api/windows/settings";
const UNREACHABLE = "Cannot reach the API, is it running?";

/** A request the API refused, or could not be made (status 0): the status and the text of its {"error"} body. */
export class ApiError extends Error {
  constructor(readonly status: number, readonly error: string) {
    super(error);
  }
}

/** What to tell the person about a failed call. */
export function errorText(error: unknown): string {
  return error instanceof ApiError ? error.error : String(error);
}

async function request(method: string, url: string, body?: unknown): Promise<Response> {
  const response = await fetch(url, {
    method,
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).catch(() => {
    throw new ApiError(0, UNREACHABLE);
  });
  if (!response.ok) {
    const failure = await response.json().catch(() => ({}));
    throw new ApiError(response.status, failure.error ?? response.statusText);
  }
  return response;
}

async function json<T>(method: string, url: string, body?: unknown): Promise<T> {
  return (await request(method, url, body)).json();
}

async function columns<T>(url: string): Promise<T> {
  return decodeColumns(await (await request("GET", url)).arrayBuffer()) as unknown as T;
}

function withSettings(url: string, settings: Partial<WindowSettings>): string {
  const query = new URLSearchParams(Object.entries(settings).map(([name, value]) => [name, String(value)]));
  return query.size ? `${url}?${query}` : url;
}

export const getSources = (reload = false) => json<Sources>("GET", reload ? `${SOURCES}?reload=true` : SOURCES);

export const listSessions = () => json<SessionRow[]>("GET", SESSIONS);
export const getSession = (sessionId: string) => json<SessionHeader>("GET", `${SESSIONS}/${sessionId}`);
export const getSessionArrays = (sessionId: string) => columns<SessionArrays>(`${SESSIONS}/${sessionId}/arrays`);

export const getReview = (sessionId: string) => json<Review | null>("GET", `${SESSIONS}/${sessionId}/review`);
export const putReview = (sessionId: string, body: ReviewBody) => json<SavedReview>("PUT", `${SESSIONS}/${sessionId}/review`, body);
export const previewReview = (sessionId: string, edits: Edit[]) =>
  json<ReviewPreview>("POST", `${SESSIONS}/${sessionId}/review/preview`, { edits });

export const listBlocks = (settings: Partial<WindowSettings> = {}) => json<BlockIndex>("GET", withSettings(BLOCKS, settings));
export const getBlock = (blockId: string, settings: Partial<WindowSettings> = {}) =>
  json<BlockHeader>("GET", withSettings(`${BLOCKS}/${blockId}`, settings));
export const getBlockArrays = (blockId: string) => columns<BlockArrays>(`${BLOCKS}/${blockId}/arrays`);

export const getWindowSettings = () => json<SettingsAnswer>("GET", WINDOW_SETTINGS);
export const putWindowSettings = (settings: WindowSettings) =>
  json<SettingsAnswer & { overwrote: boolean }>("PUT", WINDOW_SETTINGS, { settings });

export const getFormat = () => json<FormatContract>("GET", "/api/format");
export const getOpenApi = () => json<OpenApiDocument>("GET", "/api/openapi.json");
