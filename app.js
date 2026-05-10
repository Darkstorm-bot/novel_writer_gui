/* ═══════════════════════════════════════════════════════════════════════════════
   NOVELFORGE v2.1 — Frontend Application (Real Backend Connected)
   ═══════════════════════════════════════════════════════════════════════════════

    This version connects to bridge.py via WebSocket for real backend integration.

   WebSocket Protocol:
   - Send: {type: "command", ...params}
   - Receive: {type: "event", ...data}

   Commands: generate_chapter, run_critic, auto_revise, save_content,
             get_chapters, add_chapter, get_characters, save_character,
             run_research, generate_outline, check_continuity,
             get_registry, update_settings, ping

   Events: connected, disconnected, task_started, task_progress,
           token_stream, critic_complete, generation_complete,
           revision_complete, content_saved, chapters_list,
           chapter_added, characters_list, character_saved,
           research_complete, outline_complete, continuity_complete,
           registry_data, settings_updated, model_status, error
   ═══════════════════════════════════════════════════════════════════════════════ */

class NovelForgeApp {
    constructor() {
        this.ws = null;
        this.reconnectTimer = null;
        this.isConnected = false;
        this.isRealBackend = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.isShuttingDown = false;

        this.currentPage = 'writer';
        this.currentChapter = 'chapter-1';
        this.chapters = { 'chapter-1': { title: 'Chapter 1', content: '', words: 0 } };
        this.characters = {};
        this.tasks = [];
        this.mistakes = [];
        this.sessionStart = Date.now();
        this.tokenCount = 0;
        this.revisionCount = 0;
        this.mistakeCount = 0;
        this.isGenerating = false;
        this.generationStream = '';
        this.themeStorageKey = 'novelforge.theme';
        this.appearanceStorageKey = 'novelforge.appearance';

        this.init();
    }

    init() {
        this.bindEvents();
        this.loadAppearanceSettings();
        window.addEventListener('beforeunload', () => this.shutdownWebSocket());
        this.connectWebSocket();
        this.startSessionTimer();
    }

    loadAppearanceSettings() {
        const savedAppearance = this.readAppearanceSettings();
        const themeSelect = document.getElementById('setting-theme');
        const fontSelect = document.getElementById('setting-font');
        const fontSizeInput = document.getElementById('setting-font-size');
        const lineHeightInput = document.getElementById('setting-line-height');

        if (themeSelect) {
            themeSelect.value = savedAppearance.theme;
        }
        if (fontSelect) {
            fontSelect.value = savedAppearance.font;
        }
        if (fontSizeInput) {
            fontSizeInput.value = savedAppearance.fontSize;
            document.getElementById('setting-font-size-val').textContent = savedAppearance.fontSize + 'px';
        }
        if (lineHeightInput) {
            lineHeightInput.value = savedAppearance.lineHeight;
            document.getElementById('setting-line-height-val').textContent = savedAppearance.lineHeight;
        }

        this.applyTheme(savedAppearance.theme, false);
        this.applyEditorAppearance(savedAppearance);
    }

    readAppearanceSettings() {
        const defaultSettings = {
            theme: 'dark',
            font: 'Merriweather',
            fontSize: '16',
            lineHeight: '1.8'
        };

        try {
            const raw = localStorage.getItem(this.appearanceStorageKey);
            if (!raw) {
                return defaultSettings;
            }

            return { ...defaultSettings, ...JSON.parse(raw) };
        } catch (error) {
            console.warn('[Settings] Failed to read appearance settings:', error);
            return defaultSettings;
        }
    }

    saveAppearanceSettings(nextSettings) {
        const current = this.readAppearanceSettings();
        const merged = { ...current, ...nextSettings };

        localStorage.setItem(this.appearanceStorageKey, JSON.stringify(merged));

        if (this.isConnected) {
            this.sendCommand('update_settings', { settings: merged });
        }

        return merged;
    }

    applyTheme(theme, persist = true) {
        const normalizedTheme = ['dark', 'light', 'sepia'].includes(theme) ? theme : 'dark';
        document.documentElement.dataset.theme = normalizedTheme;

        if (persist) {
            this.saveAppearanceSettings({ theme: normalizedTheme });
        }

        return normalizedTheme;
    }

    applyEditorAppearance(settings) {
        const editor = document.getElementById('editor');
        if (!editor) {
            return;
        }

        editor.style.fontFamily = settings.font;
        editor.style.fontSize = `${settings.fontSize}px`;
        editor.style.lineHeight = settings.lineHeight;
    }

    /* ═══════════════════════════════════════════════════════════════════════
       WEBSOCKET CONNECTION (REAL BACKEND)
       ═══════════════════════════════════════════════════════════════════════ */
    connectWebSocket() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
            this.ws.close();
        }

        this.updateConnectionStatus('connecting');
        this.isShuttingDown = false;

        try {
            const socket = new WebSocket('ws://localhost:8765');
            this.ws = socket;

            socket.onopen = () => {
                if (this.ws !== socket || this.isShuttingDown) return;
                console.log('[WS] Connected to NovelForge backend');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.updateConnectionStatus('connected');
                this.showToast('Connected to NovelForge backend', 'success');
            };

            socket.onmessage = (event) => {
                if (this.ws !== socket || this.isShuttingDown) return;
                try {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                } catch (e) {
                    console.error('[WS] Parse error:', e);
                }
            };

            socket.onclose = () => {
                if (this.ws !== socket) return;
                console.log('[WS] Connection closed');
                this.isConnected = false;
                this.isRealBackend = false;
                this.updateConnectionStatus('disconnected');

                if (!this.isShuttingDown && this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.reconnectAttempts++;
                    this.reconnectTimer = setTimeout(() => this.connectWebSocket(), 2000 * this.reconnectAttempts);
                } else {
                    this.showToast('Backend unavailable', 'warning');
                    this.updateConnectionStatus('disconnected');
                }
            };

            socket.onerror = (error) => {
                if (this.ws !== socket || this.isShuttingDown) return;
                console.error('[WS] Error:', error);
                this.updateConnectionStatus('disconnected');
            };

        } catch (e) {
            console.error('[WS] Failed to connect:', e);
            this.updateConnectionStatus('disconnected');
            this.showToast('Backend not found', 'warning');
        }
    }

    shutdownWebSocket() {
        this.isShuttingDown = true;

        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        if (this.ws) {
            this.ws.onopen = null;
            this.ws.onmessage = null;
            this.ws.onclose = null;
            this.ws.onerror = null;

            if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
                this.ws.close();
            }
        }
    }

    sendCommand(type, data = {}) {
        // Send a command to the backend via WebSocket.
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type, ...data }));
            return true;
        }
        return false;
    }

    handleWebSocketMessage(data) {
        // Handle incoming messages from the backend.
        const msgType = data.type;

        switch (msgType) {
            case 'connected':
                this.isRealBackend = data.mode === 'real';
                break;

            case 'connection_info':
                this.isRealBackend = data.mode === 'real';
                break;

            case 'model_status':
                this.updateModelStatus(data);
                break;

            case 'task_started':
                this.handleTaskStarted(data);
                break;

            case 'task_progress':
                this.handleTaskProgress(data);
                break;

            case 'token_stream':
                this.handleTokenStream(data);
                break;

            case 'critic_complete':
                this.handleCriticComplete(data);
                break;

            case 'generation_complete':
                this.handleGenerationComplete(data);
                break;

            case 'revision_complete':
                this.handleRevisionComplete(data);
                break;

                case 'content_saved':
                this.showToast(`Saved (${data.word_count} words)`, 'success');
                break;

            case 'chapters_list':
                this.handleChaptersList(data);
                break;

            case 'chapter_added':
                this.handleChapterAdded(data);
                break;

            case 'characters_list':
                this.handleCharactersList(data);
                break;

            case 'character_saved':
                this.handleCharacterSaved(data);
                break;

            case 'research_complete':
                this.handleResearchComplete(data);
                break;

            case 'outline_complete':
                this.handleOutlineComplete(data);
                break;

            case 'continuity_complete':
                this.handleContinuityComplete(data);
                break;

            case 'registry_data':
                this.handleRegistryData(data);
                break;

            case 'settings_updated':
                this.showToast('Settings saved', 'success');
                break;

            case 'error':
                this.showToast(data.message, 'error');
                console.error('[Backend]', data.message);
                break;

            default:
                console.log('[WS] Unknown message type:', msgType, data);
        }
    }

    updateModelStatus(data) {
        if (data.head) {
            document.getElementById('head-temp').textContent = data.head.temp;
            this.updateModelActivity('head', data.head.activity);
        }
        if (data.critic) {
            document.getElementById('critic-temp').textContent = data.critic.temp;
            this.updateModelActivity('critic', data.critic.activity);
        }
    }

    handleTaskStarted(data) {
        this.addTask(data.task, data.message || data.task, data.model);

        const modelName = data.model === 'head' ? 'Head (21B)' : 'Critic (14B)';
        document.getElementById('status-task').textContent = data.message || data.task;
        document.getElementById('status-model').textContent = modelName;

        if (data.model === 'head') {
            this.updateModelActivity('head', 30);
        } else if (data.model === 'critic') {
            this.updateModelActivity('critic', 80);
        }
    }

    handleTaskProgress(data) {
        this.updateTask(data.task, data.progress);

        if (data.tokens) {
            this.tokenCount = data.tokens;
            document.getElementById('status-tokens').textContent = `${data.tokens} tokens`;
            document.getElementById('stat-tokens').textContent = data.tokens;
        }

        // Update generation overlay
        if (this.isGenerating) {
            const progress = data.progress || 0;
            document.getElementById('gen-progress-bar').style.width = progress + '%';
            document.getElementById('gen-tokens').textContent = `${data.tokens || 0} tokens`;
            document.getElementById('gen-time').textContent = `${data.elapsed ? data.elapsed.toFixed(1) : '0'}s`;
        }
    }

    handleTokenStream(data) {
        if (!this.isGenerating) return;

        this.generationStream += data.token;

        // Update stream display
        const formatted = this.generationStream
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');
        document.getElementById('gen-stream').innerHTML = `<p>${formatted}</p>`;

        // Auto-scroll
        const streamEl = document.getElementById('gen-stream');
        streamEl.scrollTop = streamEl.scrollHeight;
    }

    handleCriticComplete(data) {
        this.updateTask('critic_review', 100);
        this.updateModelActivity('critic', 0);

        document.getElementById('status-task').textContent = 'Ready';
        document.getElementById('status-model').textContent = '—';

        this.showCritiqueOverlay(data.score, data.issues || []);

        // Update quality
        document.getElementById('status-quality').textContent = `Quality: ${data.score.toFixed(2)}`;
        document.getElementById('avg-quality').textContent = data.score.toFixed(2);
    }

    handleGenerationComplete(data) {
        this.isGenerating = false;

        // Hide overlay
        document.getElementById('generation-overlay').style.display = 'none';

        // Update editor
        const editor = document.getElementById('editor');
        const formatted = data.content
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');
        editor.innerHTML = `<p>${formatted}</p>`;

        // Update chapter
        this.chapters[this.currentChapter].content = editor.innerHTML;
        this.chapters[this.currentChapter].title = data.title;

        // Update stats
        this.updateWordCount();
        document.getElementById('chapter-count').textContent = Object.keys(this.chapters).length;
        document.getElementById('status-task').textContent = 'Ready';
        document.getElementById('status-model').textContent = '—';
        document.getElementById('status-quality').textContent = `Quality: ${data.quality.toFixed(2)}`;
        document.getElementById('avg-quality').textContent = data.quality.toFixed(2);

        this.updateModelActivity('head', 0);

        this.showToast(`Chapter "${data.title}" generated`, 'success');
    }

    handleRevisionComplete(data) {
        this.revisionCount++;
        document.getElementById('stat-revisions').textContent = this.revisionCount;
        document.getElementById('status-task').textContent = 'Ready';
        this.updateModelActivity('head', 0);
        this.showToast('Revision complete', 'success');
    }

    handleChaptersList(data) {
        // Update chapter tabs from backend
        const tabsContainer = document.getElementById('chapter-tabs');
        // Keep the add button, remove existing chapter tabs
        const addBtn = document.getElementById('btn-add-chapter');
        tabsContainer.innerHTML = '';

        data.chapters.forEach(ch => {
            const btn = document.createElement('button');
            btn.className = 'tab-btn' + (ch.id === this.currentChapter ? ' active' : '');
            btn.dataset.chapter = ch.id;
            btn.textContent = ch.title;
            tabsContainer.appendChild(btn);
        });

        tabsContainer.appendChild(addBtn);
    }

    handleChapterAdded(data) {
        const ch = data.chapter;
        this.chapters[ch.id] = { title: ch.title, content: '', words: 0 };

        const tabsContainer = document.getElementById('chapter-tabs');
        const addBtn = document.getElementById('btn-add-chapter');

        const btn = document.createElement('button');
        btn.className = 'tab-btn';
        btn.dataset.chapter = ch.id;
        btn.textContent = ch.title;
        tabsContainer.insertBefore(btn, addBtn);

        this.switchChapter(ch.id);
        this.showToast(`Chapter "${ch.title}" created`, 'success');
    }

    handleCharactersList(data) {
        const list = document.getElementById('char-list');
        list.innerHTML = '';

        const colors = [
            'linear-gradient(135deg, #667eea, #764ba2)',
            'linear-gradient(135deg, #f093fb, #f5576c)',
            'linear-gradient(135deg, #4facfe, #00f2fe)',
            'linear-gradient(135deg, #43e97b, #38f9d7)',
            'linear-gradient(135deg, #fa709a, #fee140)',
            'linear-gradient(135deg, #a8edea, #fed6e3)'
        ];

        data.characters.forEach((char, i) => {
            const item = document.createElement('div');
            item.className = 'char-item' + (i === 0 ? ' active' : '');
            item.dataset.char = char.id;
            item.innerHTML = `
                <div class="char-avatar" style="background: ${colors[i % colors.length]}">${char.name.charAt(0)}</div>
                <div class="char-brief">
                    <div class="char-name">${char.name}</div>
                    <div class="char-role">${char.role}</div>
                </div>
            `;
            list.appendChild(item);

            // Store in local state
            this.characters[char.id] = char;
        });
    }

    handleCharacterSaved(data) {
        const char = data.character;
        this.characters[char.id] = char;
        this.closeModal('character');
        this.showToast(`Character "${char.name}" saved`, 'success');

        // Refresh character list
        this.sendCommand('get_characters');
    }

    handleResearchComplete(data) {
        const container = document.getElementById('research-results');

        if (!data.results || data.results.length === 0) {
            container.innerHTML = '<div class="research-empty">No results found.</div>';
            return;
        }

        container.innerHTML = `
            <div class="research-result">
                <h4>🔍 Results for "${data.query}"</h4>
                ${data.results.map(r => `
                    <div class="research-source">
                        <div class="source-title">${r.title}</div>
                        ${r.url ? `<div class="source-url">${r.url}</div>` : ''}
                        <div class="source-excerpt">${r.excerpt || ''}</div>
                    </div>
                `).join('')}
            </div>
        `;

        this.showToast('Research complete', 'success');
    }

    handleOutlineComplete(data) {
        const tree = document.getElementById('outline-tree');

        if (!data.outline || data.outline.length === 0) {
            tree.innerHTML = '<div class="outline-empty-state"><div class="empty-icon">🗺️</div><p>No outline generated.</p></div>';
            return;
        }

        tree.innerHTML = data.outline.map(act => `
            <div class="outline-act">
                <div class="outline-act-header">${act.act}</div>
                ${(act.chapters || []).map(ch => `
                    <div class="outline-chapter">
                        <div class="outline-chapter-header">${ch.title}</div>
                        ${(ch.scenes || []).map(scene => `
                            <div class="outline-scene">${scene}</div>
                        `).join('')}
                    </div>
                `).join('')}
            </div>
        `).join('');

        document.getElementById('outline-content').innerHTML = tree.innerHTML;
        this.showToast('Outline generated', 'success');
    }

    handleContinuityComplete(data) {
        document.getElementById('continuity-timeline').innerHTML = (data.timeline || []).map(t => `
            <div class="timeline-item">
                <div class="timeline-marker" style="background:${t.status === 'consistent' ? 'var(--accent-success)' : 'var(--accent-warning)'}"></div>
                <div class="timeline-info">
                    <div class="timeline-label">${t.chapter} — ${t.time}</div>
                    <div class="timeline-status">${t.status === 'consistent' ? '✓' : '⚠'} ${t.status}</div>
                </div>
            </div>
        `).join('');

        document.getElementById('consistency-list').innerHTML = (data.characters || []).map(c => `
            <div class="consistency-item">
                <div class="consistency-char">${c.name}</div>
                <div class="consistency-checks">
                    ${Object.entries(c.checks || {}).map(([check, status]) => `
                        <span class="check-${status}">${status === 'pass' ? '✓' : status === 'warning' ? '⚠' : '✗'} ${check}</span>
                    `).join('')}
                </div>
            </div>
        `).join('');

        document.getElementById('plot-threads').innerHTML = (data.plot_threads || []).map(t => `
            <div class="plot-thread">
                <div class="thread-name">${t.name}</div>
                <div class="thread-status ${t.status}">${t.status === 'active' ? '●' : '○'} ${t.status}</div>
            </div>
        `).join('');

        this.showToast('Continuity check complete', 'success');
    }

    handleRegistryData(data) {
        this.mistakes = data.mistakes || [];

        // Update badge
        document.getElementById('registry-badge').textContent = this.mistakes.length;
        document.getElementById('stat-mistakes').textContent = this.mistakes.length;

        // Update stats
        if (data.stats) {
            document.getElementById('reg-total').textContent = data.stats.total || 0;
            document.getElementById('reg-critical').textContent = data.stats.critical || 0;
            document.getElementById('reg-major').textContent = data.stats.major || 0;
            document.getElementById('reg-fixed').textContent = data.stats.fixed || 0;
        }

        this.renderRegistry();
    }

    /* ═══════════════════════════════════════════════════════════════════════
       EVENT BINDING
       ═══════════════════════════════════════════════════════════════════════ */
    bindEvents() {
        // Hamburger
        document.getElementById('hamburger-btn').addEventListener('click', () => {
            document.getElementById('left-sidebar').classList.toggle('collapsed');
        });

        // Navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                this.switchPage(item.dataset.page);
            });
        });

        // Generate Chapter
        document.getElementById('btn-generate').addEventListener('click', () => {
            this.openModal('generate');
        });

        document.getElementById('btn-gen-confirm').addEventListener('click', () => {
            this.generateChapter();
        });

        // Research
        document.getElementById('btn-research').addEventListener('click', () => {
            this.switchPage('research');
        });

        // Chapter tabs
        document.getElementById('chapter-tabs').addEventListener('click', (e) => {
            if (e.target.classList.contains('tab-btn') && !e.target.classList.contains('add-tab')) {
                this.switchChapter(e.target.dataset.chapter);
            }
        });

        document.getElementById('btn-add-chapter').addEventListener('click', () => {
            this.addChapter();
        });

        // Editor toolbar
        document.querySelectorAll('.tool-btn[data-cmd]').forEach(btn => {
            btn.addEventListener('click', () => {
                this.execCommand(btn.dataset.cmd);
            });
        });

        document.getElementById('btn-critique').addEventListener('click', () => {
            this.runCritique();
        });

        document.getElementById('btn-revise').addEventListener('click', () => {
            this.autoRevise();
        });

        // Critic close
        document.getElementById('critic-close').addEventListener('click', () => {
            document.getElementById('critic-overlay').style.display = 'none';
        });

        // Outline panel
        document.getElementById('btn-outline-view').addEventListener('click', () => {
            const panel = document.getElementById('outline-panel');
            panel.style.display = panel.style.display === 'none' ? 'flex' : 'none';
        });

        document.getElementById('close-outline').addEventListener('click', () => {
            document.getElementById('outline-panel').style.display = 'none';
        });

        // Fullscreen
        document.getElementById('btn-fullscreen').addEventListener('click', () => {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen();
            } else {
                document.exitFullscreen();
            }
        });

        // Character selection
        document.getElementById('char-list').addEventListener('click', (e) => {
            const item = e.target.closest('.char-item');
            if (item) {
                this.selectCharacter(item.dataset.char);
            }
        });

        // Character detail tabs
        document.querySelectorAll('.detail-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const tabName = tab.dataset.tab;
                document.querySelectorAll('.detail-tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.detail-panel').forEach(p => p.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(`tab-${tabName}`).classList.add('active');
            });
        });

        // Add character
        document.getElementById('btn-add-character').addEventListener('click', () => {
            this.openModal('character');
        });

        document.getElementById('btn-add-char-right').addEventListener('click', () => {
            this.openModal('character');
        });

        document.getElementById('btn-add-char-card').addEventListener('click', () => {
            this.openModal('character');
        });

        document.getElementById('btn-char-save').addEventListener('click', () => {
            this.saveCharacter();
        });

        // Modal close
        document.querySelectorAll('.modal-close, .modal-overlay').forEach(el => {
            el.addEventListener('click', (e) => {
                const modalId = el.dataset.modal || el.closest('.modal').id.replace('modal-', '');
                this.closeModal(modalId);
            });
        });

        // Settings sliders
        document.getElementById('setting-head-temp').addEventListener('input', (e) => {
            document.getElementById('setting-head-temp-val').textContent = e.target.value;
            document.getElementById('head-temp').textContent = e.target.value;
        });

        document.getElementById('setting-head-rep').addEventListener('input', (e) => {
            document.getElementById('setting-head-rep-val').textContent = e.target.value;
        });

        document.getElementById('setting-critic-temp').addEventListener('input', (e) => {
            document.getElementById('setting-critic-temp-val').textContent = e.target.value;
            document.getElementById('critic-temp').textContent = e.target.value;
        });

        document.getElementById('setting-quality-threshold').addEventListener('input', (e) => {
            document.getElementById('setting-quality-val').textContent = parseFloat(e.target.value).toFixed(2);
        });

        document.getElementById('setting-font-size').addEventListener('input', (e) => {
            document.getElementById('setting-font-size-val').textContent = e.target.value + 'px';
            document.getElementById('editor').style.fontSize = e.target.value + 'px';
            this.saveAppearanceSettings({ fontSize: e.target.value });
        });

        document.getElementById('setting-line-height').addEventListener('input', (e) => {
            document.getElementById('setting-line-height-val').textContent = e.target.value;
            document.getElementById('editor').style.lineHeight = e.target.value;
            this.saveAppearanceSettings({ lineHeight: e.target.value });
        });

        document.getElementById('setting-font').addEventListener('change', (e) => {
            document.getElementById('editor').style.fontFamily = e.target.value;
            this.saveAppearanceSettings({ font: e.target.value });
        });

        document.getElementById('setting-theme').addEventListener('change', (e) => {
            this.applyTheme(e.target.value);
        });

        // Registry filters
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.filterRegistry(btn.dataset.filter);
            });
        });

        // Research
        document.getElementById('btn-research-go').addEventListener('click', () => {
            this.runResearch();
        });

        // Generate outline
        document.getElementById('btn-generate-outline').addEventListener('click', () => {
            this.generateOutline();
        });

        document.getElementById('btn-gen-outline-2').addEventListener('click', () => {
            this.generateOutline();
        });

        // Continuity check
        document.getElementById('btn-check-continuity').addEventListener('click', () => {
            this.runContinuityCheck();
        });

        // Editor input tracking
        document.getElementById('editor').addEventListener('input', () => {
            this.updateWordCount();
        });

        // Auto-save on blur
        document.getElementById('editor').addEventListener('blur', () => {
            this.saveContent();
        });
    }

    /* ═══════════════════════════════════════════════════════════════════════
       PAGE NAVIGATION
       ═══════════════════════════════════════════════════════════════════════ */
    switchPage(page) {
        this.currentPage = page;

        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.page === page);
        });

        document.querySelectorAll('.page').forEach(p => {
            p.classList.toggle('active', p.id === `page-${page}`);
        });

        // Fetch page-specific data
        if (page === 'characters') {
            this.sendCommand('get_characters');
        } else if (page === 'registry') {
            this.sendCommand('get_registry');
        }
    }

    /* ═══════════════════════════════════════════════════════════════════════
       CHAPTER MANAGEMENT
       ═══════════════════════════════════════════════════════════════════════ */
    switchChapter(chapterId) {
        const editor = document.getElementById('editor');
        this.chapters[this.currentChapter].content = editor.innerHTML;
        this.chapters[this.currentChapter].words = this.countWords(editor.innerText);

        this.currentChapter = chapterId;
        const chapter = this.chapters[chapterId];

        editor.innerHTML = chapter.content || '<p class="placeholder">Click "Generate Chapter" to start writing, or begin typing...</p>';

        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.chapter === chapterId);
        });

        this.updateWordCount();
    }

    addChapter() {
        const title = prompt('Chapter title:', `Chapter ${Object.keys(this.chapters).length + 1}`);
        if (!title) return;

        if (this.isConnected) {
            this.sendCommand('add_chapter', { title });
        } else {
            const num = Object.keys(this.chapters).length + 1;
            const id = `chapter-${num}`;
            this.chapters[id] = { title, content: '', words: 0 };

            const tabsContainer = document.getElementById('chapter-tabs');
            const addBtn = document.getElementById('btn-add-chapter');

            const btn = document.createElement('button');
            btn.className = 'tab-btn';
            btn.dataset.chapter = id;
            btn.textContent = title;
            tabsContainer.insertBefore(btn, addBtn);

            this.switchChapter(id);
            this.showToast(`Chapter "${title}" created`, 'success');
        }
    }

    saveContent() {
        const editor = document.getElementById('editor');
        const content = editor.innerText;

        if (this.isConnected) {
            this.sendCommand('save_content', {
                chapter_id: this.currentChapter,
                content
            });
        }
    }

    /* ═══════════════════════════════════════════════════════════════════════
       GENERATION
       ═══════════════════════════════════════════════════════════════════════ */
    async generateChapter() {
        const title = document.getElementById('gen-chapter-title').value || 'Untitled Chapter';
        const prompt = document.getElementById('gen-prompt').value;

        if (!prompt.trim()) {
            this.showToast('Please enter a scene description', 'warning');
            return;
        }

        this.closeModal('generate');
        this.isGenerating = true;
        this.generationStream = '';

        // Show generation overlay
        const overlay = document.getElementById('generation-overlay');
        overlay.style.display = 'flex';
        document.getElementById('gen-model').textContent = 'Head Model (21B)';
        document.getElementById('gen-task').textContent = `Planning: ${title}`;
        document.getElementById('gen-progress-bar').style.width = '5%';
        document.getElementById('gen-tokens').textContent = '0 tokens';
        document.getElementById('gen-time').textContent = '0s';
        document.getElementById('gen-stream').innerHTML = '';

        if (this.isConnected) {
            // REAL: Send to backend
            this.sendCommand('generate_chapter', {
                title,
                prompt,
                novel_name: document.getElementById('novel-title').textContent.replace(/\s+/g, '_').toLowerCase(),
                chapter_id: this.currentChapter
            });
            // Backend will stream events back via WebSocket
        } else {
            this.isGenerating = false;
            overlay.style.display = 'none';
            this.showToast('Connect to the backend to generate chapters', 'warning');
        }
    }

    /* ═══════════════════════════════════════════════════════════════════════
       CRITIC & REVISION
       ═══════════════════════════════════════════════════════════════════════ */
    runCritique() {
        const editor = document.getElementById('editor');
        const text = editor.innerText;

        if (!text.trim() || text.includes('placeholder')) {
            this.showToast('No content to review', 'warning');
            return;
        }

        if (this.isConnected) {
            this.sendCommand('run_critic', { content: text });
        } else {
            this.showToast('Connect to the backend to run critique', 'warning');
        }
    }

    autoRevise() {
        if (this.isConnected) {
            const editor = document.getElementById('editor');
            this.sendCommand('auto_revise', { content: editor.innerText });
        } else {
            this.showToast('Connect to the backend to auto-revise', 'warning');
        }
    }

    showCritiqueOverlay(score, issues) {
        const overlay = document.getElementById('critic-overlay');
        const scoreEl = document.getElementById('critic-score');
        const issuesEl = document.getElementById('critic-issues');

        scoreEl.textContent = score.toFixed(2);
        scoreEl.className = 'critic-score ' + (score >= 0.7 ? 'high' : score >= 0.5 ? 'medium' : 'low');

        issuesEl.innerHTML = issues.map(issue => `
            <div class="critic-issue ${issue.severity}">
                <div class="critic-issue-header ${issue.severity}">${issue.severity}${issue.category ? ` · ${issue.category}` : ''}</div>
                <div class="critic-issue-text">${issue.text}</div>
            </div>
        `).join('');

        overlay.style.display = 'flex';
    }

    /* ═══════════════════════════════════════════════════════════════════════
       MODEL ACTIVITY
       ═══════════════════════════════════════════════════════════════════════ */
    updateModelActivity(model, percent) {
        const card = document.getElementById(`model-${model}`);
        const fill = document.getElementById(`${model}-activity`);
        const label = document.getElementById(`${model}-activity-label`);
        const status = card.querySelector('.model-status');

        fill.style.width = percent + '%';

        if (percent > 0) {
            card.classList.add('active');
            status.dataset.status = 'active';
            label.textContent = percent > 80 ? 'Writing...' : percent > 40 ? 'Thinking...' : 'Loading...';
        } else {
            card.classList.remove('active');
            status.dataset.status = 'idle';
            label.textContent = 'Idle';
        }
    }

    /* ═══════════════════════════════════════════════════════════════════════
       TASK QUEUE
       ═══════════════════════════════════════════════════════════════════════ */
    addTask(type, name, model) {
        const id = 'task_' + Date.now();
        this.tasks.push({ id, type, name, model, progress: 0, status: 'running' });
        this.renderTaskQueue();
    }

    updateTask(type, progress) {
        const task = this.tasks.find(t => t.type === type && t.status === 'running');
        if (task) {
            task.progress = progress;
            if (progress >= 100) {
                task.status = 'completed';
            }
            this.renderTaskQueue();
        }
    }

    renderTaskQueue() {
        const container = document.getElementById('queue-list');

        if (this.tasks.length === 0) {
            container.innerHTML = '<div class="queue-empty">No active tasks</div>';
            return;
        }

        container.innerHTML = this.tasks.slice(-5).map(task => {
            const color = task.model === 'head' ? 'var(--model-head)' : 'var(--model-critic)';
            return `
                <div class="queue-item">
                    <div class="queue-status" style="background: ${color}"></div>
                    <div class="queue-name">${task.name}</div>
                    <div class="queue-pct">${task.progress}%</div>
                </div>
            `;
        }).join('');
    }

    /* ═══════════════════════════════════════════════════════════════════════
       CHARACTER MANAGEMENT
       ═══════════════════════════════════════════════════════════════════════ */
    selectCharacter(charId) {
        document.querySelectorAll('.char-item').forEach(item => {
            item.classList.toggle('active', item.dataset.char === charId);
        });

        const char = this.characters[charId];
        if (char) {
            document.getElementById('detail-avatar').textContent = char.name.charAt(0);
            document.getElementById('detail-name').textContent = char.name;
            document.getElementById('detail-role').textContent = `${char.role || 'Character'}${char.oneline ? ' · ' + char.oneline : ''}`;
            document.getElementById('detail-age').textContent = char.age || '—';
            document.getElementById('detail-origin').textContent = char.origin || '—';
            document.getElementById('detail-motivation').textContent = char.motivation || '—';
            document.getElementById('detail-fear').textContent = char.fear || '—';
            document.getElementById('detail-voice').textContent = char.voice || '—';
            document.getElementById('detail-appearance').textContent = char.appearance || '—';
        } else {
            document.getElementById('detail-avatar').textContent = '';
            document.getElementById('detail-name').textContent = '';
            document.getElementById('detail-role').textContent = '';
            document.getElementById('detail-age').textContent = '';
            document.getElementById('detail-origin').textContent = '';
            document.getElementById('detail-motivation').textContent = '';
            document.getElementById('detail-fear').textContent = '';
            document.getElementById('detail-voice').textContent = '';
            document.getElementById('detail-appearance').textContent = '';
        }
    }

    saveCharacter() {
        const name = document.getElementById('char-name').value;
        if (!name.trim()) {
            this.showToast('Character name is required', 'warning');
            return;
        }

        const char = {
            name,
            role: document.getElementById('char-role').value,
            oneline: document.getElementById('char-oneline').value,
            age: document.getElementById('char-age').value,
            origin: document.getElementById('char-origin').value,
            motivation: document.getElementById('char-motivation').value,
            fear: document.getElementById('char-fear').value,
            voice: document.getElementById('char-voice').value,
            appearance: ''
        };

        if (this.isConnected) {
            this.sendCommand('save_character', { character: char });
        } else {
            const charId = name.toLowerCase().replace(/\s+/g, '-');
            this.characters[charId] = char;

            const list = document.getElementById('char-list');
            const item = document.createElement('div');
            item.className = 'char-item';
            item.dataset.char = charId;

            const colors = [
                'linear-gradient(135deg, #667eea, #764ba2)',
                'linear-gradient(135deg, #f093fb, #f5576c)',
                'linear-gradient(135deg, #4facfe, #00f2fe)',
                'linear-gradient(135deg, #43e97b, #38f9d7)',
            ];
            const color = colors[Object.keys(this.characters).length % colors.length];

            item.innerHTML = `
                <div class="char-avatar" style="background: ${color}">${name.charAt(0)}</div>
                <div class="char-brief">
                    <div class="char-name">${name}</div>
                    <div class="char-role">${char.role}</div>
                </div>
            `;

            list.appendChild(item);
            this.closeModal('character');
            this.showToast(`Character "${name}" added`, 'success');
        }
    }

    /* ═══════════════════════════════════════════════════════════════════════
       RESEARCH
       ═══════════════════════════════════════════════════════════════════════ */
    runResearch() {
        const query = document.getElementById('research-query').value;
        if (!query.trim()) {
            this.showToast('Enter a research topic', 'warning');
            return;
        }

        if (this.isConnected) {
            this.sendCommand('run_research', { query });
        } else {
            this.showToast('Connect to the backend to run research', 'warning');
        }
    }

    /* ═══════════════════════════════════════════════════════════════════════
       OUTLINE
       ═══════════════════════════════════════════════════════════════════════ */
    generateOutline() {
        if (this.isConnected) {
            this.sendCommand('generate_outline', { premise: document.getElementById('novel-title').textContent });
        } else {
            this.showToast('Connect to the backend to generate an outline', 'warning');
        }
    }

    /* ═══════════════════════════════════════════════════════════════════════
       CONTINUITY
       ═══════════════════════════════════════════════════════════════════════ */
    runContinuityCheck() {
        if (this.isConnected) {
            this.sendCommand('check_continuity');
        } else {
            this.showToast('Connect to the backend to run continuity checks', 'warning');
        }
    }

    /* ═══════════════════════════════════════════════════════════════════════
       REGISTRY
       ═══════════════════════════════════════════════════════════════════════ */
    loadRegistry() {
        if (this.isConnected) {
            this.sendCommand('get_registry');
        } else {
            this.showToast('Connect to the backend to load the registry', 'warning');
        }
    }

    renderRegistry() {
        const list = document.getElementById('registry-list');

        if (this.mistakes.length === 0) {
            list.innerHTML = '<div class="registry-empty">No mistakes recorded yet.</div>';
            return;
        }

        list.innerHTML = this.mistakes.map(m => `
            <div class="registry-entry">
                <div class="registry-entry-header">
                    <span class="registry-entry-category ${m.severity}">${m.category}</span>
                    <span class="registry-entry-severity">${m.severity} · ${m.fixes || 0} fixes</span>
                </div>
                <div class="registry-entry-desc">${m.description}</div>
                <div class="registry-entry-meta">
                    <span>Success: ${(m.successRate * 100).toFixed(0)}%</span>
                    <span class="registry-entry-fix">
                        <div class="fix-bar"><div class="fix-fill" style="width:${m.successRate * 100}%"></div></div>
                    </span>
                </div>
            </div>
        `).join('');
    }

    filterRegistry(filter) {
        // In real implementation, filter by severity
        this.renderRegistry();
    }

    /* ═══════════════════════════════════════════════════════════════════════
       UTILITY
       ═══════════════════════════════════════════════════════════════════════ */
    openModal(id) {
        document.getElementById(`modal-${id}`).style.display = 'block';
    }

    closeModal(id) {
        document.getElementById(`modal-${id}`).style.display = 'none';
    }

    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icons = { success: '✓', error: '✗', warning: '⚠', info: 'ℹ' };
        toast.innerHTML = `
            <span class="toast-icon">${icons[type]}</span>
            <span class="toast-message">${message}</span>
            <button class="toast-close">×</button>
        `;

        toast.querySelector('.toast-close').addEventListener('click', () => {
            toast.remove();
        });

        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(20px)';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    updateWordCount() {
        const editor = document.getElementById('editor');
        const text = editor.innerText;
        const words = this.countWords(text);
        document.getElementById('word-count').textContent = words.toLocaleString();
    }

    countWords(text) {
        return text.trim().split(/\s+/).filter(w => w.length > 0).length;
    }

    execCommand(cmd) {
        document.execCommand(cmd, false, null);
        document.getElementById('editor').focus();
    }

    updateConnectionStatus(status) {
        const dot = document.getElementById('ws-status-dot');
        const text = document.getElementById('ws-status-text');

        dot.className = 'status-dot';
        if (status === 'connected') {
            dot.classList.add('connected');
            text.textContent = 'Connected';
        } else if (status === 'connecting') {
            dot.classList.add('connecting');
            text.textContent = 'Connecting...';
        } else {
            dot.classList.add('disconnected');
            text.textContent = 'Disconnected';
        }
    }

    startSessionTimer() {
        setInterval(() => {
            const elapsed = Math.floor((Date.now() - this.sessionStart) / 1000);
            const mins = Math.floor(elapsed / 60);
            const secs = elapsed % 60;
            document.getElementById('stat-time').textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
        }, 1000);
    }

}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new NovelForgeApp();
});
