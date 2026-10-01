import { appendToken } from './auth';

/**
 * Extracts the filename from a raw filesystem path, tolerating either
 * forward or back slashes.
 *
 * The backend stores document/face paths via Python's `os.path.join`, which
 * uses backslashes on Windows (confirmed directly against a live
 * `border_mesh.db`: e.g. `C:\Users\...\uploads\documents\abc.jpg`). Splitting
 * only on '/' leaves a Windows-style path completely unsplit -- `.pop()`
 * then returns the whole absolute path instead of just the filename,
 * breaking every document image, tamper heatmap comparison, and PDF export
 * on a Windows deployment.
 */
export function basenameFromPath(path: string): string {
  const parts = path.split(/[\\/]/);
  return parts[parts.length - 1];
}

/**
 * Builds the served URL for a document image from its raw stored path
 * (which may be an already-absolute http(s) URL, or a raw filesystem path
 * with either slash convention).
 *
 * Appends the officer's session token as a query param (see lib/auth.ts's
 * appendToken) -- the backend's /uploads route now requires real officer
 * login like every other route, and an <img src="..."> has no way to send
 * an Authorization header.
 */
export function buildUploadedDocumentUrl(rawPath: string): string {
  if (rawPath.startsWith('http')) return rawPath;
  return appendToken(`/uploads/documents/${basenameFromPath(rawPath)}`);
}
