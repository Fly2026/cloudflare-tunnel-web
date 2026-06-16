// CFWEB Web 管理平台前端

(function () {
    'use strict';

    // 全局状态
    const state = {
        currentPage: 'dashboard',
        config: null,
        logEventSource: null,
        setupEventSource: null,
        tunnelStatusTimer: null,
    };

    // API 基础 URL
    const API_BASE = '';

    // 工具函数
    async function apiGet(path) {
        const res = await fetch(API_BASE + path, {
            credentials: 'same-origin',
            headers: { 'Accept': 'application/json' },
        });
        const data = await res.json().catch(() => ({}));
        return { ok: res.ok, status: res.status, data };
    }

    async function apiPost(path, body = {}) {
        const res = await fetch(API_BASE + path, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            body: JSON.stringify(body),
        });
        const data = await res.json().catch(() => ({}));
        return { ok: res.ok, status: res.status, data };
    }

    function escapeHtml(str) {
        if (str == null) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function showToast(message, type = 'success') {
        const toast = document.getElementById('toast');
        toast.textContent = message;
        toast.className = 'toast ' + type;
        setTimeout(() => {
            toast.classList.add('hidden');
        }, 3000);
    }

    function showError(msg) {
        const el = document.getElementById('login-error');
        if (el) el.textContent = msg;
    }

    function confirmDialog(title, message, onConfirm) {
        const modal = document.getElementById('confirm-modal');
        const titleEl = document.getElementById('confirm-title');
        const msgEl = document.getElementById('confirm-message');
        const okBtn = document.getElementById('confirm-ok');
        const cancelBtn = document.getElementById('confirm-cancel');

        titleEl.textContent = title;
        msgEl.textContent = message;
        modal.classList.remove('hidden');

        const clean = () => {
            modal.classList.add('hidden');
            okBtn.onclick = null;
            cancelBtn.onclick = null;
        };

        okBtn.onclick = () => {
            clean();
            onConfirm();
        };
        cancelBtn.onclick = clean;
    }

    // 认证相关
    async function checkAuth() {
        const { ok, data } = await apiGet('/api/auth/status');
        if (ok && data.authenticated) {
            showMainApp();
            return true;
        }
        showLoginPage();
        return false;
    }

    async function login(username, password) {
        const { ok, data } = await apiPost('/api/auth/login', { username, password });
        if (ok && data.success) {
            showMainApp();
            return true;
        }
        showError(data.error || '登录失败');
        return false;
    }

    async function logout() {
        await apiPost('/api/auth/logout');
        showLoginPage();
    }

    function showLoginPage() {
        document.getElementById('login-page').classList.remove('hidden');
        document.getElementById('main-app').classList.add('hidden');
        stopTunnelStatusTimer();
    }

    function showMainApp() {
        document.getElementById('login-page').classList.add('hidden');
        document.getElementById('main-app').classList.remove('hidden');
        startTunnelStatusTimer();
        navigate(location.hash || '#/dashboard');
    }

    // 路由
    function navigate(hash) {
        const path = hash.replace('#', '') || '/dashboard';
        const page = path.split('/')[1] || 'dashboard';
        state.currentPage = page;

        // 更新导航
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.toggle('active', link.dataset.page === page);
        });

        // 渲染页面
        const content = document.getElementById('content');
        content.innerHTML = '';
        closeEventSources();

        switch (page) {
            case 'dashboard': renderDashboard(content); break;
            case 'config': renderConfig(content); break;
            case 'services': renderServices(content); break;
            case 'setup': renderSetup(content); break;
            case 'tunnel': renderTunnel(content); break;
            case 'logs': renderLogs(content); break;
            case 'package': renderPackage(content); break;
            default: renderDashboard(content);
        }
    }

    function closeEventSources() {
        if (state.logEventSource) {
            state.logEventSource.close();
            state.logEventSource = null;
        }
        if (state.setupEventSource) {
            state.setupEventSource.close();
            state.setupEventSource = null;
        }
    }

    // Tunnel 状态轮询
    function startTunnelStatusTimer() {
        updateTunnelStatus();
        state.tunnelStatusTimer = setInterval(updateTunnelStatus, 3000);
    }

    function stopTunnelStatusTimer() {
        if (state.tunnelStatusTimer) {
            clearInterval(state.tunnelStatusTimer);
            state.tunnelStatusTimer = null;
        }
    }

    async function updateTunnelStatus() {
        const { ok, data } = await apiGet('/api/tunnel/status');
        const badge = document.getElementById('tunnel-status');
        if (!badge) return;
        if (ok && data.running) {
            badge.textContent = 'Tunnel 运行中';
            badge.className = 'status-badge status-running';
        } else {
            badge.textContent = 'Tunnel 未运行';
            badge.className = 'status-badge status-stopped';
        }
    }

    // 仪表盘
    async function renderDashboard(container) {
        const [{ data: cfgData }, { data: statusData }] = await Promise.all([
            apiGet('/api/config'),
            apiGet('/api/tunnel/status'),
        ]);

        const cfg = cfgData.config || {};
        const services = cfg.services || [];

        const uptime = statusData.running ? formatDuration(statusData.uptime_seconds) : '-';

        container.innerHTML = `
            <h2>仪表盘</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Tunnel 状态</h3>
                    <div class="value" style="color: ${statusData.running ? '#10b981' : '#ef4444'}">${statusData.running ? '运行中' : '已停止'}</div>
                </div>
                <div class="stat-card">
                    <h3>已配置服务</h3>
                    <div class="value">${services.length}</div>
                </div>
                <div class="stat-card">
                    <h3>运行时长</h3>
                    <div class="value">${uptime}</div>
                </div>
                <div class="stat-card">
                    <h3>域名</h3>
                    <div class="value" style="font-size: 18px; word-break: break-all;">${escapeHtml(cfg.domain || '未配置')}</div>
                </div>
            </div>

            <div class="card">
                <h2>服务映射概览</h2>
                ${services.length === 0 ? '<p style="color: #666;">暂无服务映射，请前往「服务映射」页面添加。</p>' : `
                <table class="table">
                    <thead>
                        <tr>
                            <th>公网地址</th>
                            <th>目标服务</th>
                            <th>说明</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${services.map(s => `
                            <tr>
                                <td>https://${escapeHtml(s.folder)}.${escapeHtml(cfg.domain || 'example.com')}</td>
                                <td>http://${escapeHtml(s.host || 'localhost')}:${s.port}</td>
                                <td>${escapeHtml(s.description || '-')}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
                `}
            </div>
        `;
    }

    function formatDuration(seconds) {
        if (!seconds || seconds < 0) return '-';
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        return `${h}小时 ${m}分 ${s}秒`;
    }

    // 配置管理
    async function renderConfig(container) {
        const { data } = await apiGet('/api/config');
        const cfg = data.config || {};
        const web = cfg.web || { port: 50000, username: 'admin', password_hash: '' };
        const ali = cfg.aliyun || {};

        container.innerHTML = `
            <h2>配置管理</h2>
            <div class="card">
                <form id="config-form">
                    <h3>基础配置</h3>
                    <div class="form-row">
                        <div class="form-group">
                            <label>根域名</label>
                            <input type="text" id="cfg-domain" value="${escapeHtml(cfg.domain || '')}" placeholder="example.com" required>
                        </div>
                        <div class="form-group">
                            <label>Tunnel 名称</label>
                            <input type="text" id="cfg-tunnel-name" value="${escapeHtml(cfg.tunnel_name || 'cfweb-tunnel')}" required>
                        </div>
                    </div>

                    <h3>阿里云配置</h3>
                    <div class="form-row">
                        <div class="form-group">
                            <label>AccessKey ID</label>
                            <input type="text" id="cfg-ali-key" value="${escapeHtml(ali.access_key_id || '')}" required>
                        </div>
                        <div class="form-group">
                            <label>AccessKey Secret</label>
                            <input type="password" id="cfg-ali-secret" value="${escapeHtml(ali.access_key_secret || '')}" placeholder="留空保持原值">
                        </div>
                        <div class="form-group">
                            <label>Region</label>
                            <input type="text" id="cfg-ali-region" value="${escapeHtml(ali.region || 'cn-hangzhou')}" required>
                        </div>
                    </div>

                    <h3>Web 管理台配置</h3>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Web 端口</label>
                            <input type="number" id="cfg-web-port" value="${web.port || 50000}" min="1" max="65535" required>
                        </div>
                        <div class="form-group">
                            <label>管理用户名</label>
                            <input type="text" id="cfg-web-username" value="${escapeHtml(web.username || 'admin')}" required>
                        </div>
                        <div class="form-group">
                            <label>管理密码（留空保持原值）</label>
                            <input type="password" id="cfg-web-password" placeholder="留空保持原值">
                        </div>
                    </div>

                    <button type="submit" class="btn btn-primary">保存配置</button>
                </form>
            </div>
        `;

        document.getElementById('config-form').onsubmit = async (e) => {
            e.preventDefault();
            const newConfig = {
                domain: document.getElementById('cfg-domain').value.trim(),
                tunnel_name: document.getElementById('cfg-tunnel-name').value.trim(),
                aliyun: {
                    access_key_id: document.getElementById('cfg-ali-key').value.trim(),
                    access_key_secret: document.getElementById('cfg-ali-secret').value,
                    region: document.getElementById('cfg-ali-region').value.trim(),
                },
                services: cfg.services || [],
                web: {
                    port: parseInt(document.getElementById('cfg-web-port').value),
                    username: document.getElementById('cfg-web-username').value.trim(),
                },
            };

            const password = document.getElementById('cfg-web-password').value;
            if (password) {
                // 前端无法计算 sha256，直接传明文，后端处理
                newConfig.web.password = password;
            }

            const { ok, data } = await apiPost('/api/config', { config: newConfig });
            if (ok && data.success) {
                showToast('配置保存成功');
                // 如果修改了端口，提示需要重启
                if (newConfig.web.port !== (web.port || 50000)) {
                    showToast('Web 端口已修改，请重启 Web 服务生效', 'error');
                }
            } else {
                showToast(data.error || '保存失败', 'error');
            }
        };
    }

    // 服务映射
    async function renderServices(container) {
        const { data } = await apiGet('/api/config/services');
        const services = data.services || [];
        const { data: cfgData } = await apiGet('/api/config');
        const domain = (cfgData.config || {}).domain || 'example.com';

        function renderServiceRows() {
            const rowsHtml = services.map((s, idx) => `
                <div class="service-row" data-index="${idx}">
                    <div class="form-group">
                        <label>Folder</label>
                        <input type="text" class="svc-folder" value="${escapeHtml(s.folder || '')}" placeholder="blog" required>
                    </div>
                    <div class="form-group">
                        <label>Host</label>
                        <input type="text" class="svc-host" value="${escapeHtml(s.host || 'localhost')}" required>
                    </div>
                    <div class="form-group">
                        <label>Port</label>
                        <input type="number" class="svc-port" value="${s.port || ''}" min="1" max="65535" required>
                    </div>
                    <div class="form-group">
                        <label>说明</label>
                        <input type="text" class="svc-desc" value="${escapeHtml(s.description || '')}">
                    </div>
                    <button type="button" class="btn btn-danger btn-sm btn-remove">删除</button>
                </div>
            `).join('');

            const rowsContainer = document.getElementById('service-rows');
            if (rowsContainer) rowsContainer.innerHTML = rowsHtml;
            bindRemoveButtons();
            updatePreview(domain);
        }

        function bindRemoveButtons() {
            document.querySelectorAll('.btn-remove').forEach(btn => {
                btn.onclick = () => {
                    const row = btn.closest('.service-row');
                    const idx = parseInt(row.dataset.index);
                    services.splice(idx, 1);
                    renderServiceRows();
                };
            });
        }

        function updatePreview(domain) {
            const preview = document.getElementById('services-preview');
            if (!preview) return;
            preview.innerHTML = services.map(s => `
                <div>https://${escapeHtml(s.folder)}.${escapeHtml(domain)} → http://${escapeHtml(s.host || 'localhost')}:${s.port}</div>
            `).join('');
        }

        container.innerHTML = `
            <h2>服务映射</h2>
            <div class="card">
                <p style="margin-bottom: 16px; color: #666;">配置 folder → host:port 的映射关系，每个 folder 会生成一个子域名。</p>
                <div id="service-rows"></div>
                <button type="button" id="btn-add-service" class="btn btn-success">+ 添加服务</button>
                <button type="button" id="btn-save-services" class="btn btn-primary" style="margin-left: 12px;">保存服务映射</button>
            </div>

            <div class="card">
                <h3>映射预览</h3>
                <div id="services-preview" style="font-family: monospace; color: #555;"></div>
            </div>
        `;

        renderServiceRows();

        document.getElementById('btn-add-service').onclick = () => {
            services.push({ folder: '', host: 'localhost', port: '', description: '' });
            renderServiceRows();
        };

        document.getElementById('btn-save-services').onclick = async () => {
            const rows = document.querySelectorAll('.service-row');
            const newServices = [];
            let valid = true;

            rows.forEach(row => {
                const folder = row.querySelector('.svc-folder').value.trim();
                const host = row.querySelector('.svc-host').value.trim() || 'localhost';
                const port = parseInt(row.querySelector('.svc-port').value);
                const description = row.querySelector('.svc-desc').value.trim();

                if (!folder || !/^[a-zA-Z0-9-]+$/.test(folder)) {
                    showToast('Folder 只能包含英文、数字、连字符', 'error');
                    valid = false;
                    return;
                }
                if (!port || port < 1 || port > 65535) {
                    showToast('Port 必须是 1-65535 的整数', 'error');
                    valid = false;
                    return;
                }
                newServices.push({ folder, host, port, description });
            });

            if (!valid) return;

            const { ok, data } = await apiPost('/api/config/services', { services: newServices });
            if (ok && data.success) {
                showToast('服务映射保存成功');
            } else {
                showToast(data.error || '保存失败', 'error');
            }
        };
    }

    // 安装部署
    async function renderSetup(container) {
        container.innerHTML = `
            <h2>安装部署</h2>
            <div class="card">
                <p style="margin-bottom: 16px; color: #666;">
                    一键执行完整安装流程：下载 cloudflared、登录 Cloudflare、创建 Tunnel、生成配置、同步阿里云 DNS。
                </p>
                <div class="action-group">
                    <button id="btn-start-setup" class="btn btn-primary">开始安装</button>
                </div>

                <div id="setup-login-url" class="card" style="margin: 16px 0; display: none; background: #fef3c7; border-left: 4px solid #f59e0b;">
                    <h3>🌐 需要浏览器授权</h3>
                    <p>请在浏览器中打开以下 URL 完成 Cloudflare 授权：</p>
                    <a id="login-url-link" href="#" target="_blank" rel="noopener noreferrer" style="display: inline-block; word-break: break-all; font-family: monospace; margin: 12px 0; padding: 10px 14px; background: #fff; border-radius: 6px; border: 1px solid #f59e0b; color: #b45309; text-decoration: none;">
                        点击跳转授权页面 →
                    </a>
                    <div id="login-url-text" style="word-break: break-all; font-family: monospace; margin-bottom: 12px; color: #666; font-size: 12px;"></div>
                    <button id="btn-login-done" class="btn btn-success">已完成授权，继续</button>
                </div>

                <div id="setup-output" class="output-area hidden"></div>
            </div>
        `;

        const outputEl = document.getElementById('setup-output');

        document.getElementById('btn-start-setup').onclick = async () => {
            outputEl.classList.remove('hidden');
            outputEl.textContent = '正在启动安装流程...\n';

            const { ok, data } = await apiPost('/api/setup/install');
            if (!ok || !data.success) {
                outputEl.textContent += (data.error || '启动失败') + '\n';
                return;
            }

            // 连接 SSE
            connectSetupStream(outputEl);
        };

        document.getElementById('btn-login-done').onclick = () => {
            document.getElementById('setup-login-url').style.display = 'none';
            showToast('继续安装流程');
        };
    }

    function connectSetupStream(outputEl) {
        if (state.setupEventSource) {
            state.setupEventSource.close();
        }

        const es = new EventSource('/api/setup/progress');
        state.setupEventSource = es;

        es.onmessage = (event) => {
            const line = event.data;
            outputEl.textContent += line + '\n';
            outputEl.scrollTop = outputEl.scrollHeight;

            // 检测登录 URL
            const match = line.match(/https:\/\/\S+/);
            if (match && (line.toLowerCase().includes('login') || line.toLowerCase().includes('授权') || line.toLowerCase().includes('url') || line.toLowerCase().includes('browser'))) {
                const urlBox = document.getElementById('setup-login-url');
                const linkEl = document.getElementById('login-url-link');
                const textEl = document.getElementById('login-url-text');
                if (urlBox) {
                    urlBox.style.display = 'block';
                    linkEl.href = match[0];
                    linkEl.textContent = '点击跳转授权页面 → ' + match[0];
                    textEl.textContent = match[0];
                }
            }

            if (line.includes('[SETUP_EXIT:')) {
                es.close();
                state.setupEventSource = null;
            }
        };

        es.onerror = () => {
            outputEl.textContent += '[日志连接断开]\n';
            es.close();
            state.setupEventSource = null;
        };
    }

    // Tunnel 管理
    async function renderTunnel(container) {
        const { data } = await apiGet('/api/tunnel/status');

        container.innerHTML = `
            <h2>Tunnel 管理</h2>
            <div class="card">
                <h3>当前状态</h3>
                <p>状态：<span id="tunnel-detail-status" style="font-weight: 600; color: ${data.running ? '#10b981' : '#ef4444'}">${data.running ? '运行中' : '已停止'}</span></p>
                ${data.pid ? `<p>PID：${data.pid}</p>` : ''}
                ${data.running ? `<p>运行时长：${formatDuration(data.uptime_seconds)}</p>` : ''}

                <div class="action-group" style="margin-top: 20px;">
                    <button id="btn-tunnel-start" class="btn btn-success">启动</button>
                    <button id="btn-tunnel-stop" class="btn btn-danger">停止</button>
                    <button id="btn-tunnel-restart" class="btn btn-warning">重启</button>
                </div>
            </div>
        `;

        document.getElementById('btn-tunnel-start').onclick = async () => {
            const { ok, data: res } = await apiPost('/api/tunnel/start');
            showToast(res.message || (ok ? '启动成功' : '启动失败'), ok ? 'success' : 'error');
            updateTunnelStatus();
        };

        document.getElementById('btn-tunnel-stop').onclick = () => {
            confirmDialog('确认停止', '确定要停止 Cloudflare Tunnel 吗？', async () => {
                const { ok, data: res } = await apiPost('/api/tunnel/stop');
                showToast(res.message || (ok ? '停止成功' : '停止失败'), ok ? 'success' : 'error');
                updateTunnelStatus();
            });
        };

        document.getElementById('btn-tunnel-restart').onclick = () => {
            confirmDialog('确认重启', '确定要重启 Cloudflare Tunnel 吗？', async () => {
                const { ok, data: res } = await apiPost('/api/tunnel/restart');
                showToast(res.message || (ok ? '重启成功' : '重启失败'), ok ? 'success' : 'error');
                updateTunnelStatus();
            });
        };
    }

    // 日志查看
    async function renderLogs(container) {
        container.innerHTML = `
            <h2>日志查看</h2>
            <div class="card">
                <div class="action-group">
                    <button id="btn-log-tunnel" class="btn btn-sm btn-primary">Tunnel 日志</button>
                    <button id="btn-log-setup" class="btn btn-sm">安装日志</button>
                    <button id="btn-log-web" class="btn btn-sm">Web 日志</button>
                    <button id="btn-log-pause" class="btn btn-sm">暂停</button>
                </div>
                <div id="log-container" class="log-container">正在连接日志流...</div>
            </div>
        `;

        let currentType = 'tunnel';
        let paused = false;
        const logContainer = document.getElementById('log-container');

        function setActiveType(type) {
            currentType = type;
            ['tunnel', 'setup', 'web'].forEach(t => {
                const btn = document.getElementById('btn-log-' + t);
                btn.classList.toggle('btn-primary', t === type);
            });
            connectLogStream(type);
        }

        function connectLogStream(type) {
            if (state.logEventSource) {
                state.logEventSource.close();
            }

            logContainer.textContent = '';
            const es = new EventSource('/api/logs/stream?type=' + type);
            state.logEventSource = es;

            es.onmessage = (event) => {
                if (paused) return;
                const line = document.createElement('div');
                line.className = 'log-line';
                line.textContent = event.data;
                logContainer.appendChild(line);
                logContainer.scrollTop = logContainer.scrollHeight;
            };

            es.onerror = () => {
                logContainer.textContent += '[日志连接断开]\n';
                es.close();
                state.logEventSource = null;
            };
        }

        document.getElementById('btn-log-tunnel').onclick = () => setActiveType('tunnel');
        document.getElementById('btn-log-setup').onclick = () => setActiveType('setup');
        document.getElementById('btn-log-web').onclick = () => setActiveType('web');
        document.getElementById('btn-log-pause').onclick = () => {
            paused = !paused;
            document.getElementById('btn-log-pause').textContent = paused ? '继续' : '暂停';
        };

        setActiveType('tunnel');
    }

    // 打包分发
    async function renderPackage(container) {
        container.innerHTML = `
            <h2>打包分发</h2>
            <div class="card">
                <p style="margin-bottom: 16px; color: #666;">一键打包当前项目，生成可分发的 tar.gz 文件。</p>
                <button id="btn-create-package" class="btn btn-primary">创建分发包</button>
                <div id="package-result" style="margin-top: 16px;"></div>
                <div id="package-output" class="output-area hidden"></div>
            </div>
        `;

        document.getElementById('btn-create-package').onclick = async () => {
            const resultEl = document.getElementById('package-result');
            const outputEl = document.getElementById('package-output');
            resultEl.innerHTML = '正在打包...';
            outputEl.classList.add('hidden');

            const { ok, data } = await apiPost('/api/package/create');
            if (ok && data.success) {
                resultEl.innerHTML = `
                    <p style="color: #10b981; font-weight: 500;">打包成功！</p>
                    ${data.package_path ? `<p>文件路径：<code>${escapeHtml(data.package_path)}</code></p>
                    <p>分发命令：</p>
                    <pre style="background: #f3f4f6; padding: 12px; border-radius: 6px; overflow-x: auto;">scp ${escapeHtml(data.package_path)} user@remote-host:/tmp/
ssh user@remote-host "cd /opt && tar -xzf /tmp/$(basename ${escapeHtml(data.package_path)}) && cd CFWEB && cp config.json.example config.json && vim config.json && ./install.sh"</pre>
                    ` : ''}
                `;
            } else {
                resultEl.innerHTML = `<p style="color: #ef4444;">打包失败：${escapeHtml(data.error || '未知错误')}</p>`;
            }

            if (data.output) {
                outputEl.textContent = data.output;
                outputEl.classList.remove('hidden');
            }
        };
    }

    // 初始化
    function init() {
        // 登录表单
        document.getElementById('login-form').onsubmit = async (e) => {
            e.preventDefault();
            const username = document.getElementById('login-username').value;
            const password = document.getElementById('login-password').value;
            await login(username, password);
        };

        // 退出按钮
        document.getElementById('logout-btn').onclick = logout;

        // 路由监听
        window.addEventListener('hashchange', () => navigate(location.hash));

        // 初始检查认证
        checkAuth();
    }

    document.addEventListener('DOMContentLoaded', init);
})();
