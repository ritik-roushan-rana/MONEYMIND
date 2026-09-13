const KEY = "moneymind.accounts";

export interface StoredAccount { id: string; label: string; createdAt: string }

export function listAccounts(): StoredAccount[] {
  try { return JSON.parse(localStorage.getItem(KEY) ?? "[]"); } catch { return []; }
}
export function rememberAccount(a: StoredAccount) {
  const rest = listAccounts().filter((x) => x.id !== a.id);
  localStorage.setItem(KEY, JSON.stringify([a, ...rest].slice(0, 10)));
}
export function forgetAccount(id: string) {
  localStorage.setItem(KEY, JSON.stringify(listAccounts().filter((x) => x.id !== id)));
}
export const accountLabel = (id: string) => listAccounts().find((a) => a.id === id)?.label ?? `Account ${id.slice(0, 8)}`;
