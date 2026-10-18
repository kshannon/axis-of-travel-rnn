import { decodeColumns } from "./arrow";
import type {
  BlockArrays, BlockHeader, BlockWindows, ExclusionSaved, FormatContract, Health, OpenApiDocument, Preview, PreviewBody, Readiness, Rebuilt,
  SaveBody, SavedBlocks, Selected, SelectedResult, SessionArrays, SessionHeader, SessionRow, WindowSettings,
} from "./types";

const HEALTH = "/api/health";
const SESSIONS = "/api/sessions";
const REBUILD = "/api/rebuild";
const BLOCKS = "/api/blocks";
const WINDOWS = "/api/windows";
const REAL = "real";
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

/** The url with the settings as query parameters, which is where a GET carries them. */
function withSettings(url: string, settings: Partial<WindowSettings> & { which?: string }): string {
  const query = new URLSearchParams(Object.entries(settings).map(([name, value]) => [name, String(value)]));
  return query.size ? `${url}?${query}` : url;
}

// The Data page: the folders, and rebuilding every reviewed session.
export const getHealth = (reload = false) => json<Health>("GET", reload ? `${HEALTH}?reload=true` : HEALTH);
export const rebuildAll = (settings: WindowSettings) => json<Rebuilt>("POST", REBUILD, { settings });

// The Sessions and Replay pages.
export const listSessions = () => json<SessionRow[]>("GET", SESSIONS);
export const getSession = (sessionId: string, settings: Partial<WindowSettings> = {}) =>
  json<SessionHeader>("GET", withSettings(`${SESSIONS}/${sessionId}`, settings));
export const getSessionArrays = (sessionId: string) => columns<SessionArrays>(`${SESSIONS}/${sessionId}/arrays`);
export const previewEdits = (sessionId: string, body: PreviewBody) => json<Preview>("POST", `${SESSIONS}/${sessionId}/preview`, body);
export const saveBlocks = (sessionId: string, body: SaveBody) => json<SavedBlocks>("PUT", `${SESSIONS}/${sessionId}/blocks`, body);
export const setExclusion = (sessionId: string, excluded: boolean, note: string, settings: WindowSettings) =>
  json<ExclusionSaved>("PUT", `${SESSIONS}/${sessionId}/exclusion`, { excluded, note, settings });

// The Blocks and Windows pages.
export const listBlocks = (settings: Partial<WindowSettings> = {}, which = REAL) =>
  json<Readiness>("GET", withSettings(BLOCKS, { which, ...settings }));
export const getBlock = (blockId: string) => json<BlockHeader>("GET", `${BLOCKS}/${blockId}`);
export const getBlockArrays = (blockId: string) => columns<BlockArrays>(`${BLOCKS}/${blockId}/arrays`);
export const getBlockWindows = (blockId: string, settings: Partial<WindowSettings> = {}) =>
  json<BlockWindows>("GET", withSettings(`${BLOCKS}/${blockId}/windows`, settings));
export const getSelected = () => json<Selected>("GET", WINDOWS);
export const selectSettings = (settings: WindowSettings) => json<SelectedResult>("PUT", WINDOWS, { settings });

export const getFormat = () => json<FormatContract>("GET", "/api/format");
export const getOpenApi = () => json<OpenApiDocument>("GET", "/api/openapi.json");
