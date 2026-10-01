/** One automatic check per authenticated device session and configured feed. */
export class UpdateDiscovery {
  #seen = new Set<string>();
  shouldCheck(state: {server: string; feed: string; account: {id: string; must_change_password: boolean} | null; identityVerified: boolean; canCheck: boolean}): boolean {
    if (!state.account) { this.#seen.clear(); return false; }
    if (!state.identityVerified || state.account.must_change_password || !state.canCheck) return false;
    const key = `${state.server}|${state.account.id}|${state.feed}`;
    if (this.#seen.has(key)) return false;
    this.#seen.add(key); return true;
  }
}
