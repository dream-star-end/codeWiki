<template>
  <div class="h-screen flex flex-col bg-[var(--background)] overflow-hidden">
    <!-- Header -->
    <header class="sticky top-0 z-20 bg-[var(--card-bg)] border-b border-[var(--border-color)] shadow-custom">
      <div class="px-4 py-3 flex items-center justify-between">
        <div class="flex items-center gap-4">
          <router-link to="/projects" class="text-[var(--accent-primary)] hover:text-[var(--highlight)] flex items-center gap-1 text-sm">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"/>
            </svg>
            返回画廊
          </router-link>
          <div class="flex items-center gap-2">
            <div class="bg-[var(--accent-primary)] p-1.5 rounded">
              <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/>
              </svg>
            </div>
            <h1 class="text-lg font-bold text-[var(--accent-primary)]">{{ repoName }}</h1>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <a v-if="repoUrl" :href="repoUrl" target="_blank" class="text-[var(--muted)] hover:text-[var(--accent-primary)] transition-colors">
            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
          </a>
        </div>
      </div>
    </header>

    <div class="flex flex-1 min-h-0">
      <!-- Sidebar -->
      <aside class="w-72 flex-shrink-0 bg-[var(--card-bg)] border-r border-[var(--border-color)] overflow-y-auto">
        <div class="p-4">
          <!-- MCP Generator -->
          <div class="mb-3">
            <button
              class="btn-japanese w-full text-xs"
              @click="openMcpModal"
            >
              一键生成 MCP 服务
            </button>
          </div>

          <!-- Generation Info -->
          <div class="mb-6 p-3 rounded-lg bg-[var(--background)]/50 border border-[var(--border-color)]">
            <h3 class="text-xs font-semibold text-[var(--muted)] uppercase tracking-wide mb-2">生成信息</h3>
            <div class="space-y-1.5 text-xs">
              <div class="flex justify-between">
                <span class="text-[var(--muted)]">模型</span>
                <span class="text-[var(--foreground)]">{{ modelName || 'CodeWiki' }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-[var(--muted)]">符号数</span>
                <span class="text-[var(--foreground)]">{{ currentRepo?.symbols || 0 }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-[var(--muted)]">最大深度</span>
                <span class="text-[var(--foreground)]">{{ currentRepo?.depth || 2 }}</span>
              </div>
            </div>
          </div>

          <!-- Navigation Tree -->
          <nav>
            <ul class="space-y-1">
              <li v-for="(page, idx) in pages" :key="idx">
                <div class="flex items-center gap-2">
                  <button
                    @click="selectPage(idx)"
                    :class="[
                      'flex-1 text-left px-3 py-2 rounded-lg text-sm transition-colors flex items-center gap-2',
                      currentIndex === idx
                        ? 'bg-[var(--accent-primary)]/15 text-[var(--accent-primary)] border border-[var(--accent-primary)]/30'
                        : 'text-[var(--foreground)] hover:bg-[var(--background)] border border-transparent'
                    ]"
                  >
                    <span
                      :class="[
                        'w-2 h-2 rounded-full flex-shrink-0',
                        page.kind === 'overview' ? 'bg-[var(--accent-primary)]' :
                        page.kind === 'module' ? 'bg-[var(--accent-secondary)]' : 'bg-[var(--highlight)]'
                      ]"
                    ></span>
                    <span class="truncate">{{ page.kind === 'module' ? `${page.title}模块` : page.title }}</span>
                  </button>
                  <button
                    v-if="page.kind === 'module' && moduleOutlines[page.moduleId || '']?.length"
                    class="w-6 h-6 flex items-center justify-center text-[var(--muted)] hover:text-[var(--accent-primary)]"
                    @click.stop="toggleModuleExpand(page.moduleId || '')"
                  >
                    <svg
                      class="w-4 h-4 transition-transform"
                      :class="{ 'rotate-90': expandedModules.has(page.moduleId || '') }"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                    </svg>
                  </button>
                </div>
                <ul
                  v-if="page.kind === 'module' && expandedModules.has(page.moduleId || '')"
                  class="ml-6 mt-1 space-y-1"
                >
                  <li
                    v-for="item in moduleOutlines[page.moduleId || '']"
                    :key="item.id"
                  >
                    <button
                      class="text-left text-xs text-[var(--muted)] hover:text-[var(--accent-primary)] w-full px-2 py-1 rounded"
                      @click="jumpToModuleSection(page.moduleId || '', item.id)"
                    >
                      {{ item.title }}
                    </button>
                  </li>
                </ul>
              </li>
            </ul>
          </nav>
        </div>
      </aside>

      <!-- Main Content -->
      <main class="flex-1 overflow-y-auto">
        <div class="max-w-4xl mx-auto px-8 py-8">
          <!-- Page Title -->
          <h1 class="text-2xl font-bold text-[var(--foreground)] mb-6 pb-4 border-b border-[var(--border-color)]">
            {{ currentPage?.title || '加载中...' }}
          </h1>

          <!-- Loading -->
          <div v-if="loading.summary || loading.docs[currentPage?.moduleId || '']" class="py-12 text-center">
            <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--accent-primary)]"></div>
            <p class="mt-4 text-[var(--muted)]">加载文档中...</p>
          </div>

          <!-- Markdown Content -->
          <article v-else ref="contentRef" class="prose-wiki" @click="handleDocLinkClick">
            <div v-html="renderedContent"></div>
          </article>

          <!-- Related Files -->
          <div v-if="currentPage?.files?.length" class="mt-8 pt-6 border-t border-[var(--border-color)]">
            <h3 class="text-sm font-semibold text-[var(--muted)] mb-3">相关文件</h3>
            <div class="flex flex-wrap gap-2">
              <span
                v-for="file in currentPage.files.slice(0, 10)"
                :key="file"
                class="px-2 py-1 text-xs bg-[var(--background)] text-[var(--muted)] rounded border border-[var(--border-color)]"
              >
                {{ file }}
              </span>
            </div>
          </div>
        </div>
      </main>
    </div>

    <!-- Floating AI Chat Button -->
    <button
      @click="toggleChat"
      class="fixed bottom-6 right-6 w-14 h-14 bg-gradient-to-r from-[var(--accent-primary)] to-[var(--highlight)] text-white rounded-full shadow-lg hover:shadow-xl transition-all hover:scale-110 flex items-center justify-center z-30"
      :class="{ 'rotate-45': showChat }"
    >
      <svg v-if="!showChat" class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/>
      </svg>
      <svg v-else class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
      </svg>
    </button>

    <!-- Resizable Chat Dialog -->
    <Transition name="chat-slide">
      <div
        v-if="showChat"
        class="fixed bg-[var(--card-bg)] rounded-xl shadow-2xl border border-[var(--border-color)] flex flex-col z-30 overflow-hidden"
        :style="chatDialogStyle"
      >
        <!-- Resize Handles -->
        <div class="resize-handle resize-handle-n" @mousedown="startResize('n', $event)"></div>
        <div class="resize-handle resize-handle-w" @mousedown="startResize('w', $event)"></div>
        <div class="resize-handle resize-handle-nw" @mousedown="startResize('nw', $event)"></div>

        <!-- Chat Header (draggable) -->
        <div
          class="px-4 py-3 bg-gradient-to-r from-[var(--accent-primary)] to-[var(--highlight)] text-white flex items-center justify-between cursor-move select-none"
          @mousedown="startDrag"
        >
          <div class="flex items-center gap-2">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
            </svg>
            <span class="font-semibold text-sm">AI 助手</span>
          </div>
          <button @click="clearChat" class="text-white/80 hover:text-white text-xs">
            清空对话
          </button>
        </div>

        <!-- Chat Messages -->
        <div ref="chatMessagesRef" class="flex-1 overflow-y-auto p-4 space-y-4">
          <!-- Welcome message -->
          <div v-if="chatMessages.length === 0" class="text-center py-8">
            <div class="w-12 h-12 mx-auto mb-3 bg-[var(--accent-primary)]/10 rounded-full flex items-center justify-center">
              <svg class="w-6 h-6 text-[var(--accent-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
            <p class="text-sm text-[var(--muted)]">你好！我是代码库助手</p>
            <p class="text-xs text-[var(--muted)] mt-1">可以向我提问关于这个项目的任何问题</p>
          </div>

          <!-- Messages -->
          <template v-for="(msg, idx) in chatMessages" :key="idx">
            <div class="flex" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
              <div
                :class="[
                  'max-w-[90%] rounded-xl text-sm',
                  msg.role === 'user'
                    ? 'bg-[var(--accent-primary)] text-white rounded-br-sm px-3 py-2'
                    : 'bg-[var(--background)] text-[var(--foreground)] border border-[var(--border-color)] rounded-bl-sm'
                ]"
              >
                <!-- User message -->
                <span v-if="msg.role === 'user'">{{ msg.content }}</span>
                
                <!-- Assistant message with thinking -->
                <div v-else>
                  <!-- Thinking section -->
                  <div v-if="msg.thinking" class="thinking-section">
                    <button
                      @click="toggleThinking(idx)"
                      class="w-full flex items-center gap-2 px-3 py-2 text-xs text-[var(--muted)] hover:bg-[var(--background)]/50 transition-colors rounded-t-lg border-b border-[var(--border-color)]"
                    >
                      <svg
                        class="w-3.5 h-3.5 transition-transform"
                        :class="{ 'rotate-90': expandedThinking.includes(idx) }"
                        fill="none" stroke="currentColor" viewBox="0 0 24 24"
                      >
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                      </svg>
                      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                      </svg>
                      <span>思考过程</span>
                      <span class="text-[var(--accent-primary)]">({{ msg.thinking.length }} 字)</span>
                    </button>
                    <Transition name="thinking-expand">
                      <div
                        v-if="expandedThinking.includes(idx)"
                        class="px-3 py-2 text-xs text-[var(--muted)] bg-[var(--background)]/30 max-h-48 overflow-y-auto thinking-content"
                      >
                        <pre class="whitespace-pre-wrap font-sans">{{ msg.thinking }}</pre>
                      </div>
                    </Transition>
                  </div>
                  
                  <!-- Main content -->
                  <div class="prose-chat px-3 py-2" v-html="renderMarkdown(msg.content)"></div>
                  
                  <!-- Citations / References -->
                  <div v-if="msg.citations?.length" class="citations-section px-3 py-2 border-t border-[var(--border-color)]">
                    <div class="text-xs text-[var(--muted)] mb-1.5 flex items-center gap-1">
                      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/>
                      </svg>
                      <span>引用来源</span>
                    </div>
                    <div class="flex flex-wrap gap-1.5">
                      <button
                        v-for="(citation, cidx) in getUniqueCitations(msg.citations)"
                        :key="cidx"
                        @click="jumpToCitation(citation)"
                        class="citation-link text-xs px-2 py-1 rounded bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/20 transition-colors flex items-center gap-1"
                      >
                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                        </svg>
                        <span>{{ formatCitationLabel(citation) }}</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>

          <!-- Streaming message -->
          <div v-if="isStreaming" class="flex justify-start">
            <div class="max-w-[90%] bg-[var(--background)] text-[var(--foreground)] border border-[var(--border-color)] rounded-xl rounded-bl-sm">
              <!-- Streaming thinking -->
              <div v-if="streamingThinking" class="thinking-section">
                <button
                  @click="streamThinkingExpanded = !streamThinkingExpanded"
                  class="w-full flex items-center gap-2 px-3 py-2 text-xs text-[var(--muted)] hover:bg-[var(--background)]/50 transition-colors rounded-t-lg border-b border-[var(--border-color)]"
                >
                  <svg
                    class="w-3.5 h-3.5 transition-transform"
                    :class="{ 'rotate-90': streamThinkingExpanded }"
                    fill="none" stroke="currentColor" viewBox="0 0 24 24"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                  </svg>
                  <div class="flex items-center gap-1.5">
                    <span class="w-1.5 h-1.5 bg-[var(--accent-primary)] rounded-full animate-pulse"></span>
                    <span>正在思考...</span>
                  </div>
                </button>
                <Transition name="thinking-expand">
                  <div
                    v-if="streamThinkingExpanded"
                    class="px-3 py-2 text-xs text-[var(--muted)] bg-[var(--background)]/30 max-h-48 overflow-y-auto thinking-content"
                  >
                    <pre class="whitespace-pre-wrap font-sans">{{ streamingThinking }}</pre>
                  </div>
                </Transition>
              </div>
              
              <!-- Streaming content -->
              <div v-if="streamingContent" class="prose-chat px-3 py-2" v-html="renderMarkdown(streamingContent)"></div>
              
              <!-- Loading indicator when no content yet -->
              <div v-if="!streamingThinking && !streamingContent" class="px-3 py-2">
                <div class="flex items-center gap-2">
                  <span class="flex gap-1">
                    <span class="w-1.5 h-1.5 bg-[var(--accent-primary)] rounded-full animate-bounce" style="animation-delay: 0ms"></span>
                    <span class="w-1.5 h-1.5 bg-[var(--accent-primary)] rounded-full animate-bounce" style="animation-delay: 150ms"></span>
                    <span class="w-1.5 h-1.5 bg-[var(--accent-primary)] rounded-full animate-bounce" style="animation-delay: 300ms"></span>
                  </span>
                  <span class="text-[var(--muted)] text-xs">正在思考...</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Chat Input -->
        <div class="p-3 border-t border-[var(--border-color)]">
          <div class="flex gap-2">
            <input
              v-model="chatInput"
              type="text"
              placeholder="输入你的问题..."
              class="input-japanese flex-1 text-sm py-2"
              @keyup.enter="sendMessage"
              :disabled="isStreaming"
            />
            <button
              @click="sendMessage"
              :disabled="isStreaming || !chatInput.trim()"
              class="btn-japanese px-4 py-2 disabled:opacity-50"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- MCP Modal -->
    <div v-if="showMcpModal" class="fixed inset-0 z-50 bg-black/40 flex items-center justify-center" @click="closeMcpModal">
      <div class="bg-[var(--card-bg)] rounded-xl w-full max-w-4xl mx-4 p-6 shadow-xl" @click.stop>
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold text-[var(--foreground)]">MCP 服务生成结果</h3>
          <button class="text-[var(--muted)] hover:text-[var(--foreground)]" @click="closeMcpModal">×</button>
        </div>

        <div v-if="mcpLoading" class="text-sm text-[var(--muted)]">正在生成...</div>
        <div v-else-if="mcpError" class="text-sm text-[var(--highlight)]">{{ mcpError }}</div>
        <div v-else class="space-y-4 text-xs">
          <div class="flex items-center justify-between bg-[var(--background)] rounded-lg p-3">
            <div class="text-[var(--muted)]">
              状态：<span :class="mcpRunning ? 'text-green-500' : 'text-[var(--foreground)]'">{{ mcpRunning ? '运行中' : '未启动' }}</span>
              <span v-if="mcpPid" class="ml-2">PID: {{ mcpPid }}</span>
              <span v-if="mcpPort" class="ml-2">端口: {{ mcpPort }}</span>
            </div>
            <div class="flex gap-2">
              <button class="btn-japanese text-xs px-3 py-1" @click="startMcpServer" :disabled="mcpRunning">启动</button>
              <button class="btn-japanese text-xs px-3 py-1" @click="stopMcpServer" :disabled="!mcpRunning">关闭</button>
            </div>
          </div>
          <div v-if="mcpSseUrl && mcpRunning" class="bg-green-500/10 border border-green-500/30 rounded-lg p-3">
            <div class="text-green-600 font-semibold mb-1">✅ SSE 服务已就绪</div>
            <div class="text-[var(--foreground)] font-mono text-sm">{{ mcpSseUrl }}</div>
          </div>
          <div>
            <div class="flex items-center justify-between mb-2">
              <div class="font-semibold">1) MCP Server 代码（SSE 模式，可选保存）</div>
              <button class="text-[var(--accent-primary)] hover:underline" @click="copyText(mcpServerCode)">复制</button>
            </div>
            <pre class="bg-[var(--background)] rounded-lg p-3 overflow-auto max-h-60">{{ mcpServerCode }}</pre>
            <div class="text-[var(--muted)] mt-2 text-xs">
              <p>说明：系统自动管理 MCP 服务，无需手动保存此代码。如需手动运行：</p>
              <p><code>pip install mcp httpx starlette uvicorn && python {{ mcpServerFilename }}</code></p>
            </div>
          </div>

          <div>
            <div class="flex items-center justify-between mb-2">
              <div class="font-semibold">2) Cursor 配置（SSE 远程连接）</div>
              <button class="text-[var(--accent-primary)] hover:underline" @click="copyText(mcpCursorConfig)">复制</button>
            </div>
            <pre class="bg-[var(--background)] rounded-lg p-3 overflow-auto max-h-60">{{ mcpCursorConfig }}</pre>
            <div class="text-[var(--muted)] mt-2">
              <p>将配置合并到 Cursor MCP 配置文件：</p>
              <p>Windows: <code>%APPDATA%\\Cursor\\User\\globalStorage\\cursor.mcp\\config.json</code></p>
              <p>macOS: <code>~/Library/Application Support/Cursor/User/globalStorage/cursor.mcp/config.json</code></p>
            </div>
          </div>

          <div>
            <div class="flex items-center justify-between mb-2">
              <div class="font-semibold">3) 自定义 MCP Client 配置示例</div>
              <button class="text-[var(--accent-primary)] hover:underline" @click="copyText(mcpCustomConfig)">复制</button>
            </div>
            <pre class="bg-[var(--background)] rounded-lg p-3 overflow-auto max-h-60">{{ mcpCustomConfig }}</pre>
            <div class="text-[var(--muted)] mt-2">
              <p>任何支持 SSE 传输的 MCP 客户端都可以通过 URL 直接连接。</p>
            </div>
          </div>

          <div class="text-[var(--muted)]">
            <p class="font-semibold mb-1">使用说明（SSE 远程连接模式）：</p>
            <p>1. 点击上方「启动」按钮，MCP 服务将在后台运行。</p>
            <p>2. 复制 Cursor 或自定义客户端配置到对应的配置文件中。</p>
            <p>3. 重启 Cursor/Claude Desktop，AI 即可通过 SSE 连接调用此 MCP 服务。</p>
            <p class="mt-2 text-xs">注：SSE URL 格式为 <code>http://host:port/sse</code>，无需在本地启动 Python 进程。</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useWikiStore } from '../stores/wiki'
import { storeToRefs } from 'pinia'
import { marked } from 'marked'
import mermaid from 'mermaid'

// Initialize mermaid
mermaid.initialize({
  startOnLoad: false,
  theme: 'neutral',
  securityLevel: 'loose',
  flowchart: { useMaxWidth: true, htmlLabels: true },
  sequence: { useMaxWidth: true },
})

const route = useRoute()
const store = useWikiStore()
const { pages, currentIndex, loading, repos } = storeToRefs(store)

const contentRef = ref<HTMLElement | null>(null)
const chatMessagesRef = ref<HTMLElement | null>(null)
const showChat = ref(false)
const chatInput = ref('')

// Citation type from backend
interface Citation {
  file_path: string
  symbol?: string | null
  line_start?: number | null
  line_end?: number | null
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  thinking?: string
  citations?: Citation[]
}

const chatMessages = ref<ChatMessage[]>([])
const isStreaming = ref(false)
const streamingContent = ref('')
const streamingThinking = ref('')
const streamingCitations = ref<Citation[]>([])
const streamThinkingExpanded = ref(true)
const expandedThinking = ref<number[]>([])

const showMcpModal = ref(false)
const mcpLoading = ref(false)
const mcpError = ref('')
const mcpServerCode = ref('')
const mcpCursorConfig = ref('')
const mcpCustomConfig = ref('')
const mcpServerFilename = ref('')
const mcpRunning = ref(false)
const mcpPid = ref<number | null>(null)
const mcpPort = ref<number | null>(null)
const mcpSseUrl = ref('')

// Chat dialog size and position
const chatWidth = ref(420)
const chatHeight = ref(520)
const chatX = ref(window.innerWidth - 420 - 24)
const chatY = ref(window.innerHeight - 520 - 100)

const chatDialogStyle = computed(() => ({
  width: `${chatWidth.value}px`,
  height: `${chatHeight.value}px`,
  left: `${chatX.value}px`,
  top: `${chatY.value}px`,
}))

const repoId = computed(() => route.params.id as string)
const currentRepo = computed(() => repos.value.find(r => r.id === repoId.value))
const repoName = computed(() => currentRepo.value?.name || currentRepo.value?.repo || repoId.value)
const repoUrl = computed(() => {
  const r = currentRepo.value
  if (!r) return ''
  if (r.source?.startsWith('http')) return r.source
  return `https://github.com/${r.owner}/${r.repo}`
})
const modelName = computed(() => store.model.model_name || 'CodeWiki')

function buildCustomMcpConfig(sseUrl: string): string {
  const name = `${repoName.value}-codebase`
  const config = {
    mcpServers: {
      [name]: {
        url: sseUrl,
        transport: 'sse',
      },
    },
  }
  return JSON.stringify(config, null, 2)
}

async function openMcpModal() {
  showMcpModal.value = true
  mcpLoading.value = true
  mcpError.value = ''
  try {
    await fetch(`${store.apiBase}/repos/${repoId.value}/mcp/generate`, { method: 'POST' })
    const [codeRes, cursorRes] = await Promise.all([
      fetch(`${store.apiBase}/repos/${repoId.value}/mcp/server-code`),
      fetch(`${store.apiBase}/repos/${repoId.value}/mcp/cursor-config`),
    ])
    if (!codeRes.ok || !cursorRes.ok) {
      throw new Error('生成失败，请稍后重试')
    }
    const codeData = await codeRes.json()
    const cursorData = await cursorRes.json()
    mcpServerCode.value = codeData.code || ''
    mcpServerFilename.value = codeData.filename || `mcp_server_${repoId.value}.py`
    mcpCursorConfig.value = JSON.stringify(cursorData.config || {}, null, 2)
    // 获取 SSE URL 用于自定义配置
    const statusRes = await fetch(`${store.apiBase}/repos/${repoId.value}/mcp/status`)
    const statusData = await statusRes.json()
    mcpPort.value = statusData?.port ?? null
    mcpSseUrl.value = statusData?.sse_url || `http://localhost:${statusData?.port || 9100}/sse`
    mcpCustomConfig.value = buildCustomMcpConfig(mcpSseUrl.value)
    mcpRunning.value = !!statusData?.running
    mcpPid.value = statusData?.pid ?? null
  } catch (err: any) {
    mcpError.value = err?.message || '生成失败'
  } finally {
    mcpLoading.value = false
  }
}

function closeMcpModal() {
  showMcpModal.value = false
}

async function copyText(text: string) {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // ignore
  }
}

async function refreshMcpStatus() {
  try {
    const res = await fetch(`${store.apiBase}/repos/${repoId.value}/mcp/status`)
    const data = await res.json()
    mcpRunning.value = !!data?.running
    mcpPid.value = data?.pid ?? null
    mcpPort.value = data?.port ?? null
    mcpSseUrl.value = data?.sse_url || ''
    if (mcpSseUrl.value) {
      mcpCustomConfig.value = buildCustomMcpConfig(mcpSseUrl.value)
    }
  } catch {
    mcpRunning.value = false
    mcpPid.value = null
  }
}

async function startMcpServer() {
  try {
    const res = await fetch(`${store.apiBase}/repos/${repoId.value}/mcp/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_base: store.apiBase }),
    })
    const data = await res.json()
    mcpRunning.value = !!data?.running
    mcpPid.value = data?.pid ?? null
    mcpPort.value = data?.port ?? null
    mcpSseUrl.value = data?.sse_url || ''
    if (mcpSseUrl.value) {
      mcpCustomConfig.value = buildCustomMcpConfig(mcpSseUrl.value)
      // 更新 Cursor 配置
      const cursorRes = await fetch(`${store.apiBase}/repos/${repoId.value}/mcp/cursor-config`)
      if (cursorRes.ok) {
        const cursorData = await cursorRes.json()
        mcpCursorConfig.value = JSON.stringify(cursorData.config || {}, null, 2)
      }
    }
  } catch {
    mcpError.value = '启动失败'
  }
}

async function stopMcpServer() {
  try {
    const res = await fetch(`${store.apiBase}/repos/${repoId.value}/mcp/stop`, { method: 'POST' })
    const data = await res.json()
    mcpRunning.value = !!data?.running
    mcpPid.value = data?.pid ?? null
  } catch {
    mcpError.value = '停止失败'
  }
}

const currentPage = computed(() => pages.value[currentIndex.value])

// Resize handling
let isResizing = false
let resizeDirection = ''
let startX = 0
let startY = 0
let startWidth = 0
let startHeight = 0
let startLeft = 0
let startTop = 0

function startResize(direction: string, event: MouseEvent) {
  event.preventDefault()
  event.stopPropagation()
  isResizing = true
  resizeDirection = direction
  startX = event.clientX
  startY = event.clientY
  startWidth = chatWidth.value
  startHeight = chatHeight.value
  startLeft = chatX.value
  startTop = chatY.value
  document.addEventListener('mousemove', doResize)
  document.addEventListener('mouseup', stopResize)
}

function doResize(event: MouseEvent) {
  if (!isResizing) return
  
  const deltaX = event.clientX - startX
  const deltaY = event.clientY - startY
  const minWidth = 320
  const minHeight = 400
  
  if (resizeDirection.includes('w')) {
    const newWidth = Math.max(minWidth, startWidth - deltaX)
    const newLeft = startLeft + (startWidth - newWidth)
    if (newLeft > 0) {
      chatWidth.value = newWidth
      chatX.value = newLeft
    }
  }
  
  if (resizeDirection.includes('n')) {
    const newHeight = Math.max(minHeight, startHeight - deltaY)
    const newTop = startTop + (startHeight - newHeight)
    if (newTop > 0) {
      chatHeight.value = newHeight
      chatY.value = newTop
    }
  }
}

function stopResize() {
  isResizing = false
  document.removeEventListener('mousemove', doResize)
  document.removeEventListener('mouseup', stopResize)
}

// Drag handling
let isDragging = false

function startDrag(event: MouseEvent) {
  if (isResizing) return
  isDragging = true
  startX = event.clientX
  startY = event.clientY
  startLeft = chatX.value
  startTop = chatY.value
  document.addEventListener('mousemove', doDrag)
  document.addEventListener('mouseup', stopDrag)
}

function doDrag(event: MouseEvent) {
  if (!isDragging) return
  const deltaX = event.clientX - startX
  const deltaY = event.clientY - startY
  chatX.value = Math.max(0, Math.min(window.innerWidth - chatWidth.value, startLeft + deltaX))
  chatY.value = Math.max(0, Math.min(window.innerHeight - chatHeight.value, startTop + deltaY))
}

function stopDrag() {
  isDragging = false
  document.removeEventListener('mousemove', doDrag)
  document.removeEventListener('mouseup', stopDrag)
}

// Check if content is a mermaid diagram
function isMermaidContent(code: string, language: string): boolean {
  const lang = language.toLowerCase().trim()
  if (lang.startsWith('mermaid') || lang.startsWith('flowchart') || 
      lang.startsWith('sequencediagram') || lang.startsWith('graph') ||
      lang.startsWith('classdiagram') || lang.startsWith('statediagram') ||
      lang.startsWith('erdiagram') || lang.startsWith('journey') ||
      lang.startsWith('gantt') || lang.startsWith('pie') ||
      lang.startsWith('gitgraph') || lang.startsWith('mindmap')) {
    return true
  }
  const firstLine = (code.trim().split('\n')[0] || '').toLowerCase()
  return firstLine.startsWith('flowchart') || 
         firstLine.startsWith('graph ') ||
         firstLine.startsWith('sequencediagram') ||
         firstLine.startsWith('classdiagram') ||
         firstLine.startsWith('statediagram') ||
         firstLine.startsWith('erdiagram') ||
         firstLine.startsWith('journey') ||
         firstLine.startsWith('gantt') ||
         firstLine.startsWith('pie') ||
         firstLine.startsWith('gitgraph') ||
         firstLine.startsWith('mindmap')
}

function normalizeMermaidCode(code: string): string {
  const trimmed = code.trim()
  if (!trimmed) return code
  const lines = trimmed.split('\n')
  const firstLine = (lines[0] || '').trim()
  const lowerFirst = firstLine.toLowerCase()
  const directionOnly = ['lr', 'rl', 'tb', 'bt', 'td']
  if (directionOnly.includes(lowerFirst)) {
    const rest = lines.slice(1).join('\n')
    return `flowchart ${firstLine.toUpperCase()}\n${rest}`.trim()
  }
  if (
    lowerFirst.startsWith('graph ') ||
    lowerFirst.startsWith('flowchart') ||
    lowerFirst.startsWith('sequencediagram') ||
    lowerFirst.startsWith('classdiagram') ||
    lowerFirst.startsWith('statediagram') ||
    lowerFirst.startsWith('erdiagram') ||
    lowerFirst.startsWith('journey') ||
    lowerFirst.startsWith('gantt') ||
    lowerFirst.startsWith('pie') ||
    lowerFirst.startsWith('gitgraph') ||
    lowerFirst.startsWith('mindmap')
  ) {
    return trimmed
  }
  const hasEdgeSyntax = /-->|---|\-\.\-|==>|<\-\-|<\-\>|<\-\-/.test(trimmed)
  if (hasEdgeSyntax) {
    return `flowchart LR\n${trimmed}`.trim()
  }
  return trimmed
}

const moduleIdMap = computed(() => {
  const map = new Map<string, string>()
  pages.value.forEach((page) => {
    if (page.kind !== 'module' || !page.moduleId) return
    const title = (page.title || '').toLowerCase()
    const moduleId = page.moduleId
    map.set(moduleId.toLowerCase(), moduleId)
    map.set((page.moduleId || '').toLowerCase(), moduleId)
    if (page.moduleId) {
      const last = page.moduleId.split('/').pop()?.toLowerCase()
      if (last) map.set(last, moduleId)
    }
    if (title) map.set(title, moduleId)
  })
  return map
})

function resolveModuleIdFromHref(href?: string): string | null {
  if (!href) return null
  const clean = decodeURIComponent((href.split('#')[0] || '').split('?')[0] || '').replace(/\\/g, '/')
  const base = clean.split('/').pop() || clean
  const name = base.endsWith('.md') ? base.slice(0, -3) : base
  const key = name.toLowerCase()
  return moduleIdMap.value.get(key) || moduleIdMap.value.get(clean.toLowerCase()) || null
}

// Custom renderer to handle mermaid code blocks
const renderer = new marked.Renderer()
const originalCodeRenderer = renderer.code.bind(renderer)
const originalLinkRenderer = renderer.link?.bind(renderer)
function escapeAttr(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/"/g, '&quot;')
}

renderer.heading = function(token: any) {
  const text = token.text || ''
  const level = token.depth || 2
  const id = slugify(text)
  const data = escapeAttr(text)
  return `<h${level} id="${id}" data-heading="${data}">${text}</h${level}>`
}

renderer.code = function(token: any) {
  const code = typeof token === 'string' ? token : (token.text || '')
  const language = typeof token === 'string' ? '' : (token.lang || '')
  
  if (isMermaidContent(code, language)) {
    const id = `mermaid-${Math.random().toString(36).substring(2, 9)}`
    const normalized = normalizeMermaidCode(code)
    return `<div class="mermaid-container"><pre class="mermaid" id="${id}">${normalized}</pre></div>`
  }
  return originalCodeRenderer(token)
}

renderer.link = function(token: any) {
  const href = typeof token === 'string' ? token : (token.href || '')
  const title = typeof token === 'string' ? null : token.title
  const text = typeof token === 'string' ? token : (token.text || '')
  const link = href || ''
  const moduleId = resolveModuleIdFromHref(link)
  if (moduleId) {
    const safeTitle = title ? ` title="${title}"` : ''
    return `<a href="#" data-module-id="${moduleId}"${safeTitle}>${text}</a>`
  }
  if (originalLinkRenderer) {
    return originalLinkRenderer(token)
  }
  return `<a href="${link}"${title ? ` title="${title}"` : ''}>${text}</a>`
}

marked.setOptions({ renderer })

const renderedContent = computed(() => {
  if (!currentPage.value?.content) return '<p class="text-muted">暂无内容</p>'
  return marked.parse(currentPage.value.content) as string
})

function renderMarkdown(content: string): string {
  if (!content) return ''
  return marked.parse(content) as string
}

type OutlineItem = { id: string; title: string }

function slugify(text: string): string {
  // Match marked's default slugger behavior more closely
  return text
    .trim()
    .toLowerCase()
    .replace(/[^\w\u4e00-\u9fa5\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
}

function extractOutline(markdown: string): OutlineItem[] {
  if (!markdown) return []
  const tokens = marked.lexer(markdown)
  return tokens
    // Only show the next level under the module title (depth 2 headings)
    .filter((t: any) => t.type === 'heading' && t.depth === 2)
    .map((t: any) => ({ id: slugify(t.text || ''), title: t.text || '' }))
    .filter((item) => item.id && item.title)
}

const moduleOutlines = computed<Record<string, OutlineItem[]>>(() => {
  const map: Record<string, OutlineItem[]> = {}
  pages.value.forEach((page) => {
    if (page.kind !== 'module' || !page.moduleId) return
    map[page.moduleId] = extractOutline(page.content || '')
  })
  return map
})

function scrollToAnchor(id: string) {
  const el = document.getElementById(id)
  if (!el) return false
  el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  return true
}

const expandedModules = new Set<string>()
const pendingAnchor = ref<string | null>(null)
const pendingAnchorTitle = ref<string | null>(null)

function toggleModuleExpand(moduleId: string) {
  if (expandedModules.has(moduleId)) {
    expandedModules.delete(moduleId)
  } else {
    expandedModules.add(moduleId)
  }
}

// Ensure headings have ids after content updates
watch(renderedContent, async () => {
  await nextTick()
  const container = contentRef.value
  if (!container) return
  const headings = container.querySelectorAll('h2')
  headings.forEach((h) => {
    if (!h.id) {
      h.id = slugify(h.textContent || '')
    }
  })
})

// Parse thinking content from response
function parseThinkingContent(text: string): { thinking: string; content: string } {
  // Try different thinking tag formats
  const patterns = [
    /<think>([\s\S]*?)<\/think>/gi,
    /<thinking>([\s\S]*?)<\/thinking>/gi,
    /\[思考\]([\s\S]*?)\[\/思考\]/gi,
    /【思考】([\s\S]*?)【\/思考】/gi,
  ]
  
  let thinking = ''
  let content = text
  
  for (const pattern of patterns) {
    const matches = text.matchAll(pattern)
    for (const match of matches) {
      if (match[1]) {
        thinking += match[1].trim() + '\n'
        content = content.replace(match[0], '')
      }
    }
  }
  
  return { thinking: thinking.trim(), content: content.trim() }
}

// Render mermaid diagrams after content changes
async function renderMermaidDiagrams() {
  await nextTick()
  try {
    const elements = document.querySelectorAll('.mermaid:not([data-processed])')
    if (elements.length > 0) {
      await mermaid.run({ nodes: elements as NodeListOf<HTMLElement> })
    }
  } catch (e) {
    console.warn('Mermaid rendering error:', e)
  }
}

onMounted(async () => {
  store.repoId = repoId.value
  await store.loadRepos()
  await store.loadSummary('zh')
  await renderMermaidDiagrams()
  
  // Update chat position on window resize
  window.addEventListener('resize', handleWindowResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleWindowResize)
})

function handleWindowResize() {
  // Keep chat dialog within viewport
  chatX.value = Math.min(chatX.value, window.innerWidth - chatWidth.value - 24)
  chatY.value = Math.min(chatY.value, window.innerHeight - chatHeight.value - 24)
}

watch(repoId, async (newId) => {
  if (newId) {
    store.repoId = newId
    await store.loadSummary('zh')
    await renderMermaidDiagrams()
  }
})

watch(currentIndex, async () => {
  await renderMermaidDiagrams()
})

watch(renderedContent, async () => {
  await renderMermaidDiagrams()
})

// Render mermaid in chat messages when they change
watch(chatMessages, async () => {
  await renderMermaidDiagrams()
}, { deep: true })

// Render mermaid when streaming completes
watch(isStreaming, async (newVal, oldVal) => {
  if (oldVal && !newVal) {
    // Streaming just finished, render any mermaid diagrams
    await renderMermaidDiagrams()
  }
})

function selectPage(idx: number) {
  store.currentIndex = idx
  const page = pages.value[idx]
  if (page?.moduleId && page.kind === 'module') {
    if (!expandedModules.has(page.moduleId)) {
      expandedModules.add(page.moduleId)
    }
    store.loadModuleDoc(page.moduleId)
  }
}

async function jumpToModuleSection(moduleId: string, anchorTitle: string) {
  const idx = pages.value.findIndex((p) => p.moduleId === moduleId)
  if (idx >= 0) {
    console.debug('[wiki-nav] jumpToModuleSection', { moduleId, anchorTitle, idx })
    pendingAnchorTitle.value = anchorTitle
    // If already on the same module, try to scroll immediately
    if (currentIndex.value === idx) {
      await nextTick()
      if (contentRef.value) {
        const selector = `[data-heading="${escapeAttr(anchorTitle)}"]`
        const el = contentRef.value.querySelector(selector) as HTMLElement | null
        console.debug('[wiki-nav] immediateScroll', { selector, found: !!el })
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'start' })
          pendingAnchorTitle.value = null
          return
        }
      }
    }
    selectPage(idx)
  }
}

watch([renderedContent, currentIndex], async () => {
  console.debug('[wiki-nav] watcher fired', {
    hasAnchor: !!pendingAnchor.value,
    hasTitle: !!pendingAnchorTitle.value,
    currentIndex: currentIndex.value,
  })
  if (!pendingAnchor.value && !pendingAnchorTitle.value) return
  await nextTick()
  if (pendingAnchorTitle.value && contentRef.value) {
    const selector = `[data-heading="${escapeAttr(pendingAnchorTitle.value)}"]`
    const el = contentRef.value.querySelector(selector) as HTMLElement | null
    console.debug('[wiki-nav] scrollToHeading', {
      selector,
      found: !!el,
      pendingAnchorTitle: pendingAnchorTitle.value,
    })
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    } else if (pendingAnchor.value) {
      console.debug('[wiki-nav] fallback scrollToAnchor', pendingAnchor.value)
      scrollToAnchor(pendingAnchor.value)
    }
  } else if (pendingAnchor.value) {
    console.debug('[wiki-nav] scrollToAnchor', pendingAnchor.value)
    scrollToAnchor(pendingAnchor.value)
  }
  pendingAnchor.value = null
  pendingAnchorTitle.value = null
}, { flush: 'post' })

function handleDocLinkClick(event: MouseEvent) {
  const target = event.target as HTMLElement | null
  if (!target) return
  const link = target.closest('a[data-module-id]') as HTMLAnchorElement | null
  if (!link) return
  event.preventDefault()
  const moduleId = link.getAttribute('data-module-id')
  if (!moduleId) return
  const idx = pages.value.findIndex((p) => p.moduleId === moduleId)
  if (idx >= 0) {
    selectPage(idx)
  }
}

function toggleChat() {
  showChat.value = !showChat.value
  if (showChat.value) {
    // Reset position when opening
    chatX.value = window.innerWidth - chatWidth.value - 24
    chatY.value = window.innerHeight - chatHeight.value - 100
  }
}

// Get unique citations by file_path
function getUniqueCitations(citations: Citation[]): Citation[] {
  const seen = new Set<string>()
  return citations.filter(c => {
    const key = c.file_path + (c.symbol || '')
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

// Format citation label for display
function formatCitationLabel(citation: Citation): string {
  // Handle both / and \ path separators (Windows paths use \)
  const normalizedPath = citation.file_path.replace(/\\/g, '/')
  const fileName = normalizedPath.split('/').pop() || citation.file_path
  // Remove .md extension for cleaner display
  const displayName = fileName.replace(/\.md$/i, '')
  
  if (citation.symbol) {
    return `${displayName} → ${citation.symbol}`
  }
  return displayName
}

// Find module by file path and jump to it
function jumpToCitation(citation: Citation) {
  const filePath = citation.file_path
  
  // Extract filename from path (handle both / and \ separators)
  const pathParts = filePath.replace(/\\/g, '/').split('/')
  const fileName = pathParts[pathParts.length - 1] || ''
  const moduleName = fileName.replace(/\.md$/i, '').toLowerCase()
  
  // Special case: overview.md -> jump to overview page
  if (moduleName === 'overview' || moduleName === 'summary') {
    const overviewIdx = pages.value.findIndex(p => p.kind === 'overview')
    if (overviewIdx >= 0) {
      selectPage(overviewIdx)
      showChat.value = false
      return
    }
  }
  
  // Try to match by module name (from filename)
  const moduleMatch = pages.value.findIndex(page => {
    if (page.kind !== 'module' || !page.moduleId) return false
    const pageModuleName = page.moduleId.toLowerCase()
    const pageTitle = (page.title || '').toLowerCase()
    // Match by moduleId or title
    return pageModuleName === moduleName || 
           pageModuleName.endsWith('/' + moduleName) ||
           pageTitle === moduleName ||
           pageTitle === moduleName + '模块'
  })
  
  if (moduleMatch >= 0) {
    selectPage(moduleMatch)
    showChat.value = false
    return
  }
  
  // Try partial match
  const partialMatch = pages.value.findIndex(page => {
    if (page.kind !== 'module' || !page.moduleId) return false
    const pageModuleName = page.moduleId.toLowerCase()
    const pageTitle = (page.title || '').toLowerCase()
    return pageModuleName.includes(moduleName) || 
           moduleName.includes(pageModuleName) ||
           pageTitle.includes(moduleName)
  })
  
  if (partialMatch >= 0) {
    selectPage(partialMatch)
    showChat.value = false
    return
  }
  
  // Fallback: show message
  console.log('No matching module found for:', filePath, '(extracted name:', moduleName, ')')
}

function clearChat() {
  chatMessages.value = []
  expandedThinking.value = []
}

function toggleThinking(idx: number) {
  const index = expandedThinking.value.indexOf(idx)
  if (index >= 0) {
    expandedThinking.value.splice(index, 1)
  } else {
    expandedThinking.value.push(idx)
  }
}

async function scrollToBottom() {
  await nextTick()
  if (chatMessagesRef.value) {
    chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight
  }
}

async function sendMessage() {
  if (!chatInput.value.trim() || isStreaming.value) return
  
  const userMessage = chatInput.value.trim()
  chatInput.value = ''
  
  // Add user message
  chatMessages.value.push({ role: 'user', content: userMessage })
  await scrollToBottom()
  
  // Start streaming
  isStreaming.value = true
  streamingContent.value = ''
  streamingThinking.value = ''
  streamingCitations.value = []
  streamThinkingExpanded.value = true
  
  // Separate accumulators for thinking and content
  // GLM API returns reasoning_content separately via 'thinking' type
  // See: https://docs.bigmodel.cn/cn/guide/capabilities/thinking
  let thinkingContent = ''
  let answerContent = ''
  let receivedCitations: Citation[] = []
  
  try {
    const response = await fetch(`${store.apiBase}/repos/${repoId.value}/answer/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: userMessage,
        model: store.model,
        max_evidence: 5,
      }),
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    
    if (reader) {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        const chunk = decoder.decode(value)
        const lines = chunk.split('\n')
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.type === 'citations') {
                // Handle citations from RAG search
                receivedCitations = data.citations || []
                streamingCitations.value = receivedCitations
              } else if (data.type === 'thinking') {
                // Handle reasoning_content from GLM deep thinking
                thinkingContent += data.content
                streamingThinking.value = thinkingContent
                await scrollToBottom()
              } else if (data.type === 'content') {
                // Handle regular content
                answerContent += data.content
                // Also try to parse inline thinking tags for non-GLM models
                const parsed = parseThinkingContent(answerContent)
                if (parsed.thinking && !thinkingContent) {
                  streamingThinking.value = parsed.thinking
                }
                streamingContent.value = parsed.content || answerContent
                await scrollToBottom()
              } else if (data.type === 'error') {
                streamingContent.value = `错误: ${data.error}`
              }
            } catch {
              // Ignore parse errors
            }
          }
        }
      }
    }
    
    // Final processing
    // Combine GLM reasoning_content with any inline thinking tags
    const parsedAnswer = parseThinkingContent(answerContent)
    const finalThinking = thinkingContent || parsedAnswer.thinking
    const finalContent = parsedAnswer.content || answerContent
    
    // Add message with separated thinking and citations
    chatMessages.value.push({
      role: 'assistant',
      content: finalContent || '抱歉，暂时无法回答这个问题。请尝试换一种方式提问。',
      thinking: finalThinking || undefined,
      citations: receivedCitations.length > 0 ? receivedCitations : undefined,
    })
    
    // Auto-collapse thinking after done
    // (don't add to expandedThinking, so it's collapsed by default)
    
  } catch (error: any) {
    chatMessages.value.push({
      role: 'assistant',
      content: `发生错误: ${error.message || '请检查网络连接'}`,
    })
  } finally {
    isStreaming.value = false
    streamingContent.value = ''
    streamingThinking.value = ''
    streamingCitations.value = []
    await scrollToBottom()
  }
}
</script>

<style>
.prose-wiki {
  color: var(--foreground);
  line-height: 1.75;
}

.prose-wiki h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
  color: var(--foreground);
}

.prose-wiki h2 {
  font-size: 1.25rem;
  font-weight: 600;
  margin-top: 1.25rem;
  margin-bottom: 0.5rem;
  color: var(--foreground);
}

.prose-wiki h3 {
  font-size: 1rem;
  font-weight: 600;
  margin-top: 1rem;
  margin-bottom: 0.5rem;
  color: var(--foreground);
}

.prose-wiki p {
  margin-bottom: 0.75rem;
  font-size: 0.9375rem;
}

.prose-wiki ul,
.prose-wiki ol {
  margin-bottom: 0.75rem;
  padding-left: 1.5rem;
}

.prose-wiki li {
  margin-bottom: 0.25rem;
  font-size: 0.9375rem;
}

.prose-wiki code {
  background-color: var(--background);
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
  font-size: 0.875rem;
  font-family: ui-monospace, monospace;
  border: 1px solid var(--border-color);
}

.prose-wiki pre {
  background-color: #1e1e1e;
  color: #d4d4d4;
  padding: 1rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  margin: 1rem 0;
}

.prose-wiki pre code {
  background: transparent;
  padding: 0;
  border: none;
  color: inherit;
}

.prose-wiki a {
  color: var(--link-color);
  text-decoration: none;
  border-bottom: 1px solid var(--border-color);
  transition: border-color 0.2s;
}

.prose-wiki a:hover {
  border-color: var(--accent-primary);
}

.prose-wiki blockquote {
  border-left: 4px solid var(--accent-primary);
  padding-left: 1rem;
  margin: 1rem 0;
  color: var(--muted);
  font-style: italic;
}

.prose-wiki table {
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0;
}

.prose-wiki th,
.prose-wiki td {
  border: 1px solid var(--border-color);
  padding: 0.5rem 0.75rem;
  text-align: left;
}

.prose-wiki th {
  background-color: var(--background);
  font-weight: 600;
}

/* Mermaid diagram styles */
.mermaid-container {
  margin: 1.5rem 0;
  padding: 1rem;
  background: #fafafa;
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  overflow-x: auto;
}

.mermaid-container .mermaid {
  background: transparent !important;
  color: inherit !important;
  padding: 0 !important;
  margin: 0 !important;
}

.mermaid-container .mermaid svg {
  max-width: 100%;
  height: auto;
}

.prose-wiki pre.mermaid {
  background: transparent;
  color: inherit;
  padding: 0;
  margin: 0;
}

/* Chat prose styles */
.prose-chat {
  font-size: 0.875rem;
  line-height: 1.6;
}

.prose-chat p {
  margin-bottom: 0.5rem;
}

.prose-chat p:last-child {
  margin-bottom: 0;
}

.prose-chat code {
  background-color: var(--background);
  padding: 0.125rem 0.25rem;
  border-radius: 0.25rem;
  font-size: 0.8125rem;
  font-family: ui-monospace, monospace;
}

.prose-chat pre {
  background-color: #1e1e1e;
  color: #d4d4d4;
  padding: 0.75rem;
  border-radius: 0.375rem;
  overflow-x: auto;
  margin: 0.5rem 0;
  font-size: 0.75rem;
}

.prose-chat pre code {
  background: transparent;
  padding: 0;
}

.prose-chat ul, .prose-chat ol {
  padding-left: 1.25rem;
  margin-bottom: 0.5rem;
}

.prose-chat li {
  margin-bottom: 0.25rem;
}

.prose-chat h1, .prose-chat h2, .prose-chat h3 {
  font-weight: 600;
  margin-top: 0.75rem;
  margin-bottom: 0.375rem;
}

.prose-chat h1 { font-size: 1.125rem; }
.prose-chat h2 { font-size: 1rem; }
.prose-chat h3 { font-size: 0.9375rem; }

.prose-chat blockquote {
  border-left: 3px solid var(--accent-primary);
  padding-left: 0.75rem;
  margin: 0.5rem 0;
  color: var(--muted);
  font-style: italic;
}

.prose-chat table {
  width: 100%;
  border-collapse: collapse;
  margin: 0.5rem 0;
  font-size: 0.8125rem;
}

.prose-chat th,
.prose-chat td {
  border: 1px solid var(--border-color);
  padding: 0.375rem 0.5rem;
  text-align: left;
}

.prose-chat th {
  background-color: var(--background);
  font-weight: 600;
}

/* Mermaid in chat */
.prose-chat .mermaid-container {
  margin: 0.75rem 0;
  padding: 0.75rem;
  background: #fafafa;
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  overflow-x: auto;
}

.prose-chat .mermaid-container .mermaid {
  background: transparent !important;
  padding: 0 !important;
  margin: 0 !important;
}

.prose-chat .mermaid-container .mermaid svg {
  max-width: 100%;
  height: auto;
}

.prose-chat pre.mermaid {
  background: transparent;
  color: inherit;
  padding: 0;
  margin: 0;
}

/* Chat slide animation */
.chat-slide-enter-active,
.chat-slide-leave-active {
  transition: all 0.3s ease;
}

.chat-slide-enter-from,
.chat-slide-leave-to {
  opacity: 0;
  transform: translateY(20px) scale(0.95);
}

/* Thinking expand animation */
.thinking-expand-enter-active,
.thinking-expand-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}

.thinking-expand-enter-from,
.thinking-expand-leave-to {
  max-height: 0;
  opacity: 0;
}

.thinking-expand-enter-to,
.thinking-expand-leave-from {
  max-height: 12rem;
  opacity: 1;
}

/* Thinking section */
.thinking-section {
  border-bottom: 1px solid var(--border-color);
}

.thinking-content {
  font-family: ui-monospace, monospace;
  font-size: 0.75rem;
  line-height: 1.5;
  background: linear-gradient(to bottom, var(--background), transparent);
}

/* Citations section */
.citations-section {
  background: var(--background);
  border-radius: 0 0 0.75rem 0;
}

.citation-link {
  cursor: pointer;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.citation-link:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

/* Resize handles */
.resize-handle {
  position: absolute;
  z-index: 10;
}

.resize-handle-n {
  top: 0;
  left: 10px;
  right: 10px;
  height: 6px;
  cursor: n-resize;
}

.resize-handle-w {
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 6px;
  cursor: w-resize;
}

.resize-handle-nw {
  top: 0;
  left: 0;
  width: 12px;
  height: 12px;
  cursor: nw-resize;
}

.resize-handle:hover {
  background: rgba(155, 124, 185, 0.2);
}
</style>
