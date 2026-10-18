import { decodeColumns } from "./arrow";
import type {
  BlockArrays, BlockHeader, BlockWindows, EnvironmentEntry, ExclusionSaved, FormatContract, Health, OpenApiDocument, Preview, PreviewBody, Readiness, Rebuilt,
  SaveBody, SavedBlocks, Selected, SelectedResult, SessionArrays, SessionHeader, SessionRow, WindowSettings,
} from "./types";

const HEALTH = "/api/health";
const SESSIONS = "/api/sessions";
const REBUILD = "/api/rebuild";
const BLOCKS = "/api/blocks";
const WINDOWS = "/api/windows";
const REAL = "real";
const UNREACHABLE = "Cannot reach the API, is it running?";

// The version of the format contract this page is built for, and the keys of `/api/format` its pages cannot do without. An API
// that answers another version, or without a key, is not the one this page was built with.
export const FORMAT_VERSION = 1;
const NEEDED_KEYS = ["settings", "rules"] as const;
export const STALE_API = "The API is older than this page, restart it (pixi run ratreplay-api)";

/** A request the API refused, or could not be made (status 0): the status and the text of its {"error"} body. */
export class ApiError extends Error {
  constructor(readonly status: number, readonly error: string) {
    super(error);
  }
}

/** Thrown where a page meets an answer from an API older than itself, so the page can say to restart it and not fail on a missing key. */
export class StaleApiError extends Error {
  constructor() {
    super(STALE_API);
  }
}

/** Whether the answer of `/api/format` is not the contract this page expects: another version, or a key the pages need is missing. */
export function staleApi(format: Partial<FormatContract>): boolean {
  return format.version !== FORMAT_VERSION || NEEDED_KEYS.some((key) => format[key] === undefined);
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

// The Incoming and Outgoing pages: the folders, and rebuilding every reviewed session.
export const getHealth = (reload = false) => json<Health>("GET", reload ? `${HEALTH}?reload=true` : HEALTH);
export const rebuildAll = (settings: WindowSettings) => json<Rebuilt>("POST", REBUILD, { settings });

// The Incoming (sessions) and Replay pages.
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

// The Environments page.
export const getEnvironments = () => json<EnvironmentEntry[]>("GET", "/api/environments");

export const getFormat = () => json<FormatContract>("GET", "/api/format");
export const getOpenApi = () => json<OpenApiDocument>("GET", "/api/openapi.json");
