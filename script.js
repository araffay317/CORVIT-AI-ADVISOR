/**
 * Corvit AI Advisor — Client Frontend Application
 * Handles chat messaging, streaming RAG answers, source citation rendering,
 * course recommendation wizard, and official campus modals.
 * Zero secrets / API keys in client-side code.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Determine API Base URL dynamically (supports local dev and production Netlify deployment)
    function getApiBaseUrl() {
        // 1. Global config if set via deployment window object
        if (typeof window.CORVIT_BACKEND_URL === 'string' && window.CORVIT_BACKEND_URL.trim()) {
            return window.CORVIT_BACKEND_URL.trim().replace(/\/$/, '');
        }
        // 2. User-configured backend URL stored in localStorage
        const savedUrl = localStorage.getItem('CORVIT_BACKEND_URL');
        if (savedUrl && savedUrl.trim()) {
            return savedUrl.trim().replace(/\/$/, '');
        }
        // 3. If running on same port as FastAPI server
        if (window.location.origin && window.location.origin.includes(':8000')) {
            return window.location.origin;
        }
        // 4. Default local development backend
        return 'http://127.0.0.1:8000';
    }

    const API_BASE = getApiBaseUrl();

    // State
    const chatHistory = [];
    let isSubmitting = false;
    const selectedInterests = new Set();

    // DOM Elements - Navigation
    const tabChatBtn = document.getElementById('tab-chat-btn');
    const tabRecommendBtn = document.getElementById('tab-recommend-btn');
    const tabContactsBtn = document.getElementById('tab-contacts-btn');
    const tabApiBtn = document.getElementById('tab-api-btn');
    const chatSection = document.getElementById('chat-section');
    const recommendSection = document.getElementById('recommend-section');
    const contactsModal = document.getElementById('contacts-modal');
    const closeContactsBtn = document.getElementById('close-contacts-btn');
    const apiModal = document.getElementById('api-modal');
    const closeApiModalBtn = document.getElementById('close-api-modal-btn');
    const customApiInput = document.getElementById('custom-api-input');
    const currentApiDisplay = document.getElementById('current-api-display');
    const healthStatusBadge = document.getElementById('health-status-badge');
    const testApiBtn = document.getElementById('test-api-btn');
    const resetApiBtn = document.getElementById('reset-api-btn');
    const saveApiBtn = document.getElementById('save-api-btn');

    // DOM Elements - Chat
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const chatMessages = document.getElementById('chat-messages');
    const typingIndicator = document.getElementById('typing-indicator');
    const typingStatusText = document.getElementById('typing-status-text');
    const clearChatBtn = document.getElementById('clear-chat-btn');
    const activeModelBadge = document.getElementById('active-model-badge');
    const chatErrorBanner = document.getElementById('chat-error-banner');
    const chatErrorText = document.getElementById('chat-error-text');
    const dismissErrorBtn = document.getElementById('dismiss-error-btn');
    const allowWebResearchCheck = document.getElementById('allow-web-research-check');
    const suggestionChips = document.querySelectorAll('.chip-btn');

    // DOM Elements - Recommendation Form
    const recForm = document.getElementById('recommendation-form');
    const recBackground = document.getElementById('rec-background');
    const recGoal = document.getElementById('rec-goal');
    const interestPills = document.querySelectorAll('.interest-pill');
    const levelCards = document.querySelectorAll('.level-radio-card');
    const recLoading = document.getElementById('rec-loading');
    const recPlaceholder = document.getElementById('rec-placeholder');
    const recResults = document.getElementById('rec-results');
    const recCardsContainer = document.getElementById('rec-cards-container');
    const recStudentSummary = document.getElementById('rec-student-summary');

    // ============================================================
    // 1. NAVIGATION & TAB SWITCHING
    // ============================================================
    function switchTab(target) {
        if (target === 'chat') {
            tabChatBtn.classList.add('active-tab', 'text-slate-100');
            tabChatBtn.classList.remove('text-slate-400');
            tabRecommendBtn.classList.remove('active-tab', 'text-slate-100');
            tabRecommendBtn.classList.add('text-slate-400');
            chatSection.classList.remove('hidden');
            recommendSection.classList.add('hidden');
            chatInput.focus();
        } else if (target === 'recommend') {
            tabRecommendBtn.classList.add('active-tab', 'text-slate-100');
            tabRecommendBtn.classList.remove('text-slate-400');
            tabChatBtn.classList.remove('active-tab', 'text-slate-100');
            tabChatBtn.classList.add('text-slate-400');
            chatSection.classList.add('hidden');
            recommendSection.classList.remove('hidden');
        }
    }

    tabChatBtn.addEventListener('click', () => switchTab('chat'));
    tabRecommendBtn.addEventListener('click', () => switchTab('recommend'));

    tabContactsBtn.addEventListener('click', () => {
        contactsModal.classList.remove('hidden');
    });

    closeContactsBtn.addEventListener('click', () => {
        contactsModal.classList.add('hidden');
    });

    contactsModal.addEventListener('click', (e) => {
        if (e.target === contactsModal) {
            contactsModal.classList.add('hidden');
        }
    });

    // API Server Modal Handlers
    if (tabApiBtn && apiModal) {
        tabApiBtn.addEventListener('click', () => {
            if (customApiInput) customApiInput.value = API_BASE;
            if (currentApiDisplay) currentApiDisplay.textContent = API_BASE;
            apiModal.classList.remove('hidden');
        });

        if (closeApiModalBtn) {
            closeApiModalBtn.addEventListener('click', () => {
                apiModal.classList.add('hidden');
            });
        }

        apiModal.addEventListener('click', (e) => {
            if (e.target === apiModal) {
                apiModal.classList.add('hidden');
            }
        });

        if (testApiBtn) {
            testApiBtn.addEventListener('click', async () => {
                const targetUrl = (customApiInput?.value.trim() || API_BASE).replace(/\/$/, '');
                if (healthStatusBadge) {
                    healthStatusBadge.textContent = 'Testing...';
                    healthStatusBadge.className = 'px-2 py-0.5 rounded text-[10px] bg-amber-500/10 text-amber-300 border border-amber-500/20';
                }
                try {
                    const res = await fetch(`${targetUrl}/health`, { signal: AbortSignal.timeout(5000) });
                    if (res.ok) {
                        const hData = await res.json();
                        if (healthStatusBadge) {
                            healthStatusBadge.textContent = `Online (${hData.status})`;
                            healthStatusBadge.className = 'px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-300 border border-emerald-500/20';
                        }
                    } else {
                        throw new Error(`HTTP ${res.status}`);
                    }
                } catch (err) {
                    if (healthStatusBadge) {
                        healthStatusBadge.textContent = 'Unreachable';
                        healthStatusBadge.className = 'px-2 py-0.5 rounded text-[10px] bg-rose-500/10 text-rose-300 border border-rose-500/20';
                    }
                }
            });
        }

        if (saveApiBtn) {
            saveApiBtn.addEventListener('click', () => {
                const newUrl = (customApiInput?.value.trim() || '').replace(/\/$/, '');
                if (!newUrl) {
                    alert('Please enter a valid backend URL.');
                    return;
                }
                localStorage.setItem('CORVIT_BACKEND_URL', newUrl);
                alert(`Backend URL updated to: ${newUrl}\nThe page will now reload to apply changes.`);
                window.location.reload();
            });
        }

        if (resetApiBtn) {
            resetApiBtn.addEventListener('click', () => {
                localStorage.removeItem('CORVIT_BACKEND_URL');
                alert('Backend URL reset to local default (http://127.0.0.1:8000).\nThe page will now reload.');
                window.location.reload();
            });
        }
    }

    // Expose convenient global helper for setting backend URL
    window.setCorvitBackendUrl = function(url) {
        if (url) {
            localStorage.setItem('CORVIT_BACKEND_URL', url.trim().replace(/\/$/, ''));
            window.location.reload();
        }
    };

    // ============================================================
    // 2. CHAT FUNCTIONALITY
    // ============================================================
    // Auto-grow textarea
    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 128) + 'px';
    });

    // Enter key submits (Shift+Enter adds newline)
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });

    // Suggestion chips handler
    suggestionChips.forEach((chip) => {
        chip.addEventListener('click', () => {
            chatInput.value = chip.textContent.trim();
            chatInput.dispatchEvent(new Event('input'));
            chatInput.focus();
            chatForm.dispatchEvent(new Event('submit'));
        });
    });

    // Clear chat button
    clearChatBtn.addEventListener('click', () => {
        if (chatHistory.length === 0 && chatMessages.children.length <= 1) return;
        chatHistory.length = 0;
        // Keep welcome message, remove others
        while (chatMessages.children.length > 1) {
            chatMessages.removeChild(chatMessages.lastChild);
        }
        hideError();
    });

    dismissErrorBtn.addEventListener('click', hideError);

    function showError(msg) {
        chatErrorText.textContent = msg;
        chatErrorBanner.classList.remove('hidden');
    }

    function hideError() {
        chatErrorBanner.classList.add('hidden');
    }

    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function formatMarkdown(text) {
        if (!text) return '';
        let escaped = escapeHtml(text);
        // Simple markdown bold formatting: **bold**
        escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        // Simple markdown links: [label](url)
        escaped = escaped.replace(/\[(.*?)\]\((https?:\/\/[^\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-blue-400 hover:underline font-medium">$1</a>');
        // Convert bullet lines
        const lines = escaped.split('\n');
        let inList = false;
        const processed = [];

        for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed.startsWith('• ') || trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
                if (!inList) {
                    processed.push('<ul class="list-disc ml-5 space-y-1 my-2">');
                    inList = true;
                }
                processed.push(`<li>${trimmed.substring(2)}</li>`);
            } else {
                if (inList) {
                    processed.push('</ul>');
                    inList = false;
                }
                if (trimmed) {
                    processed.push(`<p class="mb-2.5 last:mb-0 leading-relaxed">${line}</p>`);
                }
            }
        }
        if (inList) processed.push('</ul>');
        return processed.join('\n');
    }

    function appendUserMessage(text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'flex items-start justify-end gap-3 max-w-3xl ml-auto message-user animate-fade-in';
        msgDiv.innerHTML = `
            <div class="flex-1 text-right">
                <div class="inline-block text-left bg-gradient-to-r from-blue-600 to-indigo-600 border border-blue-400/30 text-white rounded-2xl rounded-tr-sm p-4 shadow-lg text-sm sm:text-base leading-relaxed">
                    ${escapeHtml(text)}
                </div>
            </div>
            <div class="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 flex-shrink-0 flex items-center justify-center text-xs font-bold text-slate-300 shadow-md">
                You
            </div>
        `;
        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function appendAssistantMessage(data) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'flex items-start gap-3 max-w-3xl message-assistant animate-fade-in';

        // Format sources section
        let sourcesHtml = '';
        if (data.sources && data.sources.length > 0) {
            const sourceItems = data.sources.map((src, i) => `
                <div class="bg-slate-950/80 border border-slate-800/90 rounded-lg p-2.5 text-xs space-y-1">
                    <div class="flex items-center justify-between gap-2">
                        <span class="font-semibold text-slate-200 truncate">[#${i + 1}] ${escapeHtml(src.title)}</span>
                        <span class="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-300 text-[10px] uppercase font-mono tracking-wider flex-shrink-0">${escapeHtml(src.category)}</span>
                    </div>
                    ${src.snippet ? `<p class="text-slate-400 text-[11px] line-clamp-2 italic">"${escapeHtml(src.snippet)}"</p>` : ''}
                </div>
            `).join('');

            sourcesHtml = `
                <div class="mt-4 pt-3 border-t border-slate-800/80">
                    <details class="group">
                        <summary class="cursor-pointer text-xs font-semibold text-slate-400 hover:text-slate-200 flex items-center gap-1.5 select-none">
                            <span class="text-blue-400">📚 Verified Sources & Citations</span>
                            <span class="px-1.5 py-0.2 rounded-full bg-slate-800 text-[10px] text-slate-300">${data.sources.length}</span>
                            <span class="text-[10px] group-open:rotate-90 transition-transform">▸</span>
                        </summary>
                        <div class="mt-2.5 space-y-2">
                            ${sourceItems}
                        </div>
                    </details>
                </div>
            `;
        }

        // Format disclaimer notice
        let disclaimerHtml = '';
        if (data.disclaimer) {
            disclaimerHtml = `
                <div class="mt-3 p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-200/90 text-xs flex items-start gap-2">
                    <span class="text-amber-400 flex-shrink-0">⚠️</span>
                    <p class="leading-relaxed">${escapeHtml(data.disclaimer)}</p>
                </div>
            `;
        }

        // Format model badge
        let modelBadgeHtml = '';
        if (data.model_used) {
            const isFallback = data.model_used.includes('llama') || data.model_used.includes('offline');
            const badgeColor = isFallback
                ? 'bg-purple-500/10 text-purple-300 border-purple-500/20'
                : 'bg-blue-500/10 text-blue-300 border-blue-500/20';
            modelBadgeHtml = `
                <span class="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded border ${badgeColor}">
                    <span>Model:</span> ${escapeHtml(data.model_used)}
                </span>
            `;
        }

        // Verified badge
        const verifiedBadgeHtml = data.is_verified
            ? `<span class="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">✓ Verified Corvit Knowledge</span>`
            : `<span class="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">Out-of-scope response</span>`;

        msgDiv.innerHTML = `
            <div class="w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-600 flex-shrink-0 flex items-center justify-center text-xs font-bold text-white shadow-md">
                AI
            </div>
            <div class="flex-1">
                <div class="bg-slate-900/90 border border-slate-800 rounded-2xl rounded-tl-sm p-4 sm:p-5 shadow-lg space-y-2">
                    <div class="message-bubble text-sm sm:text-base leading-relaxed text-slate-200">
                        ${formatMarkdown(data.answer)}
                    </div>
                    ${disclaimerHtml}
                    ${sourcesHtml}
                    <div class="mt-3 pt-2.5 border-t border-slate-800/60 flex items-center justify-between flex-wrap gap-2">
                        <div class="flex items-center gap-2 flex-wrap">
                            ${verifiedBadgeHtml}
                            ${modelBadgeHtml}
                        </div>
                        <button class="copy-msg-btn text-[11px] text-slate-400 hover:text-slate-200 flex items-center gap-1 px-2 py-1 rounded bg-slate-950/60 border border-slate-800 transition" title="Copy answer">
                            <span>Copy</span>
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Add copy action
        const copyBtn = msgDiv.querySelector('.copy-msg-btn');
        copyBtn.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(data.answer);
                copyBtn.innerHTML = '<span>✓ Copied</span>';
                setTimeout(() => { copyBtn.innerHTML = '<span>Copy</span>'; }, 2000);
            } catch (err) {
                console.error('Clipboard copy failed:', err);
            }
        });

        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Chat form submit handler
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const userText = chatInput.value.trim();
        if (!userText || isSubmitting) return;

        hideError();
        isSubmitting = true;
        sendBtn.disabled = true;
        chatInput.disabled = true;

        appendUserMessage(userText);
        chatInput.value = '';
        chatInput.style.height = 'auto';

        // Show typing indicator
        typingStatusText.textContent = userText.toLowerCase().includes('latest') || userText.toLowerCase().includes('schedule')
            ? 'Checking Corvit timetable & official announcements...'
            : 'Consulting verified Corvit knowledge base...';
        typingIndicator.classList.remove('hidden');
        chatMessages.scrollTop = chatMessages.scrollHeight;

        try {
            const payload = {
                message: userText,
                history: chatHistory.slice(-6), // Bounded recent conversation history
                allow_web_research: allowWebResearchCheck ? allowWebResearchCheck.checked : true
            };

            const response = await fetch(`${API_BASE}/api/v1/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                const errDetail = errData.detail || `Server returned HTTP ${response.status}`;
                throw new Error(errDetail);
            }

            const data = await response.json();
            appendAssistantMessage(data);

            // Update conversational history
            chatHistory.push({ role: 'user', content: userText });
            chatHistory.push({ role: 'assistant', content: data.answer });

            // Update active model badge if provided
            if (data.model_used && activeModelBadge) {
                activeModelBadge.textContent = `Model: ${data.model_used}`;
            }

        } catch (error) {
            console.error('Chat error:', error);
            showError(error.message || 'Unable to communicate with Corvit AI Advisor backend.');

            // Also render friendly error card in message stream if high demand or server down
            const fallbackCard = {
                answer: `**Advisor Connection Notice:**\n${error.message}\n\nFor immediate verified guidance on course admissions, timetables, and fee policies, please contact **Corvit Systems Admissions**:\n• **Lahore Campus**: 11A-D1, Ghalib Road, Gulberg III | Phone: 042-35762401-2\n• **Islamabad Campus**: Al Malik Center, Blue Area | Phone: 051-2348287\n• **Email**: info@corvit.com`,
                model_used: 'Offline Advisor Support',
                sources: [],
                is_verified: false,
                disclaimer: 'Connection to AI server was interrupted. Official phone assistance is available during regular business hours.'
            };
            appendAssistantMessage(fallbackCard);

        } finally {
            isSubmitting = false;
            sendBtn.disabled = false;
            chatInput.disabled = false;
            typingIndicator.classList.add('hidden');
            chatInput.focus();
        }
    });

    // ============================================================
    // 3. COURSE RECOMMENDATION WIZARD
    // ============================================================
    // Interest Pills toggling
    interestPills.forEach((pill) => {
        pill.addEventListener('click', () => {
            const val = pill.getAttribute('data-val');
            if (selectedInterests.has(val)) {
                selectedInterests.delete(val);
                pill.classList.remove('active-pill');
            } else {
                selectedInterests.add(val);
                pill.classList.add('active-pill');
            }
            document.getElementById('rec-interests').value = Array.from(selectedInterests).join(',');
        });
    });

    // Level radio styling
    levelCards.forEach((card) => {
        card.addEventListener('click', () => {
            levelCards.forEach((c) => c.classList.remove('active-level'));
            card.classList.add('active-level');
        });
    });
    // Set default active level
    levelCards[0]?.classList.add('active-level');

    // Recommendation form submit
    recForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const background = recBackground.value.trim();
        const goal = recGoal.value.trim();
        const level = document.querySelector('input[name="rec-level"]:checked')?.value || 'Beginner';
        const interests = Array.from(selectedInterests);

        if (!background) {
            alert('Please enter your educational or professional background.');
            recBackground.focus();
            return;
        }

        if (interests.length === 0) {
            alert('Please select at least one area of interest.');
            return;
        }

        // Show loading state
        recLoading.classList.remove('hidden');
        recPlaceholder.classList.add('hidden');
        recResults.classList.add('hidden');
        recCardsContainer.innerHTML = '';

        try {
            const payload = {
                background: background,
                experience_level: level,
                interests: interests,
                career_goal: goal || null
            };

            const response = await fetch(`${API_BASE}/api/v1/recommend-course`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || `Server returned HTTP ${response.status}`);
            }

            const data = await response.json();

            // Display results
            recStudentSummary.textContent = data.student_summary || `${background} • ${level}`;

            if (data.recommendations && data.recommendations.length > 0) {
                data.recommendations.forEach((rec, idx) => {
                    const card = document.createElement('div');
                    card.className = 'glass-panel rounded-2xl p-5 border border-slate-800 shadow-md space-y-3 animate-fade-in';

                    const rankColors = [
                        'from-blue-600 to-indigo-600 text-white',
                        'from-indigo-600 to-purple-600 text-white',
                        'from-slate-700 to-slate-800 text-slate-200'
                    ];
                    const rankClass = rankColors[idx] || rankColors[2];

                    // Reasons items
                    const reasonsHtml = rec.reasons.map((r) => `<li class="text-xs text-slate-300">${escapeHtml(r)}</li>`).join('');

                    card.innerHTML = `
                        <div class="flex items-start justify-between gap-3">
                            <div class="space-y-1">
                                <div class="flex items-center gap-2">
                                    <span class="px-2.5 py-0.5 rounded-md text-xs font-bold bg-gradient-to-r ${rankClass}">
                                        #${idx + 1} Best Match
                                    </span>
                                    <span class="text-xs text-slate-400">⏱️ ${escapeHtml(rec.duration || 'Standard Track')}</span>
                                </div>
                                <h5 class="text-base sm:text-lg font-bold font-outfit text-white">
                                    ${escapeHtml(rec.course_name)}
                                </h5>
                            </div>
                            <div class="text-right flex-shrink-0">
                                <div class="text-lg sm:text-xl font-extrabold text-blue-400 font-outfit">${rec.match_score}%</div>
                                <div class="text-[10px] text-slate-400 uppercase tracking-wider">Relevance</div>
                            </div>
                        </div>

                        <!-- Progress Bar -->
                        <div class="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                            <div class="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full" style="width: ${rec.match_score}%"></div>
                        </div>

                        <!-- Outline Summary -->
                        <div class="text-xs text-slate-300 leading-relaxed bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
                            <span class="font-semibold text-slate-200 block mb-1">📖 Curriculum Scope:</span>
                            ${escapeHtml(rec.outline_summary)}
                        </div>

                        <!-- Justification Reasons -->
                        <div class="space-y-1">
                            <span class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Why this is recommended for you:</span>
                            <ul class="list-disc ml-5 space-y-0.5">
                                ${reasonsHtml}
                            </ul>
                        </div>

                        ${rec.prerequisites ? `
                            <div class="text-[11px] text-slate-400 pt-2 border-t border-slate-800/60">
                                <span class="font-medium text-slate-300">Prerequisites / Background:</span> ${escapeHtml(rec.prerequisites)}
                            </div>
                        ` : ''}

                        <!-- Action button to ask about this course -->
                        <div class="pt-2 flex justify-end">
                            <button class="ask-course-btn text-xs px-3.5 py-1.5 rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 font-medium transition flex items-center gap-1.5" data-course="${escapeHtml(rec.course_name)}">
                                <span>💬 Ask AI Advisor About This Course</span>
                            </button>
                        </div>
                    `;

                    // Handle "Ask AI Advisor" click
                    const askBtn = card.querySelector('.ask-course-btn');
                    askBtn.addEventListener('click', () => {
                        const courseName = askBtn.getAttribute('data-course');
                        switchTab('chat');
                        chatInput.value = `Tell me more about the ${courseName} course at Corvit Systems, including curriculum, timings, and fees.`;
                        chatInput.dispatchEvent(new Event('input'));
                        chatInput.focus();
                        chatForm.dispatchEvent(new Event('submit'));
                    });

                    recCardsContainer.appendChild(card);
                });

                recResults.classList.remove('hidden');
            } else {
                recPlaceholder.classList.remove('hidden');
            }

        } catch (error) {
            console.error('Recommendation error:', error);
            alert(`Unable to calculate recommendations: ${error.message}`);
            recPlaceholder.classList.remove('hidden');
        } finally {
            recLoading.classList.add('hidden');
        }
    });

    console.log('Corvit AI Advisor Frontend fully initialized with API Base:', API_BASE);
});
