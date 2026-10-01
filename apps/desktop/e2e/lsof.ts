/** Return every named lsof -Fn entry. Bare `n` records have no path to verify. */
export function parseLsofPaths(output: string): string[] {
  return output.split(/\r?\n/).filter(line => line.startsWith('n') && line.length > 1).map(line => line.slice(1));
}
