import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import type { Snapshot, SourceAccessSnapshot, SourceTool } from '../../shared/types';
import './style.css';
import appIcon from '../../../resources/TokenMeter.svg';

const messages: Record<string, string> = {invalid_credentials:'用户名或密码不正确', account_disabled:'账号已停用，请联系管理员', rate_limited:'尝试次数过多，请稍后重试', invalid_session:'会话已失效，请重新登录', forbidden:'当前账号没有此操作权限', password_change_required:'请先更改初始密码', password_unchanged:'新密码不能与当前密码相同', admin_protected:'不能停用自己或最后一位管理员', invalid_password:'临时密码需要 12 至 128 位', unsafe_storage:'本机凭据文件不安全，请检查文件后重新登录', invalid_server_url:'请输入 HTTPS 服务地址或本机回环 HTTP 地址', update_source_rejected:'更新地址无效，仅支持 HTTPS 或本机回环 HTTP', update_configuration_locked:'更新进行中，暂时不能修改更新源', network_unavailable:'无法连接服务，请检查地址和网络', logout_unconfirmed:'已清除本机凭据，服务端退出尚未确认', password_confirmation_mismatch:'两次输入的新密码不一致', server_configuration_locked:'切换服务前请先退出登录', operation_failed:'操作未完成，请重试'};
const describe = (code: string) => messages[code] ? `${messages[code]}（${code}）` : code;
Object.assign(messages, {update_download_failed:'无法获取更新，请检查更新服务是否已启动', update_source_rejected:'更新地址无效，仅支持 HTTPS 或本机回环 HTTP', update_transport_rejected:'更新请求被转向不允许的地址，已停止', update_signature_rejected:'更新签名验证失败，已停止安装', update_integrity_failed:'更新文件不完整，请重新下载', update_bundle_invalid:'更新应用验证失败，已停止安装', update_native_failed:'系统未能完成更新，请稍后重试', update_metadata_invalid:'更新清单格式不正确', update_cancelled:'更新已取消', update_unavailable:'当前没有可安装的更新'});
const roleName = (role: string) => role === 'admin' ? '管理员' : '成员';
const auditNames: Record<string,string> = {account_provisioned:'预置账号', password_changed:'更改密码', password_reset:'重置密码', account_disabled:'停用账号', account_enabled:'启用账号', login:'登录', logout:'退出登录'};
const sourceNames: Record<SourceTool, string> = {codex: 'Codex', claude_code: 'Claude Code'};
const sourceMessages: Record<string, string> = {
  access_denied: '无法访问已选目录，请重新选择', root_changed: '已选目录发生变化，请重新选择',
  tree_changed: '目录内容在读取时发生变化，请重新预览', unsafe_root: '已选目录不安全，请重新选择',
  source_unavailable: '来源暂不可用，请重新选择', source_key_unavailable: '本机密钥暂不可用，来源已停止读取',
  source_invalidation_failed: '来源停读状态未能安全保存，请检查后重新选择',
  source_access_denied: '当前来源不允许读取', source_operation_stale: '来源状态已变化，请重试',
  invalid_session: '请先验证团队身份', invalid_source_tool: '工具类型无效', invalid_selection: '目录选择已失效，请重新选择',
  picker_failed: '系统目录选择器未能完成操作', invalid_source_consent: '请选择采集与未来同步意愿',
  operation_busy: '来源操作正在进行，请稍后重试', operation_failed: '来源操作未完成，请重试'
};
const sourceLimitNames: Record<string, string> = {
  candidate_limit: '候选文件达到 1000 个上限', entry_limit: '已检查目录项达到 5000 个上限',
  depth_limit: '目录深度超过 8 层', time_limit: '预览达到 2 秒上限',
  tree_changed: '目录在预览时发生变化', io_error: '读取目录时发生错误'
};
function safeSourceCode(value: string | null | undefined): string | null {
  return value && /^[a-z_]{3,60}$/.test(value) ? value : null;
}
function sourceDate(value: number): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? '' : date.toISOString();
}
function Modal({title, children, onDismiss}: {title: string; children: React.ReactNode; onDismiss: () => void}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { const element = dialog.current!; const previous = document.activeElement as HTMLElement | null; element.showModal(); return () => {element.close(); previous?.focus();}; }, []);
  return <dialog ref={dialog} className="dialog" aria-label={title} onCancel={event => {event.preventDefault(); onDismiss();}}>{children}</dialog>;
}
function SourceCard({tool, view, ready, busy, sourceError, onSnapshot}: {
  tool: SourceTool; view: SourceAccessSnapshot[SourceTool]; ready: boolean; busy: boolean;
  sourceError: string | null; onSnapshot: (value: Snapshot) => void;
}) {
  const [working, setWorking] = useState(false);
  const [localCode, setLocalCode] = useState<string | null>(null);
  const [pendingChoice, setPendingChoice] = useState({selectionId: '', collectAllowed: false, syncIntent: false});
  const [confirmedChoice, setConfirmedChoice] = useState({sourceId: '', collectAllowed: false, syncIntent: false});
  const [previewedSelection, setPreviewedSelection] = useState<string | null>(null);
  const [refreshedSource, setRefreshedSource] = useState<string | null>(null);
  const [revokePrompt, setRevokePrompt] = useState(false);
  const pending = view.pending;
  const confirmed = view.confirmed;
  const locked = !ready || busy || working;
  const state = pending ? 'pending' : confirmed?.status ?? 'none';
  const pendingConsent = pendingChoice.selectionId === pending?.selectionId ? pendingChoice :
    {selectionId: pending?.selectionId ?? '', collectAllowed: false, syncIntent: false};
  const confirmedConsent = confirmedChoice.sourceId === confirmed?.sourceId ? confirmedChoice :
    {sourceId: confirmed?.sourceId ?? '', collectAllowed: confirmed?.collectAllowed ?? false,
      syncIntent: confirmed?.syncIntent ?? false};
  const canRefresh = !locked && !pending && confirmed?.status === 'confirmed_enabled';
  const currentCandidates = pending ?
    (previewedSelection === pending.selectionId ? pending.candidates : null) :
    (confirmed?.status === 'confirmed_enabled' && refreshedSource === confirmed.sourceId ? view.candidates : null);
  const incomplete = pending ? pending.incomplete : view.incomplete;
  const reason = pending ? pending.reason : view.reason;
  const errorCode = safeSourceCode(sourceError ?? localCode ??
    (confirmed?.status === 'needs_reselect' ? confirmed.reason : null));
  useEffect(() => {
    setPendingChoice({selectionId: pending?.selectionId ?? '', collectAllowed: false, syncIntent: false});
    setPreviewedSelection(null);
  }, [pending?.selectionId]);
  useEffect(() => {
    setConfirmedChoice({sourceId: confirmed?.sourceId ?? '', collectAllowed: confirmed?.collectAllowed ?? false,
      syncIntent: confirmed?.syncIntent ?? false});
  }, [confirmed?.sourceId, confirmed?.collectAllowed, confirmed?.syncIntent]);
  useEffect(() => { if (confirmed?.status !== 'confirmed_enabled') setRefreshedSource(null); }, [confirmed?.status, confirmed?.sourceId]);
  useEffect(() => { if (!confirmed) setRevokePrompt(false); }, [confirmed?.sourceId]);
  const run = async (call: () => Promise<Snapshot>): Promise<Snapshot | null> => {
    setWorking(true); setLocalCode(null);
    try {
      const result = await call();
      onSnapshot(result);
      setLocalCode(safeSourceCode(result.sourceErrors?.[tool]));
      return result;
    } catch {
      setLocalCode('operation_failed');
      return null;
    } finally { setWorking(false); }
  };
  const saveConsent = async (collectAllowed: boolean, syncIntent: boolean) => {
    if (!confirmed || confirmed.status === 'needs_reselect' || locked) return;
    const sourceId = confirmed.sourceId;
    setConfirmedChoice({sourceId, collectAllowed, syncIntent});
    setRefreshedSource(null);
    const result = await run(() => window.tokenmeter.updateSourceConsent({sourceId, collectAllowed, syncIntent}));
    const actual = result?.sources[tool].confirmed;
    setConfirmedChoice({sourceId: actual?.sourceId ?? sourceId,
      collectAllowed: actual?.collectAllowed ?? confirmed.collectAllowed,
      syncIntent: actual?.syncIntent ?? confirmed.syncIntent});
  };
  const statusLabel = pending ? '已选择目录，等待预览和确认' :
    confirmed?.status === 'confirmed_enabled' ? '已确认，允许采集' :
    confirmed?.status === 'confirmed_paused' ? '已确认，采集已暂停' :
    confirmed?.status === 'needs_reselect' ? '来源失效，需要重新选择' : '尚未选择来源';
  return <section className="source-card" aria-labelledby={`source-heading-${tool}`}>
    <div className="section-title split"><div><h3 id={`source-heading-${tool}`}>{sourceNames[tool]}</h3>
      <p data-testid={`source.status.${tool}`} data-state={state} role="status">{working && !pending ? '正在处理来源… · ' : ''}{statusLabel}</p></div>
      <button data-testid={`source.choose.${tool}`} disabled={locked} onClick={() => { void run(() => window.tokenmeter.chooseSource({tool})); }}>
        {confirmed ? '更换目录…' : '选择目录…'}
      </button></div>
    {confirmed && <div className="source-confirmed" data-testid={`source.confirmed.${tool}`}>
      <p>{confirmed.status === 'needs_reselect' ? '已停止读取。重新选择并确认目录后才能恢复。' :
        `采集${confirmed.collectAllowed ? '已开启' : '已暂停'}；未来同步意愿${confirmed.syncIntent ? '已开启' : '已关闭'}。`}</p>
    </div>}
    {pending && <div className="source-pending" data-testid={`source.pending.${tool}`}>
      <p>待确认目录：<strong>{pending.label}</strong>。选择目录本身不会开始采集。</p>
      <button data-testid={`source.preview.${tool}`} disabled={locked} onClick={() => {
        const selectionId = pending.selectionId;
        void run(() => window.tokenmeter.previewSource({selectionId})).then(result => {
          if (result && !result.sourceErrors[tool] && result.sources[tool].pending?.selectionId === selectionId)
            setPreviewedSelection(selectionId);
        });
      }}>预览候选文件</button>
    </div>}
    {currentCandidates && <div className="source-candidates">
      <p data-testid={`source.completeness.${tool}`} data-complete={String(!incomplete)} data-reason={incomplete ? reason ?? 'io_error' : ''}>
        {incomplete ? `预览不完整：${sourceLimitNames[reason ?? ''] ?? '需要重新检查目录'}` :
          `候选文件 ${currentCandidates.length} 个 · 已检查当前预览范围`}
      </p>
      {currentCandidates.length > 0 && <ul aria-label={`${sourceNames[tool]} 候选文件`}>{currentCandidates.map(item => {
        const mtime = sourceDate(item.mtimeMs);
        return <li key={item.relativeName}
          data-testid={`source.candidate.${tool}`} data-relative-name={item.relativeName}
          data-size-bytes={item.size} data-mtime-utc={mtime}>
          <span className="source-candidate-name">{item.relativeName}</span>
          <span>{item.size} B</span><time dateTime={mtime}>{mtime || '修改时间未知'}</time>
        </li>;
      })}</ul>}
      {currentCandidates.length === 0 && !incomplete && <p>当前预览范围内没有符合条件的 .jsonl 文件；仍可确认目录，等待今后的日志。</p>}
    </div>}
    {pending ? <div className="source-consent">
      <label className="checkbox"><input type="checkbox" data-testid={`source.collect.${tool}`}
        checked={pendingConsent.collectAllowed} disabled={locked}
        onChange={event => setPendingChoice({...pendingConsent, collectAllowed: event.target.checked})}/>允许从此目录采集</label>
      <label className="checkbox"><input type="checkbox" data-testid={`source.sync.${tool}`}
        checked={pendingConsent.syncIntent} disabled={locked}
        onChange={event => setPendingChoice({...pendingConsent, syncIntent: event.target.checked})}/>愿意在未来功能中同步用量</label>
      <p>同步功能尚未启用，此意愿不会立即上传数据。</p>
      <button className="primary" data-testid={`source.confirm.${tool}`} disabled={locked} onClick={() => {
        void run(() => window.tokenmeter.confirmSource({selectionId: pending.selectionId,
          collectAllowed: pendingConsent.collectAllowed, syncIntent: pendingConsent.syncIntent}));
      }}>确认来源与意愿</button>
    </div> : confirmed && confirmed.status !== 'needs_reselect' ? <div className="source-consent">
      <label className="checkbox"><input type="checkbox" data-testid={`source.collect.${tool}`}
        checked={confirmedConsent.collectAllowed} disabled={locked}
        onChange={event => { void saveConsent(event.target.checked, confirmedConsent.syncIntent); }}/>
        允许从此目录采集</label>
      <label className="checkbox"><input type="checkbox" data-testid={`source.sync.${tool}`}
        checked={confirmedConsent.syncIntent} disabled={locked}
        onChange={event => { void saveConsent(confirmedConsent.collectAllowed, event.target.checked); }}/>
        愿意在未来功能中同步用量</label>
    </div> : null}
    <div className="source-actions">
      <button data-testid={`source.refresh.${tool}`} disabled={!canRefresh} onClick={() => {
        if (!confirmed) return;
        const sourceId = confirmed.sourceId;
        void run(() => window.tokenmeter.refreshSource({sourceId})).then(result => {
          const current = result?.sources[tool];
          if (current?.confirmed?.sourceId === sourceId &&
              (!result?.sourceErrors[tool] || current.incomplete)) setRefreshedSource(sourceId);
        });
      }}>刷新候选</button>
      {confirmed && <button data-testid={`source.revoke.${tool}`} disabled={locked} onClick={() => setRevokePrompt(true)}>撤销来源…</button>}
    </div>
    {errorCode && <p className="error" role="alert" data-testid={`source.error.${tool}`} data-code={errorCode}>
      {sourceMessages[errorCode] ?? '来源操作未完成，请重试'}
    </p>}
    {revokePrompt && confirmed && <Modal title={`撤销 ${sourceNames[tool]} 来源`} onDismiss={() => setRevokePrompt(false)}>
      <h2>撤销 {sourceNames[tool]} 来源？</h2><p>撤销后立即停止读取并删除此来源的本机记录。要恢复采集，需要重新选择并确认目录。</p>
      <div className="dialog-actions"><span/><button data-testid={`source.revoke.cancel.${tool}`} onClick={() => setRevokePrompt(false)}>取消</button>
        <button className="primary" data-testid={`source.revoke.confirm.${tool}`} disabled={locked} onClick={async () => {
          const result = await run(() => window.tokenmeter.revokeSource({sourceId: confirmed.sourceId}));
          if (result && !result.sourceErrors?.[tool]) setRevokePrompt(false);
        }}>确认撤销</button></div>
    </Modal>}
  </section>;
}
function App() {
  const [state, setState] = useState<Snapshot | null>(null);
  const [server, setServer] = useState(''); const [username, setUsername] = useState(''); const [password, setPassword] = useState('');
  const [current, setCurrent] = useState(''); const [next, setNext] = useState(''); const [confirm, setConfirm] = useState('');
  const [passwordExpanded, setPasswordExpanded] = useState(false);
  const [configuration, setConfiguration] = useState(false); const [configServer, setConfigServer] = useState(''); const [configFeed, setConfigFeed] = useState('');
  const [configError, setConfigError] = useState(''); const [configStatus, setConfigStatus] = useState(''); const [localError, setLocalError] = useState('');
  const [resetID, setResetID] = useState<string | null>(null); const [temporary, setTemporary] = useState('');
  const apply = async (promise: Promise<Snapshot>) => { try { const value = await promise; setState(value); return value; } catch { setLocalError('operation_failed'); return null; } };
  useEffect(() => { const unsubscribe = window.tokenmeter.onState(setState); void apply(window.tokenmeter.snapshot()); return unsubscribe; }, []);
  useEffect(() => { if (state) setServer(state.server); }, [state?.server]);
  useEffect(() => {setPasswordExpanded(false); setCurrent(''); setNext(''); setConfirm('');}, [state?.account?.id]);
  useEffect(() => {
    const open = () => { if (state && !resetID) {setConfigServer(state.server); setConfigFeed(state.feed); setConfigError(''); setConfiguration(true);} };
    const shortcut = (event: KeyboardEvent) => { if (event.metaKey && event.key === ',' && !event.altKey && !event.ctrlKey && !event.shiftKey) {event.preventDefault(); open();} };
    const unsubscribe = window.tokenmeter.onOpenConfiguration(open);
    document.addEventListener('keydown', shortcut);
    return () => {unsubscribe(); document.removeEventListener('keydown', shortcut);};
  }, [state?.server, state?.feed, resetID]);
  if (!state) return <main className="loading">正在启动 TokenMeter…</main>;
  const s = state;
  const resetValidation = temporary.length < 12 ? '临时密码至少需要 12 位' : temporary.length > 128 ? '临时密码最多支持 128 位' : '';
  const accountName = (id: string | null) => id === null ? '系统' : s.users.find(user => user.id === id)?.username ?? (s.account?.id === id ? s.account.username : `账号 ${id.slice(-8)}`);
  const openConfiguration = () => { setConfigServer(s.server); setConfigFeed(s.feed); setConfigError(''); setConfiguration(true); };
  return <div className="shell">
    <aside><div className="brand"><img src={appIcon} alt="" className="app-icon"/><div>TokenMeter<small>团队模型用量</small></div></div><nav aria-label="应用导航"><span className="nav-section">工作区</span><span className="selected" aria-current="page"><svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="6" r="3"/><path d="M4 17v-2a6 6 0 0 1 12 0v2"/></svg>账号与设备</span><span className="muted">用量统计 · 开发中</span></nav><div className="sidebar-bottom"><span className="local-dot"/> 本地桌面客户端<p data-testid="app.build">v{s.version} · build {s.build}</p></div></aside>
    <main><header><div><h1>账号与设备</h1><p className="subtitle">管理访问权限、当前会话与服务连接。</p></div><button data-testid="configuration.open" title="服务配置（⌘,）" onClick={openConfiguration}>服务配置…</button></header>
      {configStatus && <p className="success" role="status" data-testid="configuration.status">{configStatus}</p>}
      {(s.error || localError) && <p role="alert" className="error" data-testid="auth.error">{describe(s.error || localError)}</p>}
      {s.pendingLogout && <section className="notice"><strong>退出尚未完成</strong><p>本机凭据已清除，服务端会话撤销尚未确认。恢复连接后请重试。</p><button data-testid="session.retry-logout" disabled={s.busy} onClick={() => apply(window.tokenmeter.retryLogout())}>重试退出</button></section>}
      {!s.account ? <section className="card login"><div className="section-title"><h2>登录团队</h2><p>使用管理员预置的账号。</p></div><form onSubmit={event => { event.preventDefault(); setLocalError(''); void apply(window.tokenmeter.login({server, username, password, automaticLogin: s.automaticLogin})); setPassword(''); }}>
        <label>服务地址<input data-testid="auth.server" value={server} onChange={e => setServer(e.target.value)} disabled={!s.canConfigureServer} placeholder="http://127.0.0.1:49176" spellCheck={false}/></label>
        <label>账号<input data-testid="auth.username" value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" spellCheck={false}/></label>
        <label>密码<input data-testid="auth.password" type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password"/></label>
        <label className="checkbox"><input data-testid="auth.automatic-login" type="checkbox" checked={s.automaticLogin} disabled={s.busy} onChange={e => apply(window.tokenmeter.setAutomaticLogin(e.target.checked))}/>在此设备自动登录</label>
        <button className="primary full" data-testid="auth.login" disabled={s.busy || s.pendingLogout || !username || !password} type="submit">{s.busy ? '正在连接…' : '登录'}</button>
      </form>{s.canRetryRestore && <div className="dialog-actions"><button data-testid="session.refresh" disabled={s.busy} onClick={() => apply(window.tokenmeter.refresh())}>重试连接</button></div>}</section> : <>
        <section className="card session"><div className="avatar">{s.account.username.slice(0, 1).toUpperCase()}</div><div className="session-info"><h2 data-testid="session.username">{s.account.username}</h2><span data-testid="session.role">{roleName(s.account.role)}</span><p data-testid={s.identityVerified ? 'session.verified' : 'session.unverified'}>{s.identityVerified ? `身份已验证 · ${new Date(s.lastIdentityCheck).toLocaleTimeString('zh-CN', {hour:'2-digit', minute:'2-digit'})}` : '身份尚未验证，请刷新连接'}</p></div><div className="actions"><button data-testid="session.refresh" disabled={s.busy} onClick={() => apply(window.tokenmeter.refresh())}>刷新身份</button><button data-testid="session.logout" disabled={s.busy} onClick={() => apply(window.tokenmeter.logout())}>退出登录</button></div></section>
        <section className="card password-card"><div className="section-title split"><div><h2>{s.account.must_change_password ? '首次登录，请更改密码' : '密码与安全'}</h2><p>{s.account.must_change_password ? '请设置至少 12 位的新密码，完成后即可使用团队功能。' : '修改密码会撤销旧会话。'}</p></div>{!s.account.must_change_password && <button data-testid="password.toggle" aria-expanded={passwordExpanded} aria-controls="password-form" onClick={() => setPasswordExpanded(!passwordExpanded)}>{passwordExpanded ? '收起' : '更改密码…'}</button>}</div>
          {(s.account.must_change_password || passwordExpanded) && <form id="password-form" onSubmit={event => {event.preventDefault(); setLocalError(''); if (next !== confirm) {setLocalError('password_confirmation_mismatch'); return;} void apply(window.tokenmeter.changePassword({currentPassword:current, newPassword:next})); setCurrent(''); setNext(''); setConfirm('');}}><div className="form-grid"><label>当前密码<input data-testid="password.current" type="password" value={current} onChange={e => setCurrent(e.target.value)}/></label><label>新密码<input data-testid="password.new" type="password" value={next} onChange={e => setNext(e.target.value)}/></label><label>确认新密码<input data-testid="password.confirm" type="password" value={confirm} onChange={e => setConfirm(e.target.value)}/></label></div><button data-testid="password.submit" disabled={s.busy || !current || next.length < 12 || !confirm} type="submit">更新密码</button></form>}
          {s.passwordStatus && <p className="success" role="status" data-testid="password.status">{s.passwordStatus}</p>}
        </section>
        {s.account.role === 'admin' && !s.account.must_change_password && <section className="card"><div className="section-title split"><div><h2>团队账号</h2><p>停用、重新启用或重置成员密码。</p></div><button data-testid="admin.accounts" disabled={s.busy} onClick={() => apply(window.tokenmeter.listUsers())}>加载账号</button></div>
          {s.adminStatus && <p className="success" role="status" data-testid="admin.status">{s.adminStatus}</p>}
          {s.users.length > 0 && <table><thead><tr><th>账号</th><th>角色</th><th>状态</th><th>操作</th></tr></thead><tbody>{s.users.map(user => <tr key={user.id}><td>{user.username}</td><td>{roleName(user.role)}</td><td data-testid={`admin.state.${user.username}`}>{user.is_active ? '已启用' : '已停用'}{user.must_change_password ? ' · 待改密' : ''}</td><td className="table-actions"><button data-testid={`admin.${user.is_active ? 'disable' : 'enable'}.${user.username}`} disabled={s.busy} onClick={() => apply(window.tokenmeter.manageUser({userId: user.id, action: user.is_active ? 'disable' : 'enable'}))}>{user.is_active ? '停用' : '启用'}</button><button data-testid={`admin.reset.${user.username}`} disabled={s.busy} onClick={() => { setResetID(user.id); setTemporary(''); }}>重置密码</button></td></tr>)}</tbody></table>}
          <div className="audit-head"><h3>操作记录</h3><button data-testid="admin.audit" disabled={s.busy} onClick={() => apply(window.tokenmeter.listAudit())}>加载审计</button></div><div className="audit-list">{s.audit.map(item => <div className="audit-row" key={item.id}><strong data-testid={`audit.action.${item.action}`}>{auditNames[item.action] ?? '账号操作'}</strong><span title={item.actor_id ?? 'system'} data-testid={`audit.actor.${item.action}.${item.actor_id ?? 'system'}`}>操作人：{accountName(item.actor_id)}</span><span title={item.target_id ?? 'none'} data-testid={`audit.target.${item.action}.${item.target_id ?? 'none'}`}>对象：{item.target_id ? accountName(item.target_id) : '无'}</span><time dateTime={item.occurred_at}>{new Date(item.occurred_at).toLocaleString('zh-CN', {month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit'})}</time></div>)}</div>
        </section>}
        {!s.account.must_change_password && s.identityVerified && s.sourcesReady &&
          <section className="card sources" aria-labelledby="sources-heading">
            <div className="section-title"><h2 id="sources-heading">本机日志来源</h2>
              <p>为每个工具选择已有日志目录。仅在你确认后，App 才会保存来源和采集意愿。</p></div>
            <div className="source-list">{(['codex', 'claude_code'] as const).map(tool =>
              <SourceCard key={tool} tool={tool} view={s.sources[tool]} ready={s.sourcesReady}
                busy={s.busy} sourceError={s.sourceErrors[tool]} onSnapshot={setState}/>)}</div>
          </section>}
      </>}
      <section className="card update"><div><h2>软件更新</h2><p role="status" data-testid="updates.status">{s.updates.errorCode ? describe(s.updates.errorCode) : s.updates.status}{s.updates.availableVersion ? ` · v${s.updates.availableVersion}` : ''}</p></div><div className="actions"><button data-testid="updates.check" disabled={!s.updates.canCheck} onClick={() => apply(window.tokenmeter.checkUpdates())}>检查更新</button>{s.updates.phase === 'available' && <button className="primary" data-testid="updates.install" onClick={() => apply(window.tokenmeter.installUpdate())}>安装并重启</button>}{['downloading', 'verifying'].includes(s.updates.phase) && <button data-testid="updates.cancel" onClick={() => apply(window.tokenmeter.cancelUpdate())}>取消</button>}</div></section>
      {configuration && <Modal title="服务配置" onDismiss={() => setConfiguration(false)}>
        <h2>服务配置</h2><p>连接此设备上的服务，或团队提供的 HTTPS 服务。</p>
        <form onSubmit={async event => { event.preventDefault(); const result = await apply(window.tokenmeter.saveConfiguration({server: configServer, feed: configFeed})); if (result?.error) setConfigError(result.error); else if (result) {setConfigStatus('配置已保存'); setConfiguration(false);} }}>
          <label>API 服务地址<input data-testid="configuration.api-url" value={configServer} onChange={e => setConfigServer(e.target.value)} disabled={!s.canConfigureServer} spellCheck={false}/></label>
          <label>软件更新清单<input data-testid="configuration.update-url" value={configFeed} onChange={e => setConfigFeed(e.target.value)} disabled={!s.updates.canConfigure} spellCheck={false}/></label>
          {configError && <p className="error" role="alert" data-testid="configuration.error">{describe(configError)}</p>}
          <div className="dialog-actions"><button type="button" data-testid="configuration.reset-defaults" disabled={!s.canConfigureServer || !s.updates.canConfigure} onClick={async () => { const result = await apply(window.tokenmeter.resetConfiguration()); if (result?.error) setConfigError(result.error); else if (result) {setConfigError(''); setConfigServer(result.server); setConfigFeed(result.feed); setConfigStatus('已恢复默认地址');} }}>恢复默认</button><span/><button type="button" data-testid="configuration.cancel" onClick={() => setConfiguration(false)}>取消</button><button type="submit" className="primary" data-testid="configuration.save">保存</button></div>
        </form>
      </Modal>}
      {resetID && <Modal title="重置成员密码" onDismiss={() => {setResetID(null); setTemporary('');}}>
        <h2>重置成员密码</h2><p>重置会撤销旧会话。成员下次登录时需要设置新密码。</p>
        <form onSubmit={event => {event.preventDefault(); if (resetValidation || s.busy) return; void apply(window.tokenmeter.manageUser({userId: resetID, action: 'reset-password', temporaryPassword: temporary})); setResetID(null); setTemporary('');}}>
          <label>临时密码<input type="password" data-testid="admin.temporary-password" value={temporary} onChange={e => setTemporary(e.target.value)} autoComplete="new-password"/></label>
          {resetValidation && <p className="error" role="alert" data-testid="admin.reset.validation">{resetValidation}</p>}
          <div className="dialog-actions"><span/><button type="button" onClick={() => {setResetID(null); setTemporary('');}}>取消</button><button type="submit" className="primary" data-testid="admin.reset.confirm" disabled={!!resetValidation || s.busy}>确认重置</button></div>
        </form>
      </Modal>}
    </main>
  </div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
