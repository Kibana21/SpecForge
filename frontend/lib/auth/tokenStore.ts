/**
 * Module-level access token store.
 * The access token lives in memory only — never localStorage/sessionStorage.
 * This singleton is updated by AuthContext and read by the API client.
 */
let _token: string | null = null;

export const tokenStore = {
  get: (): string | null => _token,
  set: (t: string | null): void => {
    _token = t;
  },
};
