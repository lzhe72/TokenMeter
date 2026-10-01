export class ClientError extends Error {
  code: string;
  constructor(code: string, message: string) { super(message); this.code = code; }
}
export function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new ClientError('invalid_input', '输入格式不正确');
  return value as Record<string, unknown>;
}
export function string(value: unknown, max = 2048): string {
  if (typeof value !== 'string' || !value.length || value.length > max) throw new ClientError('invalid_input', '输入长度不正确');
  return value;
}
export function boolean(value: unknown): boolean {
  if (typeof value !== 'boolean') throw new ClientError('invalid_input', '开关值不正确');
  return value;
}
export function canonicalOrigin(input: unknown): string {
  const text = string(input).trim();
  const fail = () => new ClientError('invalid_server_url', '服务地址仅支持 HTTPS 或本机回环 HTTP，且不能包含路径、凭据或参数');
  const authority = text.match(/^https?:\/\/([^/?#]+)\/?$/i)?.[1];
  if (!authority || authority.endsWith(':') || /[\s\\%@]/.test(authority)) throw fail();
  let url: URL; try { url = new URL(text); } catch { throw fail(); }
  if (url.username || url.password || url.search || url.hash || !['http:', 'https:'].includes(url.protocol)) throw fail();
  const rawHost = authority.startsWith('[') ? authority.slice(0, authority.indexOf(']') + 1) : authority.split(':')[0];
  if (url.protocol === 'http:' && !['127.0.0.1', 'localhost', '[::1]'].includes(rawHost.toLowerCase())) throw fail();
  if (url.port === '0') throw fail();
  return url.origin;
}
