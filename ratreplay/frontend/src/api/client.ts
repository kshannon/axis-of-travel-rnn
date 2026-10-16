import { decodeColumns } from "./arrow";
import type {
  AttachBody, BlockArrays, BlockHeader, BlockIndex, Edit, FormatContract, OpenApiDocument, Review, ReviewBody, ReviewPreview,
  SavedReview, SessionArrays, SessionHeader, SessionRow, SettingsAnswer, Source, WindowSettings,
} from "./types";

const SOURCES = "/api/sources";
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

export const listSources = () => json<Source[]>("GET", SOURCES);
export const attachSource = (body: AttachBody) => json<Source>("POST", SOURCES, body);
export const detachSource = (sid: string) => json<{ detached: string }>("DELETE", `${SOURCES}/${sid}`);

export const listSessions = (sid: string) => json<SessionRow[]>("GET", `${SOURCES}/${sid}/sessions`);
export const getSession = (sid: string, sessionId: string) =>
  json<SessionHeader>("GET", `${SOURCES}/${sid}/sessions/${sessionId}`);
export const getSessionArrays = (sid: string, sessionId: string) =>
  columns<SessionArrays>(`${SOURCES}/${sid}/sessions/${sessionId}/arrays`);

export const getReview = (sid: string, sessionId: string) =>
  json<Review | null>("GET", `${SOURCES}/${sid}/sessions/${sessionId}/review`);
export const putReview = (sid: string, sessionId: string, body: ReviewBody) =>
  json<SavedReview>("PUT", `${SOURCES}/${sid}/sessions/${sessionId}/review`, body);
export const previewReview = (sid: string, sessionId: string, edits: Edit[]) =>
  json<ReviewPreview>("POST", `${SOURCES}/${sid}/sessions/${sessionId}/review/preview`, { edits });

export const listBlocks = (sid: string, settings: Partial<WindowSettings> = {}) =>
  json<BlockIndex>("GET", withSettings(`${SOURCES}/${sid}/blocks`, settings));
export const getBlock = (sid: string, blockId: string, settings: Partial<WindowSettings> = {}) =>
  json<BlockHeader>("GET", withSettings(`${SOURCES}/${sid}/blocks/${blockId}`, settings));
export const getBlockArrays = (sid: string, blockId: string) =>
  columns<BlockArrays>(`${SOURCES}/${sid}/blocks/${blockId}/arrays`);

export const getWindowSettings = () => json<SettingsAnswer>("GET", WINDOW_SETTINGS);
export const putWindowSettings = (settings: WindowSettings, source: string) =>
  json<SettingsAnswer & { overwrote: boolean }>("PUT", WINDOW_SETTINGS, { settings, source });

export const getFormat = () => json<FormatContract>("GET", "/api/format");
export const getOpenApi = () => json<OpenApiDocument>("GET", "/api/openapi.json");
